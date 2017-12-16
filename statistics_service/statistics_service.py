import matplotlib
matplotlib.use('Agg')

# python modules
from flask import Flask, jsonify, request, render_template, redirect, url_for, make_response, send_file
from flask_jwt import JWT, jwt_required, current_identity
from werkzeug.security import safe_str_cmp
import json
import pickle
import redis

import numpy as np
import matplotlib.pyplot as plt
import pandas
from io import BytesIO

application = Flask(__name__)

# local modules
import statistics_lib

rds = redis.Redis('127.0.0.1')

if application.debug is not True:
    import logging
    from logging.handlers import RotatingFileHandler
    
    handler = RotatingFileHandler("statistics_service.log", maxBytes=100000000, backupCount=5)
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter("%(asctime)s - %(module)s - %(lineno)d - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    application.logger.addHandler(handler)


# Tests whether to return json or render_template
def request_wants_json():
    best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
    return best == 'application/json' and request.accept_mimetypes[best] > request.accept_mimetypes['text/html']


# Set redis value
def set_value(rds, key, value):
    rds.set(key, pickle.dumps(value), ex=12*60*60)
# Get redis value
def get_value(rds, key):
    pickled_value = rds.get(key)
    if pickled_value is None:
        return None
    return pickle.loads(pickled_value)


''' --------------- JWT Oauth2 setup --------------- '''
application.config['SECRET_KEY'] = 'JOIASUdigao987nahisuf'
authorization_code = 'isjfydth'

class User(object):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

    def __str__(self):
        return "User(id='%s')" % self.id

users = [
    User('Gilles', 'Gilles', 'c0c4a69b17a7955ac230bfc8db4a123eaa956ccf3c0022e68b8d4e2f5b699d1f'),
    User('Felix', 'Felix', '72ab994fa2eb426c051ef59cad617750bfe06d7cf6311285ff79c19c32afd236'),
    User('Paul', 'Paul', '28f0116ef42bf718324946f13d787a1d41274a08335d52ee833d5b577f02a32a'),
]

username_table = {u.username: u for u in users}
userid_table = {u.id: u for u in users}

def authenticate(username, password):
    user = username_table.get(username, None)
    if user and safe_str_cmp(user.password.encode('utf-8'), password.encode('utf-8')):
        return user

def identity(payload):
    user_id = payload['identity']
    return userid_table.get(user_id, None)

jwt = JWT(application, authenticate, identity)

@application.route('/protected')
@jwt_required()
def protected():
    return jsonify({'token_holder': current_identity.id}), 200

@application.route('/connect', methods = ['POST'])
def connect():
    connect_json = request.get_json(force=True)
    connect_dict = json.loads(connect_json)
    auth_code = connect_dict['auth_code']
    if not (auth_code == authorization_code):
        return jsonify({'err_msg': 'auth_code incorrect'}), 400

    resp = make_response(jsonify({'succ_msg': 'can connect!'}))
    resp.headers['Authorization'] = 'Basic {0}'.format(application.config['SECRET_KEY'])
    return resp, 200
''' --------------- --------------- '''


@application.route('/report', methods = ['PATCH'])
def report():
    report_json = request.get_json(force=True)
    report_dict = json.loads(report_json)
    print(report_dict)

    if not get_value(rds, report_dict['hash']):
        set_value(rds, report_dict['hash'], True)
        statistics_lib.push_event(report_dict['job'],
                                  report_dict['status'],
                                  report_dict['user'],
                                  report_dict['time'],
                                  msg_json = report_dict.get('msg_json', None),
                                  status_code = report_dict.get('status_code', None),
                                  url = report_dict.get('url', None),
                                  payload = report_dict.get('payload', None))
    else:
        return jsonify({'succ_msg': 'report already exists'}), 200

    return jsonify({'succ_msg': 'report delivered'}), 200

@application.route('/admin/stats/user_login', methods = ['GET'])
def user_login():
    user_login = statistics_lib.get_user_login_data()
    if request_wants_json():
        return jsonify(user_login), 200
    return render_template('user_login_attempts.html', prms = user_login)

@application.route('/admin/stats/user_login/fig')
def user_login_fig():
    user_login = statistics_lib.get_user_login_data()

    user_fails = dict()
    for user_stat in user_login:
        if not user_fails.get(user_stat['user'], None):
            user_fails[user_stat['user']] = 0
        if user_stat['status'] != 'success':
            user_fails[user_stat['user']] = user_fails[user_stat['user']] + 1
    print(user_fails)

    users = []
    fails = []
    for key in user_fails:
        users.append(key)
        fails.append(user_fails[key])
    print(users)
    print(fails)

    df = pandas.DataFrame(dict(\
        users=users,
        fails=fails
    ))

    #Plotting
    fig, ax = plt.subplots()
    fig.set_size_inches(12, 5)
    plt.title('User failed logon attempts')
    ax.set_xlabel('Failed logon attempts')
    ax.set_ylabel('Users')
    ind = np.arange(len(df))
    width = 0.8
    ax.barh(ind + 1*width, df.fails, width, color='chocolate', label='success rate')
    ax.set(yticks=ind + width, yticklabels=df.users, ylim=[width - 1, len(df)+1])
    ax.legend()
    plt.grid()
    plt.show()

    img = BytesIO()
    plt.savefig(img)
    img.seek(0)

    return send_file(img, mimetype='image/png', cache_timeout=2)

@application.route('/admin/stats/user_bill_update', methods = ['GET'])
def user_bill_update():
    user_bill_update = statistics_lib.get_user_bill_update_data()
    if request_wants_json():
        return jsonify(user_bill_update), 200
    return render_template('user_bill_update.html', prms = user_bill_update)

@application.route('/admin/stats/user_bill_update/fig', methods = ['GET'])
def user_bill_update_fig():
    user_bill_update = statistics_lib.get_user_bill_update_data()

    bill_update_dict = {'success': 0, 'failure': 0, 'timedout': 0, 'total': 0}
    for bill_update_stat in user_bill_update:
        bill_update_dict['total'] = bill_update_dict['total'] + 1
        if bill_update_stat['status'] == 'success':
            bill_update_dict['success'] = bill_update_dict['success'] + 1
        elif bill_update_stat['status'] == 'failure':
            bill_update_dict['failure'] = bill_update_dict['failure'] + 1
        else: # timedout
            bill_update_dict['timedout'] = bill_update_dict['timedout'] + 1
    print(bill_update_dict)
    success_rate = bill_update_dict['success']/bill_update_dict['total']
    print(success_rate)
    failure_rate = bill_update_dict['failure']/bill_update_dict['total']
    print(failure_rate)
    timedout_rate = bill_update_dict['timedout']/bill_update_dict['total']
    print(timedout_rate)

    # Pie chart, where the slices will be ordered and plotted counter-clockwise:
    labels = 'Success ratio', 'Failure ratio', 'Timedout ratio'
    sizes = [success_rate, failure_rate, timedout_rate]
    explode = (0.1, 0, 0)

    fig1, ax1 = plt.subplots()
    ax1.pie(sizes, explode=explode, labels=labels, autopct='%1.1f%%', shadow=True, startangle=90)
    ax1.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
    plt.show()

    img = BytesIO()
    plt.savefig(img)
    img.seek(0)

    return send_file(img, mimetype='image/png', cache_timeout=2)

@application.route('/admin/stats/ops_status', methods = ['GET'])
def ops_status():
    ops_status = statistics_lib.get_ops_status()
    if request_wants_json():
        return jsonify(ops_status), 200
    return render_template('ops_status.html', prms = ops_status)

@application.route('/admin/stats/ops_status/fig')
def ops_status_fig():
    ops_stats = statistics_lib.get_ops_status()

    ops = []
    ratios = []
    for key in ops_stats:
        ops.append(key)
        ratios.append(ops_stats[key]['success']/ops_stats[key]['total'])
    print(ops)
    print(ratios)

    df = pandas.DataFrame(dict(\
        ops=ops,
        ratios=ratios
    ))

    #Plotting
    fig, ax = plt.subplots()
    fig.set_size_inches(12, 5)
    plt.title('Ops success rates')
    ax.set_xlabel('Ratios')
    ax.set_ylabel('Ops')
    ind = np.arange(len(df))
    width = 0.8
    ax.barh(ind + 1*width, df.ratios, width, color='chocolate', label='success rate')
    ax.set(yticks=ind + width, yticklabels=df.ops, ylim=[width - 1, len(df)+1])
    ax.set_xlim([0, 1])
    ax.legend()
    plt.grid()
    plt.show()

    img = BytesIO()
    plt.savefig(img)
    img.seek(0)

    return send_file(img, mimetype='image/png', cache_timeout=2)


@application.route('/', methods = ['GET'])
def start():
    return jsonify({'succ_msg': 'Welcome!'}), 200

@application.errorhandler(404)
def page_not_found(e):
    return jsonify({'err_msg': 'Page not found'}), 404


if __name__ == '__main__':
    application.run(host = '0.0.0.0')
