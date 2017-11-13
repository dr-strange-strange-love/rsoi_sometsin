
from orders_service import orders_db, Order
from tinydb.operations import set as st

def get_orders_info_by_user_id(user_id):
    user_orders = orders_db.search(Order.user == user_id)

    user_orders_list = []
    for order in user_orders:
        order_dict = {'order_id': order.doc_id}
        goods_list =[]
        for good in order['goods']:
            goods_list.append(good['title'])
        order_dict['goods'] = goods_list
        user_orders_list.append(order_dict)

    return user_orders_list

def get_order_info(order_id, user_id):
    user_has_order = False
    user_orders = orders_db.search(Order.user == user_id)
    for order in user_orders:
        if order_id == order.doc_id:
            user_has_order = True
            
    if not user_has_order:
        return {'err_msg': 'Invalid info: no such order'}

    return orders_db.get(doc_id = order_id)

def create_order(user_id, goods_list, billing_id):
    order_id = orders_db.insert({
        'user': user_id,
        'goods': goods_list,
        'billing_id': billing_id
    })
    return order_id

def delete_goods(order_id):
    orders_db.update(st('goods', []), doc_ids = [order_id])
