
from billing_service import billing_db, Bill
from tinydb.operations import set as st

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
    print(bill)
    if bill['order complete']:
        return {'err_msg': 'order complete, cant perform any operation'}

    if (bill['total_price']-bill['paid']) <= summ:
        can_complete = True
        print(can_complete)

    if complete and can_complete:
        billing_db.update(st('paid', bill['paid']+summ), doc_ids = [billing_id])
        billing_db.update(st('order complete', True), doc_ids = [billing_id])
    elif complete and (not can_complete):
        return {'err_msh': 'not enough funds to complrte order, aborting...'}
    else:
        billing_db.update(st('paid', bill['paid']+summ), doc_ids = [billing_id])

    return {}

def clean_bill(billing_id, total):
    billing_db.update(st('total_price', total), doc_ids = [billing_id])
    return {}
