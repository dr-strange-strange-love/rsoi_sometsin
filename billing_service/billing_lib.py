
from tinydb import TinyDB, Query
from tinydb.operations import set as st

billing_db = TinyDB('/Users/amadeus/Documents/rsoi_services/warehouse/billing_db.json')
Bill = Query()

def debug_start(): # instead of using classes
    global billing_db
    billing_db.close()
    billing_db = TinyDB('/Users/amadeus/Documents/rsoi_services/warehouse_mock/billing_db.json')

def debug_finish(): # instead of using classes
    global billing_db
    billing_db.close()


def get_billing_info_by_id(billing_id):
    return billing_db.get(doc_id = billing_id)

def create_billing(price):
    bill_id = billing_db.insert({
        'total_price': price,
        'paid': 0,
        'order complete': False
    })
    return bill_id

def update_bill(billing_id, summ, complete=False):
    can_complete = False
    bill = billing_db.get(doc_id = billing_id)
    if bill['order complete']:
        return {'err_msg': 'order complete, cant perform any operation'}

    if (bill['total_price']-bill['paid']) <= summ:
        can_complete = True

    if complete and can_complete:
        billing_db.update(st('paid', bill['paid']+summ), doc_ids = [billing_id])
        billing_db.update(st('order complete', True), doc_ids = [billing_id])
    elif complete and (not can_complete):
        return {'err_msh': 'not enough funds to complrte order, aborting...'}
    else:
        billing_db.update(st('paid', bill['paid']+summ), doc_ids = [billing_id])

    return {'succ_msh': 'bill updated'}

def clean_bill(billing_id, total):
    billing_db.update(st('total_price', total), doc_ids = [billing_id])
    return {}
