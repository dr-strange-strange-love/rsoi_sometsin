
# python modules
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, make_response
from flask_jwt import JWT, jwt_required, current_identity
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token,
    jwt_refresh_token_required, create_refresh_token,
    get_jwt_identity, set_access_cookies,
    set_refresh_cookies, unset_jwt_cookies
)
from tinydb import TinyDB, Query
import base64
import json
import jwt
import pickle
import redis
import uuid

# local modules
import session_lib

application = Flask(__name__)
try:
    users_db = TinyDB('/Users/amadeus/Documents/rsoi_services/warehouse/users_db.json')
except:
    users_db = TinyDB('/srv/www/rsoi_services/warehouse/users_db.json')
User = Query()

rds = redis.Redis('127.0.0.1')

if application.debug is not True:
    import logging
    from logging.handlers import RotatingFileHandler
    
    handler = RotatingFileHandler("session_service.log", maxBytes=100000000, backupCount=5)
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter("%(asctime)s - %(module)s - %(lineno)d - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    application.logger.addHandler(handler)


# Set redis value
def set_value(rds, key, value):
    rds.set(key, pickle.dumps(value), ex=96*60*60)
# Get redis value
def get_value(rds, key):
    pickled_value = rds.get(key)
    if pickled_value is None:
        return None
    return pickle.loads(pickled_value)


@application.route('/user/<user_id>/tokens', methods = ['GET'])
def order_info(user_id):
    user_tokens = get_value(rds, str(user_id))
    if not user_tokens:
        return jsonify({}), 200
    return jsonify(user_tokens), 200

@application.route('/token_simple', methods = ['POST'])
def token_simple():
    user_json = request.get_json(force=True)
    user_dict = json.loads(user_json)
    identity = user_dict['identity']
    authorization_basic = request.headers['Authorization']

    # generate jwt token based on identity, time and app_secret
    encoded_jwt = jwt.encode(
        {
            'identity': identity,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow()+timedelta(minutes=30),
            'nbf': datetime.utcnow(),
            'jti': uuid.uuid4().hex,
            'type': 'access',
            'fresh': False
        },
        authorization_basic.split()[1],
        algorithm='HS256')
    print(encoded_jwt)

    resp = make_response(jsonify({'succ_msg': 'token created!'}))
    resp.headers['Cookie'] = encoded_jwt
    return resp, 200

@application.route('/token', methods = ['POST'])
def token():
    user_json = request.get_json(force=True)
    user_dict = json.loads(user_json)
    identity = user_dict['identity']
    print(identity)
    client_id = user_dict['client_id']
    print(client_id)
    authorization_basic = request.headers['Authorization']
    print(authorization_basic)

    # generate jwt token based on identity, time and app_secret
    encoded_jwt = jwt.encode(
        {
            'identity': identity,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow()+timedelta(minutes=1),
            'nbf': datetime.utcnow(),
        },
        authorization_basic.split()[1],
        algorithm='HS256')
    print(encoded_jwt)

    # update redis
    user_tokens = get_value(rds, identity)
    print(user_tokens)
    if not user_tokens:
        user_tokens = dict()
    if not user_tokens.get(client_id, None):
        user_tokens[client_id + '_refresh'] = base64.b64encode(identity.encode('ascii')).decode("utf-8")
    user_tokens[client_id] = encoded_jwt.decode("utf-8")
    set_value(rds, identity, user_tokens)

    return jsonify({'succ_msg': 'token created!'}), 200

@application.route('/refresh_token', methods = ['POST'])
def refresh_token():
    user_json = request.get_json(force=True)
    user_dict = json.loads(user_json)
    refresh_token = user_dict['refresh_token']
    print(refresh_token)
    client_id = user_dict['client_id']
    print(client_id)
    authorization_basic = request.headers['Authorization']
    print(authorization_basic)

    identity = base64.b64decode(refresh_token.encode('ascii')).decode('utf-8')
    print(identity)

    # generate new jwt token based on identity, time and app_secret
    encoded_jwt = jwt.encode(
        {
            'identity': identity,
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow()+timedelta(minutes=1),
            'nbf': datetime.utcnow(),
        },
        authorization_basic.split()[1],
        algorithm='HS256')
    print(encoded_jwt)

    # update token
    user_tokens = get_value(rds, identity)
    user_tokens[client_id] = encoded_jwt.decode("utf-8")
    set_value(rds, identity, user_tokens)

    return jsonify({'succ_msg': 'token refreshed!'}), 200


''' --------------- General methods --------------- '''
@application.route('/', methods = ['GET'])
def start():
    return jsonify({'succ_msg': 'Welcome!'}), 200

@application.errorhandler(404)
def page_not_found(e):
    return jsonify({'err_msg': 'Page not found'}), 404
''' --------------- --------------- '''


if __name__ == '__main__':
    application.run(host = '0.0.0.0')
