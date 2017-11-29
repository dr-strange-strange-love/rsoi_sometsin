
# python modules
from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_cors import CORS
from requests.exceptions import ReadTimeout
from threading import Thread
from tinydb import TinyDB, Query
import flask_login
import json
import requests

# local modules
import aggregation_lib

application = Flask(__name__)
CORS(application)
try:
    users_db = TinyDB('/Users/amadeus/Documents/rsoi_services/warehouse/users_db.json')
except:
    users_db = TinyDB('/srv/www/rsoi_services/warehouse/users_db.json')
User = Query()

login_manager = flask_login.LoginManager()
login_manager.init_app(application)

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
    order_dict = {'user': user_id}

    # step.1 - get order data
    url = 'http://127.0.0.1:8002/user/{0}/orders/{1}'.format(user_id, order_id)
    prms = {}
    hdrs = {'accept': 'application/json'}
    try:
        r = requests.get(url, params = prms, headers = hdrs, timeout = 10)
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
@application.route('/', methods = ['GET'])
def start():
    return render_template('start.html')

@application.errorhandler(404)
def page_not_found(e):
    return jsonify({'err_msg': 'Page not found'}), 404
''' --------------- --------------- '''


if __name__ == '__main__':
	application.run(host = '0.0.0.0')
