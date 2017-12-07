
# python modules
from flask import Flask, jsonify, request, make_response
from flask_jwt import JWT, jwt_required, current_identity
from werkzeug.security import safe_str_cmp
import json

application = Flask(__name__)

# local modules
import orders_lib

if application.debug is not True:
    import logging
    from logging.handlers import RotatingFileHandler
    
    handler = RotatingFileHandler("orders_service.log", maxBytes=100000000, backupCount=5)
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter("%(asctime)s - %(module)s - %(lineno)d - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    application.logger.addHandler(handler)


''' --------------- JWT Oauth2 setup --------------- '''
application.config['SECRET_KEY'] = 'hdba763_sjahd&^bdgHsS'
authorization_code = 'suydgswe'

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


@application.route('/user/<user_id>/orders', methods = ['GET', 'POST'])
@jwt_required()
def get_create_orders(user_id):
    if request.method == 'GET': # get orders info
        user_orders_list = orders_lib.get_orders_info_by_user_id(user_id)
        return jsonify(user_orders_list)
    else: # create order
        order_json = request.get_json(force=True)
        order_dict = json.loads(order_json)

        order_id = orders_lib.create_order(user_id, order_dict['goods_list'], order_dict['billing_id'])

        return jsonify({'order_id': order_id})

@application.route('/user/<user_id>/orders/<order_id>', methods = ['GET'])
@jwt_required()
def order_info(user_id, order_id):
    user_order = orders_lib.get_order_info(int(order_id), user_id)
    return jsonify(user_order)

@application.route('/orders/<order_id>/goods', methods = ['DELETE'])
def delete_goods_from_order(order_id):
    orders_lib.delete_goods(int(order_id))
    return jsonify({'succ_msg': 'Goods removed successfully!'})


@application.route('/', methods = ['GET'])
def start():
    return jsonify({'succ_msg': 'Welcome!'}), 200

@application.errorhandler(404)
def page_not_found(e):
    return jsonify({'err_msg': 'Page not found'}), 404


if __name__ == '__main__':
    application.run(host = '0.0.0.0')
