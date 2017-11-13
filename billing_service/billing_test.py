
import unittest

from . import billing_lib


class BillingLibTestCase(unittest.TestCase):
    def setUp(self):
        billing_lib.debug_start()

        billing_db = billing_lib.billing_db
        billing_db.purge()
        billing_db.insert({
                'total_price': 63890,
                'paid': 30445,
                'order complete': False
            })
        billing_db.insert({
                'total_price': 1500,
                'paid': 0,
                'order complete': False
            })
        billing_db.insert({
                'total_price': 600,
                'paid': 0,
                'order complete': False
            })

    def tearDown(self):
        billing_lib.debug_finish()

    def test_get_billing_info_by_id(self):
        expected_result = {'paid': 0, 'order complete': False, 'total_price': 1500}
        prms = {'billing_id': 2}

        billing_info_result = billing_lib.get_billing_info_by_id(prms['billing_id'])
        self.assertEqual(billing_info_result, expected_result)

    def test_create_billing(self):
        expected_result = 4
        prms = {'price': 9000}

        billing_id_result = billing_lib.create_billing(prms['price'])
        self.assertEqual(billing_id_result, expected_result)

    def test_update_bill(self):
        expected_result = {'err_msh': 'not enough funds to complrte order, aborting...'}
        prms = {'billing_id': 1, 'sum': 3000, 'complete': True}

        result = billing_lib.update_bill(prms['billing_id'], prms['sum'], prms['complete'])
        self.assertEqual(result, expected_result)


if __name__ == "__main__":
    unittest.main()
