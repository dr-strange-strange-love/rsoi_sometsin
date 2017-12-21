import matplotlib
matplotlib.use('Agg')

# python modules
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template, redirect, url_for, make_response, send_file
from flask_jwt import JWT, jwt_required, current_identity
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token,
    jwt_refresh_token_required, create_refresh_token,
    get_jwt_identity, set_access_cookies,
    set_refresh_cookies, unset_jwt_cookies
)
from io import BytesIO
from multiprocessing import Lock
from requests.exceptions import ReadTimeout
from threading import Thread
from time import sleep
from tinydb import TinyDB, Query
from werkzeug.security import safe_str_cmp
import base64
import hashlib
import json
import numpy as np
import matplotlib.pyplot as plt
import pandas
import pickle
import pika
import random
import redis
import requests

application = Flask(__name__)

if application.debug is not True:
    import logging
    from logging.handlers import RotatingFileHandler
    
    handler = RotatingFileHandler("aggregation_service.log", maxBytes=100000000, backupCount=5)
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter("%(asctime)s - %(module)s - %(lineno)d - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    application.logger.addHandler(handler)

# local modules
import aggregation_lib

rds = redis.Redis('127.0.0.1', db=1) # for stats

thread = Thread(target = aggregation_lib.reset_billing_total_queue)
thread.start()
thread = Thread(target = aggregation_lib.statistics_queue_async)
thread.start()
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='rsoi_stats_sender')
channel.queue_declare(queue='rsoi_stats_feedback')

def callback(ch, method, properties, body):
    feedback_stats(json.loads(body))

channel.basic_consume(callback, queue='rsoi_stats_feedback', no_ack=True)
thread = Thread(target = channel.start_consuming)
thread.start()


# Set redis value
def set_value(rds, key, value):
    rds.set(key, pickle.dumps(value), ex=12*60*60)
# Get redis value
def get_value(rds, key):
    pickled_value = rds.get(key)
    if pickled_value is None:
        return None
    return pickle.loads(pickled_value)
def delete_key(rds, key):
    rds.delete(key)


def sent_stats_redis_scanner():
    count_max = 5

    while True:
        keys = rds.keys()
        for key in keys:
            application.logger.warning('{0}'.format(str(key)))
            val = get_value(rds, key)
            application.logger.warning('{0}'.format(str(val)))
            time_diff = datetime.utcnow() - datetime.strptime(val['time'], '%Y-%m-%d %H:%M:%S.%f')
            application.logger.warning('{0}'.format(str(time_diff)))
            if time_diff > timedelta(seconds=5):
                val['time'] = str(datetime.utcnow())
                if not val.get('count', None):
                    val['count'] = 1
                else:
                    val['count'] = val['count'] + 1
                if val['count'] >= count_max:
                    delete_key(rds, key)
                    application.logger.warning('This report timeouted: {0}'.format(str(val)))
                else:
                    set_value(rds, key, val)
                    # sending login stats
                    send_dict = val
                    channel.basic_publish(
                        exchange='',
                        routing_key='rsoi_stats_sender',
                        body=json.dumps(send_dict),
                        properties=pika.BasicProperties(delivery_mode = 2,)
                    )
        sleep(2)

t1_lock = Lock()
if t1_lock.acquire():
    thread = Thread(target = sent_stats_redis_scanner)
    thread.start()


# Tests whether to return json or render_template
def request_wants_json():
    best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
    return best == 'application/json' and request.accept_mimetypes[best] > request.accept_mimetypes['text/html']


''' --------------- JWT setup --------------- '''
application.config['SECRET_KEY'] = 'juf8477*&8sd7nsh.sJ'
application.config['JWT_TOKEN_LOCATION'] = ['cookies']
application.config['JWT_COOKIE_CSRF_PROTECT'] = False

clients = [
    {
        'client_id': 'orders_service',
        'redirect_url': 'http://127.0.0.1:8002/connect',
        'auth_code': 'suydgswe'
    },
    {
        'client_id': 'billing_service',
        'redirect_url': 'http://127.0.0.1:8003/connect',
        'auth_code': 'jdusorjg'
    },
    {
        'client_id': 'statistics_service',
        'redirect_url': 'http://127.0.0.1:8005/connect',
        'auth_code': 'isjfydth'
    }
]

class User(object):
    def __init__(self, id, username, password, role='user'):
        self.id = id
        self.username = username
        self.password = password
        self.role = role

    def __str__(self):
        return "User(id='%s')" % self.id

users = [
    User('admin', 'admin', '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 'admin'),
    User('Gilles', 'Gilles', 'c0c4a69b17a7955ac230bfc8db4a123eaa956ccf3c0022e68b8d4e2f5b699d1f', 'admin'),
    User('Felix', 'Felix', '72ab994fa2eb426c051ef59cad617750bfe06d7cf6311285ff79c19c32afd236', 'user'),
    User('Paul', 'Paul', '28f0116ef42bf718324946f13d787a1d41274a08335d52ee833d5b577f02a32a', 'user'),
]

username_table = {u.username: u for u in users}
userid_table = {u.id: u for u in users}

def authenticate(username, password):
    user = username_table.get(username, None)
    if user and safe_str_cmp(user.password.encode('utf-8'), password.encode('utf-8')):
        return user

def check_role(username, role):
    user = userid_table.get(username, None)
    if user and user.role == role:
        return True
    return False

def identity(payload):
    user_id = payload['identity']
    return userid_table.get(user_id, None)

jwt = JWTManager(application)

@application.route('/protected', methods=['GET'])
@jwt_required
def protected():
    username = get_jwt_identity()
    return jsonify({'token_holder': '{0}'.format(username)}), 200

class TokenError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)
''' --------------- --------------- '''


''' --------------- Auth and UI methods --------------- '''
@application.route('/login', methods = ['GET', 'POST'])
def login():
    if request.method == 'GET':
        return '''
               <form action='login' method='POST'>
                <input type='text' name='username' id='username' placeholder='username'/>
                <input type='password' name='password' id='password' placeholder='password'/>
                <input type='submit' name='Log in'/>
               </form>
               '''

    username = request.form['username']
    password = request.form['password']
    user = authenticate(username, hashlib.sha256(password.encode('utf-8')).hexdigest())
    if user:
        url = 'http://127.0.0.1:8004/token_simple'
        payload = {'identity': user.id}
        prms = json.dumps(payload)
        hdrs = {'Authorization': 'Basic {0}'.format(application.config['SECRET_KEY'])}
        r = requests.post(url, json = prms, headers = hdrs)
        print(r.headers)
        # sending login stats
        hash_val = '%032x' % random.getrandbits(128)
        send_dict = {
            'job': 'user login',
            'status': 'success',
            'user': username,
            'time': str(datetime.utcnow()),
            'hash': hash_val
        }
        set_value(rds, 'sent_' + hash_val, send_dict)
        channel.basic_publish(
            exchange='',
            routing_key='rsoi_stats_sender',
            body=json.dumps(send_dict),
            properties=pika.BasicProperties(delivery_mode = 2,)
        )
        '''
        aggregation_lib.statistics_q_sync.put({
            'job': 'user login',
            'status': 'success',
            'user': username,
            'time': str(datetime.utcnow()),
            'hash': '%032x' % random.getrandbits(128)
        })
        '''
        resp = make_response(jsonify({'succ_msg': 'logged in, token set up'}))
        set_access_cookies(resp, r.headers['Cookie'])
        return resp, 200
    else:
        hash_val = '%032x' % random.getrandbits(128)
        send_dict = {
            'job': 'user login',
            'status': 'failure',
            'user': username,
            'time': str(datetime.utcnow()),
            'hash': hash_val
        }
        set_value(rds, 'sent_' + hash_val, send_dict)
        channel.basic_publish(
            exchange='',
            routing_key='rsoi_stats_sender',
            body=json.dumps(send_dict),
            properties=pika.BasicProperties(delivery_mode = 2,)
        )
        '''
        aggregation_lib.statistics_q_sync.put({
            'job': 'user login',
            'status': 'failure',
            'user': username,
            'time': str(datetime.utcnow()),
            'hash': '%032x' % random.getrandbits(128)
        })
        '''
        return jsonify({'err_msg': 'user doesnt exist'}), 400

@application.route('/', methods = ['GET'])
@jwt_required
def start():
    user = get_jwt_identity()
    return render_template('start.html', prms = {'user': user}), 200

@application.route('/auth', methods = ['GET', 'POST'])
@jwt_required
def auth():
    if request.method == 'GET':
        return '''
               <form action='auth' method='POST'>
                <input type='text' name='client_id' id='client_id' placeholder='client_id'/>
                <input type='submit' name='Authenticate app'/>
               </form>
               '''

    # check client_id
    client_id = request.form['client_id']
    client_dict = dict()
    for client in clients:
        if client['client_id'] == client_id:
            print(client)
            client_dict = client
            break
    if not client_dict:
        return jsonify({'err_msg': 'no such client_id in database'}), 400

    # get client_secret (using auth_code)
    url = client_dict['redirect_url']
    payload = {'auth_code': client_dict['auth_code']}
    prms = json.dumps(payload)
    r = requests.post(url, json = prms)
    print(r.headers)
    client_secret = r.headers['Authorization'].split()[1]
    print(client_secret)

    # create and store token on session_service
    user = get_jwt_identity()
    url = 'http://127.0.0.1:8004/token'
    payload = {'identity': user, 'client_id': client_dict['client_id']}
    prms = json.dumps(payload)
    hdrs = {'Authorization': 'Basic {0}'.format(client_secret)}
    r = requests.post(url, json = prms, headers = hdrs)
    resp = r.json()

    return jsonify(resp), 200

def refresh_token(client_id, refresh_token):
    # check client_id
    client_dict = dict()
    for client in clients:
        if client['client_id'] == client_id:
            print(client)
            client_dict = client
            break
    if not client_dict:
        print('no such client_id in database')

    # get client_secret (using auth_code)
    url = client_dict['redirect_url']
    payload = {'auth_code': client_dict['auth_code']}
    prms = json.dumps(payload)
    r = requests.post(url, json = prms)
    print(r.headers)
    client_secret = r.headers['Authorization'].split()[1]
    print(client_secret)

    # create and store token on session_service
    url = 'http://127.0.0.1:8004/refresh_token'
    payload = {'refresh_token': refresh_token, 'client_id': client_dict['client_id']}
    prms = json.dumps(payload)
    hdrs = {'Authorization': 'Basic {0}'.format(client_secret)}
    r = requests.post(url, json = prms, headers = hdrs)
    print(r.text)
    print('token refreshed!')
''' --------------- --------------- '''


def feedback_stats(feedback_dict):
    delete_key(rds, 'sent_' + feedback_dict['report']['hash'])
    if feedback_dict.get('err_msg', None):
        application.logger.warning('This report couldnt be processed by statistics service: {0}'.format(str(feedback_dict['report'])))


''' --------------- Stats --------------- '''
@application.route('/admin/stats/user_login', methods = ['GET'])
@jwt_required
def user_login():
    if not check_role(get_jwt_identity(), 'admin'):
        return jsonify({'err_msg': 'admin resource, access denied'}), 400

    # get user tokens
    url = 'http://127.0.0.1:8004/user/{0}/tokens'.format(get_jwt_identity())
    r = requests.get(url)
    user_tokens = r.json()
    print(user_tokens)

    url = 'http://127.0.0.1:8005/admin/stats/user_login'
    prms = {}
    hdrs = {
        'accept': 'application/json',
        'Authorization': 'JWT {0}'.format(user_tokens.get('statistics_service', 'invalid_token'))
    }
    r = requests.get(url, params = prms, headers = hdrs, timeout = 10)
    if r.status_code == 401:
        return jsonify(r.json()), 401
    user_login = r.json()

    if request_wants_json():
        return jsonify(user_login), 200
    return render_template('user_login_attempts.html', prms = user_login)

@application.route('/admin/stats/user_login/fig')
@jwt_required
def user_login_fig():
    # get user tokens
    url = 'http://127.0.0.1:8004/user/{0}/tokens'.format(get_jwt_identity())
    r = requests.get(url)
    user_tokens = r.json()
    print(user_tokens)

    url = 'http://127.0.0.1:8005/admin/stats/user_login'
    prms = {}
    hdrs = {
        'accept': 'application/json',
        'Authorization': 'JWT {0}'.format(user_tokens.get('statistics_service', 'invalid_token'))
    }
    r = requests.get(url, params = prms, headers = hdrs, timeout = 10)
    user_login = r.json()

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
    ax.barh(ind + 1*width, df.fails, width, color='chocolate', label='number of logon failed attempts')
    ax.set(yticks=ind + width, yticklabels=df.users, ylim=[width - 1, len(df)+1])
    ax.legend()
    plt.grid()
    plt.show()

    img = BytesIO()
    plt.savefig(img)
    img.seek(0)

    return send_file(img, mimetype='image/png', cache_timeout=2)

@application.route('/admin/stats/user_bill_update', methods = ['GET'])
@jwt_required
def user_bill_update():
    if not check_role(get_jwt_identity(), 'admin'):
        return jsonify({'err_msg': 'admin resource, access denied'}), 400

    # get user tokens
    url = 'http://127.0.0.1:8004/user/{0}/tokens'.format(get_jwt_identity())
    r = requests.get(url)
    user_tokens = r.json()
    print(user_tokens)

    url = 'http://127.0.0.1:8005/admin/stats/user_bill_update'
    prms = {}
    hdrs = {
        'accept': 'application/json',
        'Authorization': 'JWT {0}'.format(user_tokens.get('statistics_service', 'invalid_token'))
    }
    r = requests.get(url, params = prms, headers = hdrs, timeout = 10)
    if r.status_code == 401:
        return jsonify(r.json()), 401
    user_bill_update = r.json()

    if request_wants_json():
        return jsonify(user_bill_update), 200
    return render_template('user_bill_update.html', prms = user_bill_update)

@application.route('/admin/stats/user_bill_update/fig', methods = ['GET'])
@jwt_required
def user_bill_update_fig():
    # get user tokens
    url = 'http://127.0.0.1:8004/user/{0}/tokens'.format(get_jwt_identity())
    r = requests.get(url)
    user_tokens = r.json()
    print(user_tokens)

    url = 'http://127.0.0.1:8005/admin/stats/user_bill_update'
    prms = {}
    hdrs = {
        'accept': 'application/json',
        'Authorization': 'JWT {0}'.format(user_tokens.get('statistics_service', 'invalid_token'))
    }
    r = requests.get(url, params = prms, headers = hdrs, timeout = 10)
    user_bill_update = r.json()

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
@jwt_required
def ops_status():
    if not check_role(get_jwt_identity(), 'admin'):
        return jsonify({'err_msg': 'admin resource, access denied'}), 400

    # get user tokens
    url = 'http://127.0.0.1:8004/user/{0}/tokens'.format(get_jwt_identity())
    r = requests.get(url)
    user_tokens = r.json()
    print(user_tokens)

    url = 'http://127.0.0.1:8005/admin/stats/ops_status'
    prms = {}
    hdrs = {
        'accept': 'application/json',
        'Authorization': 'JWT {0}'.format(user_tokens.get('statistics_service', 'invalid_token'))
    }
    r = requests.get(url, params = prms, headers = hdrs, timeout = 10)
    if r.status_code == 401:
        return jsonify(r.json()), 401
    ops_stats = r.json()

    if request_wants_json():
        return jsonify(ops_stats), 200
    return render_template('ops_status.html', prms = ops_stats)

@application.route('/admin/stats/ops_status/fig')
@jwt_required
def ops_status_fig():
    # get user tokens
    url = 'http://127.0.0.1:8004/user/{0}/tokens'.format(get_jwt_identity())
    r = requests.get(url)
    user_tokens = r.json()
    print(user_tokens)

    url = 'http://127.0.0.1:8005/admin/stats/ops_status'
    prms = {}
    hdrs = {
        'accept': 'application/json',
        'Authorization': 'JWT {0}'.format(user_tokens.get('statistics_service', 'invalid_token'))
    }
    r = requests.get(url, params = prms, headers = hdrs, timeout = 10)
    ops_stats = r.json()

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
''' --------------- --------------- '''


''' --------------- Goods methods --------------- '''
@application.route('/goods', methods = ['GET'])
def goods_list():
    page = request.args.get('page')
    size = request.args.get('size')
    if not page:
        page = "1"
    if not size:
        size = "20"

    url = 'http://127.0.0.1:8001/goods'
    prms = {'page': page, 'size': size}
    hdrs = {'accept': 'application/json'}
    try:
        r = requests.get(url, params = prms, headers = hdrs, timeout = 10)
        if r.status_code == 500:
            return jsonify({'err_msg': 'Internal server error!'}), 500
    except (OSError, ReadTimeout) as err:
        jsonify({'err_msg': 'goods service unavailable...'}), 503
    decoded_data = r.json()
    print(decoded_data)

    # Returning json-file or html-template
    if request_wants_json():
        return jsonify(decoded_data), 200
    return render_template('goods.html', prms = decoded_data)

@application.route('/goods/<good_id>', methods = ['GET'])
def good_info_by_id(good_id):
    url = 'http://127.0.0.1:8001/goods/{0}'.format(good_id)
    prms = {}
    hdrs = {'accept': 'application/json'}
    try:
        r = requests.get(url, params = prms, headers = hdrs, timeout = 10)
    except (OSError, ReadTimeout) as err:
        jsonify({'err_msg': 'goods service unavailable...'}), 503
    decoded_data = r.json()
    if not decoded_data:
        jsonify({'err_msg': 'good id doesnt exist'}), 400

    return jsonify(decoded_data), 200
''' --------------- --------------- '''


''' --------------- Orders methods --------------- '''
@application.route('/user/<user_id>/orders', methods = ['GET', 'POST'])
@jwt_required
def get_create_order(user_id):
    # get user tokens
    url = 'http://127.0.0.1:8004/user/{0}/tokens'.format(get_jwt_identity())
    r = requests.get(url)
    user_tokens = r.json()
    print(user_tokens)

    if request.method == 'GET':
        url = 'http://127.0.0.1:8002/user/{0}/orders'.format(user_id)
        prms = {}
        hdrs = {'Authorization': 'JWT {0}'.format(user_tokens.get('orders_service', 'invalid_token'))}
        try:
            r = requests.get(url, params = prms, headers = hdrs, timeout = 10)
            if r.status_code == 401:
                return jsonify(r.json()), 401
        except (OSError, ReadTimeout) as err:
            jsonify({'err_msg': 'orders service unavailable...'}), 503
        decoded_data = r.json()

        return jsonify(decoded_data), 200
    else:
        order_json = request.get_json(force=True)
        try:
            goods_list = json.loads(order_json)
        except TypeError as err:
            goods_list = order_json
        order_dict = {'goods_list': goods_list}

        # step.1 - decrement left_in_stock and calculate price (POST to goods_db, returns price)
        url = 'http://127.0.0.1:8001/goods'
        order_dict['operation'] = 'decrement'
        payload = order_dict
        prms = json.dumps(payload)
        try:
            r = requests.post(url, json = prms, timeout = 5)
        except (OSError, ReadTimeout) as err:
            return jsonify({'err_msg': 'goods service unavailable...'}), 503
        price = r.json()
        if r.status_code == 400:
            return jsonify(price), 400

        # step.2 - create billing (POST to billing_db, returns billing_id)
        url = 'http://127.0.0.1:8003/billing'
        payload = price
        prms = json.dumps(payload)
        hdrs = {'Authorization': 'JWT {0}'.format(user_tokens.get('billing_service', 'invalid_token'))}
        try:
            r = requests.post(url, json = prms, headers = hdrs, timeout = 5)
            if r.status_code == 401:
                raise TokenError('billing token invalid')
        except (OSError, ReadTimeout, TokenError) as err:
            # -step.1
            print('rollbacking1!')
            url = 'http://127.0.0.1:8001/goods'
            order_dict['operation'] = 'increment'
            payload = order_dict
            prms = json.dumps(payload)
            r = requests.post(url, json = prms)
            return jsonify({'err_msg': 'billing service unavailable, rolling back...'}), 503
        bill = r.json()

        # step.3 - create order (POST to orders_db)
        url = 'http://127.0.0.1:8002/user/{0}/orders'.format(user_id)
        payload = {
            'goods_list': goods_list,
            'billing_id': bill['bill_id']
        }
        prms = json.dumps(payload)
        hdrs = {'Authorization': 'JWT {0}'.format(user_tokens.get('orders_service', 'invalid_token'))}
        try:
            r = requests.post(url, json = prms, headers = hdrs, timeout = 10)
            if r.status_code == 401:
                raise TokenError('orders token invalid')
        except (OSError, ReadTimeout, TokenError) as err:
            # -step.1
            print('rollbacking2!')
            url = 'http://127.0.0.1:8001/goods'
            order_dict['operation'] = 'increment'
            payload = order_dict
            prms = json.dumps(payload)
            r = requests.post(url, json = prms)
            # -step.2
            url = 'http://127.0.0.1:8003/billing/' + str(bill['bill_id'])
            r = requests.delete(url)
            return jsonify({'err_msg': 'orders service unavailable, rolling back...'}), 503
        print(r.text)
        order = r.json()

        return jsonify(order), 200

@application.route('/user/<user_id>/orders/<order_id>', methods = ['GET'])
@jwt_required
def order_info(user_id, order_id):
    # get user tokens
    url = 'http://127.0.0.1:8004/user/{0}/tokens'.format(get_jwt_identity())
    r = requests.get(url)
    user_tokens = r.json()
    print(user_tokens)

    order_dict = {'user': user_id}

    # step.1 - get order data
    url = 'http://127.0.0.1:8002/user/{0}/orders/{1}'.format(user_id, order_id)
    prms = {}
    hdrs = {'Authorization': 'JWT {0}'.format(user_tokens.get('orders_service', 'invalid_token'))}
    try:
        r = requests.get(url, params = prms, headers = hdrs, timeout = 10)
        if r.status_code == 401:
            r_dict = r.json()
            if r_dict['description'] == 'Signature has expired':
                refresh_token('orders_service', user_tokens.get('orders_service_refresh', 'invalid_token'))
            return jsonify(r_dict), 401
    except (OSError, ReadTimeout) as err:
        return jsonify({'err_msg': 'orders service unavailable...'}), 503
    user_order = r.json()

    try:
        goods_list = []
        for good in user_order['goods']:
            goods_list.append(good)
        order_dict['goods'] = goods_list
    except:
        return jsonify(user_order), 400

    # step.2 - get billing data for that order (if can't - degrade)
    url = 'http://127.0.0.1:8003/billing/' + str(user_order['billing_id'])
    prms = {}
    hdrs = {'Authorization': 'JWT {0}'.format(user_tokens.get('billing_service', 'invalid_token'))}
    try:
        r = requests.get(url, params = prms, headers = hdrs, timeout = 5)
        if r.status_code == 401:
            raise TokenError('billing token invalid')
        billing_info = r.json()
        order_dict['billing_info'] = billing_info
    except (OSError, ReadTimeout) as err:
        order_dict['billing_info'] = 'billing service unavailable!'
    except TokenError as err:
        refresh_token('billing_service', user_tokens.get('billing_service_refresh', 'invalid_token'))
        order_dict['billing_info'] = 'billing token invalid, refreshing!'

    return jsonify(order_dict), 200

@application.route('/user/<user_id>/orders/<order_id>/goods', methods = ['DELETE'])
@jwt_required
def delete_goods_from_order(user_id, order_id):
    # get user tokens
    url = 'http://127.0.0.1:8004/user/{0}/tokens'.format(get_jwt_identity())
    r = requests.get(url)
    user_tokens = r.json()
    print(user_tokens)

    # step.1 - get goods info from order (GET from orders_db)
    url = 'http://127.0.0.1:8002/user/{0}/orders/{1}'.format(user_id, order_id)
    prms = {}
    hdrs = {'accept': 'application/json'}
    hdrs = {'Authorization': 'JWT {0}'.format(user_tokens.get('orders_service', 'invalid_token'))}
    try:
        r = requests.get(url, params = prms, headers = hdrs, timeout = 10)
        if r.status_code == 401:
            raise TokenError('orders token invalid')
    except (OSError, ReadTimeout) as err:
        return jsonify({'err_msg': 'orders service unavailable...'}), 503
    except TokenError as err:
        return jsonify({'err_msg': 'orders_service token invalid...'}), 401
    user_order = r.json()
    try:
        billing_id = user_order['billing_id']
        goods_list = user_order['goods']
        order_dict = {'goods_list': goods_list}
    except:
        return jsonify(user_order), 400

    # step.2 - increment left_in_stock (POST to goods_db)
    url = 'http://127.0.0.1:8001/goods'
    order_dict['operation'] = 'increment'
    payload = order_dict
    prms = json.dumps(payload)
    try:
        r = requests.post(url, json = prms, timeout = 10)
    except (OSError, ReadTimeout) as err:
        return jsonify({'err_msg': 'goods service unavailable...'}), 503
    print(r.text)

    # step.3 - reduce goods to [] (DELETE/POST to order_db)
    aggregation_lib.statistics_q_async.put({
        'url': 'http://127.0.0.1:8002/orders/{0}/goods'.format(order_id),
        'method': 'DELETE',
        'payload': {},
        'headers': {},
        'job': 'goods removal',
        'user': get_jwt_identity(),
        'time': str(datetime.utcnow()),
        'hash': '%032x' % random.getrandbits(128)
    })
    '''
    url = 'http://127.0.0.1:8002/orders/{0}/goods'.format(order_id)
    r = requests.delete(url, timeout = 10)
    print(r.text)
    '''

    # step.4 - update bill (PATCH to billing_db)
    aggregation_lib.statistics_q_async.put({
        'url': 'http://127.0.0.1:8003/billing/' + str(billing_id),
        'method': 'PATCH',
        'payload': {'total': 0},
        'headers': {'Authorization': 'JWT {0}'.format(user_tokens.get('billing_service', 'invalid_token'))},
        'job': 'bill update',
        'user': get_jwt_identity(),
        'time': str(datetime.utcnow()),
        'hash': '%032x' % random.getrandbits(128)
    })
    '''
    url = 'http://127.0.0.1:8003/billing/' + str(billing_id)
    payload = {'total': 0}
    prms = json.dumps(payload)
    hdrs = {'Authorization': 'JWT {0}'.format(user_tokens.get('billing_service', 'invalid_token'))}
    try:
        r = requests.patch(url, json = prms, timeout = 5)
        if r.status_code == 401:
            raise TokenError('billing token invalid')
    except (ReadTimeout, TokenError) as err:
        aggregation_lib.reset_billing_total_q.put(url)
    '''

    return jsonify({'succ_msg': 'Goods are being removerd, check logs!'}), 200

@application.route('/user/<user_id>/orders/<order_id>/billing', methods = ['PATCH'])
@jwt_required
def perform_billing(user_id, order_id):
    # get user tokens
    url = 'http://127.0.0.1:8004/user/{0}/tokens'.format(get_jwt_identity())
    r = requests.get(url)
    user_tokens = r.json()
    print(user_tokens)

    billing_json = request.get_json(force=True)
    try:
        billing_dict = json.loads(billing_json)
    except:
        billing_dict = billing_json

    # step.1 - get billing_id from orders (GET from orders_db)
    url = 'http://127.0.0.1:8002/user/{0}/orders/{1}'.format(user_id, order_id)
    prms = {}
    hdrs = {'accept': 'application/json'}
    hdrs = {'Authorization': 'JWT {0}'.format(user_tokens.get('orders_service', 'invalid_token'))}
    try:
        r = requests.get(url, params = prms, headers = hdrs, timeout = 10)
        if r.status_code == 401:
            raise TokenError('orders token invalid')
    except (OSError, ReadTimeout) as err:
        return jsonify({'err_msg': 'orders service unavailable...'}), 503
    except TokenError as err:
        return jsonify({'err_msg': 'orders service token invalid...'}), 401
    user_order = r.json()
    try:
        billing_id = user_order['billing_id']
    except:
        return jsonify(user_order), 400

    # step.2 - update bill (PATCH to billing_db)
    aggregation_lib.statistics_q_async.put({
        'url': 'http://127.0.0.1:8003/billing/' + str(billing_id),
        'method': 'PATCH',
        'payload': billing_dict,
        'headers': {'Authorization': 'JWT {0}'.format(user_tokens.get('billing_service', 'invalid_token'))},
        'job': 'bill update',
        'user': get_jwt_identity(),
        'time': str(datetime.utcnow()),
        'hash': '%032x' % random.getrandbits(128)
    })
    '''
    url = 'http://127.0.0.1:8003/billing/' + str(billing_id)
    payload = billing_dict
    prms = json.dumps(payload)
    hdrs = {'Authorization': 'JWT {0}'.format(user_tokens.get('billing_service', 'invalid_token'))}
    try:
        r = requests.patch(url, json = prms, headers = hdrs, timeout = 10)
        if r.status_code == 401:
            raise TokenError('billing token invalid')
    except (OSError, ReadTimeout) as err:
        jsonify({'err_msg': 'server unavailable!'}), 503
    except TokenError as err:
        return jsonify({'err_msg': 'billing service token invalid...'}), 401
    res = r.json()
    '''

    return jsonify({'succ_msh': 'bill is being updated, check logs...'}), 200
''' --------------- --------------- '''


''' --------------- General methods --------------- '''
@application.errorhandler(404)
def page_not_found(e):
    return jsonify({'err_msg': 'Page not found'}), 404
''' --------------- --------------- '''


if __name__ == '__main__':
	application.run(host = '0.0.0.0')
