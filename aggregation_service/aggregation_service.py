
# python modules
from flask import Flask, jsonify, request, render_template, redirect, url_for, make_response
from flask_jwt import JWT, jwt_required, current_identity
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token,
    jwt_refresh_token_required, create_refresh_token,
    get_jwt_identity, set_access_cookies,
    set_refresh_cookies, unset_jwt_cookies
)
from requests.exceptions import ReadTimeout
from threading import Thread
from tinydb import TinyDB, Query
from werkzeug.security import safe_str_cmp
import base64
import hashlib
import json
import requests

# local modules
import aggregation_lib

application = Flask(__name__)

thread = Thread(target = aggregation_lib.reset_billing_total_queue)
thread.start()

if application.debug is not True:
    import logging
    from logging.handlers import RotatingFileHandler
    
    handler = RotatingFileHandler("aggregation_service.log", maxBytes=100000000, backupCount=5)
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter("%(asctime)s - %(module)s - %(lineno)d - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    application.logger.addHandler(handler)


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
    }
]

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

jwt = JWTManager(application)

@application.route('/protected', methods=['GET'])
@jwt_required
def protected():
    username = get_jwt_identity()
    return jsonify({'token_holder': '{0}'.format(username)}), 200
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
        resp = make_response(jsonify({'succ_msg': 'logged in, token set up'}))
        set_access_cookies(resp, r.headers['Cookie'])
        return resp, 200
    else:
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

    return jsonify(decoded_data), 200

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
def get_create_order(user_id):
    if request.method == 'GET':
        url = 'http://127.0.0.1:8002/user/{0}/orders'.format(user_id)
        prms = {}
        hdrs = {'accept': 'application/json'}
        try:
            r = requests.get(url, params = prms, headers = hdrs, timeout = 10)
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
        try:
            r = requests.post(url, json = prms, timeout = 5)
        except (OSError, ReadTimeout) as err:
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
        try:
            r = requests.post(url, json = prms, timeout = 10)
        except (OSError, ReadTimeout) as err:
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
            return jsonify({'err_msg': 'orders service unavailable, rolling back'}), 503
        print(r.text)
        order = r.json()

        return jsonify(order), 200

@application.route('/user/<user_id>/orders/<order_id>', methods = ['GET'])
def order_info(user_id, order_id):
    # get user tokens
    url = 'http://127.0.0.1:8004/user/{0}/tokens'.format(str(user_id))
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
            return jsonify(r.json()), 401
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
    hdrs = {'accept': 'application/json'}
    try:
        r = requests.get(url, params = prms, headers = hdrs, timeout = 5)
        billing_info = r.json()
        order_dict['billing_info'] = billing_info
    except (OSError, ReadTimeout) as err:
        order_dict['billing_info'] = 'billing service unavailable!'

    return jsonify(order_dict), 200

@application.route('/user/<user_id>/orders/<order_id>/goods', methods = ['DELETE'])
def delete_goods_from_order(user_id, order_id):
    # step.1 - get goods info from order (GET from orders_db)
    url = 'http://127.0.0.1:8002/user/{0}/orders/{1}'.format(user_id, order_id)
    prms = {}
    hdrs = {'accept': 'application/json'}
    try:
        r = requests.get(url, params = prms, headers = hdrs, timeout = 10)
    except (OSError, ReadTimeout) as err:
        return jsonify({'err_msg': 'orders service unavailable...'}), 503
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
    url = 'http://127.0.0.1:8002/orders/{0}/goods'.format(order_id)
    r = requests.delete(url, timeout = 10)
    print(r.text)

    # step.4 - update bill (PATCH to billing_db)
    url = 'http://127.0.0.1:8003/billing/' + str(billing_id)
    payload = {'total': 0}
    prms = json.dumps(payload)
    try:
        r = requests.patch(url, json = prms, timeout = 5)
        print(r.text)
    except ReadTimeout as err:
        aggregation_lib.reset_billing_total_q.put(url)

    return jsonify({'succ_msg': 'Goods removed successfully!'}), 200

@application.route('/user/<user_id>/orders/<order_id>/billing', methods = ['PATCH'])
def perform_billing(user_id, order_id):
    billing_json = request.get_json(force=True)
    try:
        billing_dict = json.loads(billing_json)
    except:
        billing_dict = billing_json

    # step.1 - get billing_id from orders (GET from orders_db)
    url = 'http://127.0.0.1:8002/user/{0}/orders/{1}'.format(user_id, order_id)
    prms = {}
    hdrs = {'accept': 'application/json'}
    try:
        r = requests.get(url, params = prms, headers = hdrs, timeout = 10)
    except (OSError, ReadTimeout) as err:
        return jsonify({'err_msg': 'orders service unavailable...'}), 503
    user_order = r.json()
    try:
        billing_id = user_order['billing_id']
    except:
        return jsonify(user_order), 400

    # step.2 - update bill (PATCH to billing_db)
    url = 'http://127.0.0.1:8003/billing/' + str(billing_id)
    payload = billing_dict
    prms = json.dumps(payload)
    try:
        r = requests.patch(url, json = prms, timeout = 10)
        print(r.text)
    except (OSError, ReadTimeout) as err:
        jsonify({'err_msg': 'server unavailable!'}), 503
    res = r.json()

    return jsonify(res), 200
''' --------------- --------------- '''


''' --------------- General methods --------------- '''
@application.errorhandler(404)
def page_not_found(e):
    return jsonify({'err_msg': 'Page not found'}), 404
''' --------------- --------------- '''


if __name__ == '__main__':
	application.run(host = '0.0.0.0')
