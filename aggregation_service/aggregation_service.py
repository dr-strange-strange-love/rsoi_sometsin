
# python modules
from flask import Flask, jsonify, request, render_template, redirect, url_for
from requests.exceptions import ReadTimeout
from tinydb import TinyDB, Query
import flask_login
import json
import requests

# local modules
import aggregation_lib

application = Flask(__name__)
users_db = TinyDB('/Users/amadeus/Documents/rsoi_services/warehouse/users_db.json')
User = Query()
application.secret_key = '8cHHshdj*_ASI(jsd'

login_manager = flask_login.LoginManager()
login_manager.init_app(application)

if application.debug is not True:
    import logging
    from logging.handlers import RotatingFileHandler
    
    handler = RotatingFileHandler("aggregation_service.log", maxBytes=100000000, backupCount=5)
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter("%(asctime)s - %(module)s - %(lineno)d - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    application.logger.addHandler(handler)


''' --------------- Login methods --------------- '''
class User(flask_login.UserMixin):
    pass

@login_manager.user_loader
def user_loader(name):
    flag = False
    users = users_db.all()
    for user in users:
        if user['username'] == name:
            flag = True
            
    if not flag:
        return

    user = User()
    user.id = name
    return user

@login_manager.request_loader
def request_loader(request):
    username = request.form.get('username')

    flag = False
    users = users_db.all()
    for user in users:
        if user['username'] == username:
            active_user = user
            flag = True
            
    if not flag:
        return

    user = User()
    user.id = username

    user.is_authenticated = request.form['password'] == active_user['password']

    return user

@application.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return '''
               <form action='login' method='POST'>
                <input type='text' name='email' id='email' placeholder='email'/>
                <input type='password' name='password' id='password' placeholder='password'/>
                <input type='submit' name='submit'/>
               </form>
               '''

    email = request.form['email']

    print(email)
    print(request.form['password'])

    # workaround, password - 1q2w3e
    if request.form['password'] == 'c0c4a69b17a7955ac230bfc8db4a123eaa956ccf3c0022e68b8d4e2f5b699d1f':
        user = User()
        user.id = email
        flask_login.login_user(user)
        return redirect(url_for('protected'))

    return 'Bad login'


@application.route('/protected')
@flask_login.login_required
def protected():
    return 'Logged in as: ' + flask_login.current_user.id
''' --------------- --------------- '''


''' --------------- Goods methods --------------- '''
@application.route('/goods', methods = ['GET'])
def goods_list():
    try:
        page = request.args.get('page')
        size = request.args.get('size')
    except:
        page = 1
        size = 20

    url = 'http://127.0.0.1:8001/goods'
    prms = {'page': page, 'size': size}
    hdrs = {'accept': 'application/json'}
    r = requests.get(url, params = prms, headers = hdrs)
    decoded_data = r.json()

    return jsonify(decoded_data)

@application.route('/goods/<good_id>', methods = ['GET'])
def good_info_by_id(good_id):
    url = 'http://127.0.0.1:8001/goods/' + good_id
    prms = {}
    hdrs = {'accept': 'application/json'}
    r = requests.get(url, params = prms, headers = hdrs)
    decoded_data = r.json()

    return jsonify(decoded_data)
''' --------------- --------------- '''


''' --------------- Orders methods --------------- '''
@application.route('/user/<user_id>/orders', methods = ['GET'])
def orders_info_by_user_id(user_id):
    url = 'http://127.0.0.1:8002/orders/' + user_id
    prms = {}
    hdrs = {'accept': 'application/json'}
    r = requests.get(url, params = prms, headers = hdrs)
    decoded_data = r.json()

    return jsonify(decoded_data)

@application.route('/user/<user_id>/order/<order_id>', methods = ['GET'])
def order_info(user_id, order_id):
    order_dict = {'user': user_id}

    # step.1 - get order data
    url = 'http://127.0.0.1:8002/' + order_id + '/' + user_id
    prms = {}
    hdrs = {'accept': 'application/json'}
    r = requests.get(url, params = prms, headers = hdrs)
    user_order = r.json()

    try:
        goods_list = []
        for good in user_order['goods']:
            goods_list.append(good)
        order_dict['goods'] = goods_list
    except:
        return jsonify(user_order)

    # step.2 - get billing data for that order (if can't - degrade)
    url = 'http://127.0.0.1:8003/billing/' + str(user_order['billing_id'])
    prms = {}
    hdrs = {'accept': 'application/json'}
    r = requests.get(url, params = prms, headers = hdrs)
    billing_info = r.json()

    order_dict['billing_info'] = billing_info

    return jsonify(order_dict)

@application.route('/user/<user_id>/order', methods = ['POST'])
def create_order(user_id):
    order_json = request.get_json(force=True)
    order_list = json.loads(order_json)

    # step.1 - decrement left_in_stock and calculate price (POST to goods_db, returns price)
    url = 'http://127.0.0.1:8001/goods/decrement'
    payload = order_list
    prms = json.dumps(payload)
    r = requests.post(url, json = prms)
    price = r.json()
    if 'err_msg' in price:
        return jsonify(price) #it's actually error dict

    # step.2 -  create billing (POST to billing_db, returns billing_id)
    url = 'http://127.0.0.1:8003/billing/create'
    payload = price
    prms = json.dumps(payload)
    try:
        r = requests.post(url, json = prms, timeout = 10)
    except ReadTimeout as err:
        return jsonify({'err_msg': 'billing service unavailable, rollback!'})
    bill = r.json()

    # step.3 - create order (POST to orders_db)
    url = 'http://127.0.0.1:8002/order/' + user_id
    payload = {
        'goods_list': order_list,
        'billing_id': bill['bill_id']
    }
    prms = json.dumps(payload)
    r = requests.post(url, json = prms, timeout = 10)
    order = r.json()

    return jsonify(order)

@application.route('/user/<user_id>/order/<order_id>/goods', methods = ['DELETE'])
def delete_goods_from_order(user_id, order_id):
    # step.1 - get goods info from order (GET from orders_db)
    url = 'http://127.0.0.1:8002/' + order_id + '/' + user_id
    prms = {}
    hdrs = {'accept': 'application/json'}
    r = requests.get(url, params = prms, headers = hdrs)
    user_order = r.json()
    try:
        billing_id = user_order['billing_id']
        goods_list = user_order['goods']
    except:
        return jsonify(user_order)

    # step.2 - increment left_in_stock (POST to goods_db)
    url = 'http://127.0.0.1:8001/goods/increment'
    payload = goods_list
    prms = json.dumps(payload)
    r = requests.post(url, json = prms, timeout = 10)
    print(r.text)

    # step.3 - reduce goods to [] (DELETE/POST to order_db)
    url = 'http://127.0.0.1:8002/order/' + order_id + '/user/' + user_id + '/goods'
    r = requests.delete(url, timeout = 10)
    print(r.text)

    # step.4 - update bill (PATCH to billing_db)
    url = 'http://127.0.0.1:8003/billing/' + str(billing_id)
    payload = {'total': 0}
    prms = json.dumps(payload)
    r = requests.patch(url, json = prms)
    print(r.text)

    return 'Goods removed successfully!'

@application.route('/user/<user_id>/order/<order_id>/billing', methods = ['PATCH'])
def perform_billing():
    billing_json = request.get_json(force=True)
    billing_dict = json.loads(billing_json)
    print(billing_dict)

    # step.1 - get billing_id from orders (GET from orders_db)
    url = 'http://127.0.0.1:8002/' + order_id + '/' + user_id
    prms = {}
    hdrs = {'accept': 'application/json'}
    r = requests.get(url, params = prms, headers = hdrs)
    user_order = r.json()
    try:
        billing_id = user_order['billing_id']
    except:
        return jsonify(user_order)

    # step.2 - update bill (PATCH to billing_db)
    url = 'http://127.0.0.1:8003/billing' + str(billing_id)
    payload = billing_dict
    prms = json.dumps(payload)
    r = requests.patch(url, json = prms)
    res = r.json()

    return jsonify(res)
''' --------------- --------------- '''


''' --------------- General methods --------------- '''
@application.route('/', methods = ['GET'])
def start():
	return 'Welcome!'

@application.errorhandler(404)
def page_not_found(e):
	return 'Page not found', 404
''' --------------- --------------- '''


if __name__ == '__main__':
	application.run(host = '0.0.0.0')
