
# python modules
from flask import Flask, jsonify, request
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


@application.route('/user/<user_id>/orders', methods = ['GET', 'POST'])
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
