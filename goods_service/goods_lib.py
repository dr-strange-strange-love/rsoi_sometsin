
from goods_service import goods_db, Good
from tinydb.operations import add, subtract

def get_goods_list(page=0, size=20):
    """ Gets chunked list of goods """
    goods_list = []
    goods = goods_db.all()
    for good in goods:
        goods_list.append({'id': good.doc_id, 'title': good['title']})

    try:
        chunked_goods_list = [goods_list[i:i+size] for i in range(0, len(goods_list), size)]
        return chunked_goods_list[page]
    except:
        return []

def get_good_info_by_id(good_id):
    """ Gets full good info """
    good_info_dict = goods_db.get(doc_id = good_id)
    return good_info_dict

def decrement_left_in_stock(goods_list):
    for good in goods_list:
        good_info = goods_db.search(Good.title == good['title'])[0]
        if good_info['left in stock'] < good['quantity']:
            raise Exception('Not enough items in stock')

    for good in goods_list:
        goods_db.update(subtract('left in stock', good['quantity']), Good.title == good['title'])

def increment_left_in_stock(goods_list):
    for good in goods_list:
        goods_db.update(add('left in stock', good['quantity']), Good.title == good['title'])

def calculate_price(goods_list):
    price = 0
    for good in goods_list:
        good_info = goods_db.search(Good.title == good['title'])[0]
        delivery = not (good['city'] in good_info['available in'])
        price_ = (good_info['price'] + delivery*good_info['delivery price']) * good['quantity']
        price = price + price_
    
    return price
