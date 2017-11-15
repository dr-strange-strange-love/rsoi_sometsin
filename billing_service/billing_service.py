
# python modules
from flask import Flask, jsonify, request
import json

application = Flask(__name__)

# local modules
import billing_lib

if application.debug is not True:
    import logging
    from logging.handlers import RotatingFileHandler
    
    handler = RotatingFileHandler("billing_service.log", maxBytes=100000000, backupCount=5)
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter("%(asctime)s - %(module)s - %(lineno)d - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    application.logger.addHandler(handler)


@application.route('/billing/<billing_id>', methods = ['GET', 'PATCH'])
def billing_info_by_id(billing_id):
    if request.method == 'GET':
        billing_info = billing_lib.get_billing_info_by_id(int(billing_id))
        return jsonify(billing_info)
    else:
        billing_json = request.get_json(force=True)
        billing_dict = json.loads(billing_json)
        print(billing_dict)

        if 'total' in billing_dict:
            res = billing_lib.clean_bill(int(billing_id), int(billing_dict['total']))
        else:
            res = billing_lib.update_bill(int(billing_id), int(billing_dict['sum']), billing_dict['complete'])

        return jsonify(res)

@application.route('/billing/create', methods = ['POST'])
def create_bill():
    bill_json = request.get_json(force=True)
    bill_dict = json.loads(bill_json)

    bill_id = billing_lib.create_billing(int(bill_dict['price']))

    return jsonify({'bill_id': bill_id})


@application.route('/', methods = ['GET'])
def start():
    return 'Welcome!'

@application.errorhandler(404)
def page_not_found(e):
    return 'Page not found', 404


if __name__ == '__main__':
    application.run(host = '0.0.0.0')
