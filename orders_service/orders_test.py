
import unittest

from . import orders_lib


class OrdersLibTestCase(unittest.TestCase):
    def setUp(self):
        orders_lib.debug_start()

        orders_db = orders_lib.orders_db
        orders_db.purge()
        orders_db.insert({
                'user': 'Gilles',
                'goods': [
                {
                    'title': 'kittens',
                    'quantity': 2,
                    'city': 'Sochi'
                },
                {
                    'title': 'iphone x',
                    'quantity': 1,
                    'city': 'St Petersburg' # delivery - true
                }],
                'billing_id': 1
            })
        orders_db.insert({
                'user': 'Felix',
                'goods': [{
                    'title': 'kittens',
                    'quantity': 1,
                    'city': 'Sochi'
                }],
                'billing_id': 2
            })
        orders_db.insert({
                'user': 'Gilles',
                'goods': [
                {
                    'title': 'dystopian films sale',
                    'quantity': 5,
                    'city': 'Sochi'
                }],
                'billing_id': 3
            })

    def tearDown(self):
        orders_lib.debug_finish()

    def test_get_orders_info_by_user_id(self):
        expected_result = [{'order_id': 1, 'goods': ['kittens', 'iphone x']}, {'order_id': 3, 'goods': ['dystopian films sale']}]
        prms = {'user_id': 'Gilles'}

        user_orders_result = orders_lib.get_orders_info_by_user_id(prms['user_id'])
        self.assertEqual(user_orders_result, expected_result)

    def test_get_order_info(self):
        expected_result = {'err_msg': 'Invalid info: no such order'}
        prms = {'order_id': 5, 'user_id': 'Gilles'}

        order_result = orders_lib.get_order_info(prms['order_id'], prms['user_id'])
        self.assertEqual(order_result, expected_result)


if __name__ == "__main__":
    unittest.main()
