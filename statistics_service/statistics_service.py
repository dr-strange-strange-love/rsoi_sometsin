# python modules
from flask import Flask, jsonify, request, render_template, redirect, url_for, make_response, send_file
from flask_jwt import JWT, jwt_required, current_identity
from multiprocessing import Lock
from threading import Thread
from werkzeug.security import safe_str_cmp
import json
import pickle
import pika
import redis

application = Flask(__name__)

# local modules
import statistics_lib

rds = redis.Redis('127.0.0.1', db=2)

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
channel = connection.channel()

if application.debug is not True:
    import logging
    from logging.handlers import RotatingFileHandler
    
    handler = RotatingFileHandler("statistics_service.log", maxBytes=100000000, backupCount=5)
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter("%(asctime)s - %(module)s - %(lineno)d - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    application.logger.addHandler(handler)


# Set redis value
def set_value(rds, key, value):
    rds.set(key, pickle.dumps(value), ex=12*60*60)
# Get redis value
def get_value(rds, key):
    pickled_value = rds.get(key)
    if pickled_value is None:
        return None
    return pickle.loads(pickled_value)


def report_stats(report_dict):
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

        channel.basic_publish(
            exchange='',
            routing_key='rsoi_stats_feedback',
            body=json.dumps({
                'succ_msg': '{0} reported OK'.format(report_dict['hash']),
                'report': report_dict
            })
        )
    else:
        channel.basic_publish(
            exchange='',
            routing_key='rsoi_stats_feedback',
            body=json.dumps({
                'err_msg': '{0} has already been processed'.format(report_dict['hash']),
                'report': report_dict
            })
        )

def callback(ch, method, properties, body):
        report_stats(json.loads(body))

t1_lock = Lock()
if t1_lock.acquire():
    channel.basic_consume(callback, queue='rsoi_stats_sender', no_ack=True)
    thread = Thread(target = channel.start_consuming)
    thread.start()


# Tests whether to return json or render_template
def request_wants_json():
    best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
    return best == 'application/json' and request.accept_mimetypes[best] > request.accept_mimetypes['text/html']


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
    User('admin', 'admin', '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918'),
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
    from_date = request.args.get('from_date')
    if not from_date:
        from_date = '1900-00-00'

    user_login = statistics_lib.get_user_login_data(from_date=from_date)
    return jsonify(user_login), 200

@application.route('/admin/stats/user_bill_update', methods = ['GET'])
def user_bill_update():
    user_bill_update = statistics_lib.get_user_bill_update_data()
    return jsonify(user_bill_update), 200

@application.route('/admin/stats/ops_status', methods = ['GET'])
def ops_status():
    ops_status = statistics_lib.get_ops_status()
    return jsonify(ops_status), 200


@application.route('/', methods = ['GET'])
def start():
    return jsonify({'succ_msg': 'Welcome!'}), 200

@application.errorhandler(404)
def page_not_found(e):
    return jsonify({'err_msg': 'Page not found'}), 404


if __name__ == '__main__':
    application.run(host = '0.0.0.0')
