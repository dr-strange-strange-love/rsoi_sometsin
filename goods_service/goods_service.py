
# python modules
from flask import Flask, jsonify, request
import json

application = Flask(__name__)

# local modules
import goods_lib

if application.debug is not True:
    import logging
    from logging.handlers import RotatingFileHandler
    
    handler = RotatingFileHandler("goods_service.log", maxBytes=100000000, backupCount=5)
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter("%(asctime)s - %(module)s - %(lineno)d - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    application.logger.addHandler(handler)


@application.route('/goods', methods = ['GET'])
def goods_list():
    page = request.args.get('page')
    size = request.args.get('size')

    chunked_list = goods_lib.get_goods_list(int(page)-1, int(size))

    return jsonify(chunked_list)

@application.route('/goods/<good_id>', methods = ['GET'])
def good_info_by_id(good_id):
    return jsonify(goods_lib.get_good_info_by_id(int(good_id)))

@application.route('/goods/decrement', methods = ['POST'])
def manipulate_goods():
    goods_json = request.get_json(force=True)
    goods_list = json.loads(goods_json)

    # decrement left_in_stock
    try:
        goods_lib.decrement_left_in_stock(goods_list)
    except:
        return jsonify({'err_msg': 'Not enough items in stock'})

    # calculate price
    price = goods_lib.calculate_price(goods_list)
    print(price)

    return jsonify({'price': int(price)})

@application.route('/goods/increment', methods = ['POST'])
def manipulate_goods_increment():
    goods_json = request.get_json(force=True)
    goods_list = json.loads(goods_json)

    goods_lib.increment_left_in_stock(goods_list)

    return 'Increment successfull!'


@application.route('/', methods = ['GET'])
def start():
    return 'Welcome!'

@application.errorhandler(404)
def page_not_found(e):
    return 'Page not found', 404


if __name__ == '__main__':
    application.run(host = '0.0.0.0')
