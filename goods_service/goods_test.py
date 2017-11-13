
import unittest

from . import goods_lib


class GoodsLibTestCase(unittest.TestCase):
    def setUp(self):
        goods_lib.debug_start()

        goods_db = goods_lib.goods_db
        goods_db.purge()
        goods_db.insert({
                'title': 'vaz 2101 (1974)',
                'price': 6540,
                'left in stock': 1,
                'description': 'this Kopeyka would suit a young man low on budget; transmission broken',
                'bargain': True,
                'available in': ['Tula'],
                'delivery': False,
                'delivery price': 0
            })
        goods_db.insert({
                'title': 'dystopian films sale',
                'price': 100,
                'left in stock': 43,
                'description': 'try your luck with dystopian films classics such as: Brazil, A Clockwork Orange, Blade Runner, Mad Max and more',
                'bargain': False,
                'available in': ['Moscow', 'Tula', 'Sochi'],
                'delivery': True,
                'delivery price': 150
            })
        goods_db.insert({
                'title': 'cult films sale',
                'price': 90,
                'left in stock': 22,
                'description': 'try your luck with cult films classics such as: Aguirre, the Wrath of God; Akira; Holy Mountain; Taxi Driver and more',
                'bargain': False,
                'available in': ['Moscow', 'Tula', 'Sochi'],
                'delivery': True,
                'delivery price': 150
            })
        goods_db.insert({
                'title': 'iphone x',
                'price': 59990,
                'left in stock': 4,
                'description': 'iphones x 256GB confiscated from customs',
                'bargain': True,
                'available in': ['Moscow', 'Tula', 'Sochi'],
                'delivery': True,
                'delivery price': 900
            })
        goods_db.insert({
                'title': 'husband',
                'price': 9900,
                'left in stock': 1,
                'description': 'need money real bad',
                'bargain': False,
                'available in': ['Moscow'],
                'delivery': False,
                'delivery price': 0
            })
        goods_db.insert({
                'title': 'kittens',
                'price': 1500,
                'left in stock': 2,
                'description': 'siamese kittens, very cute',
                'bargain': False,
                'available in': ['Sochi'],
                'delivery': False,
                'delivery price': 0
            })

    def tearDown(self):
        goods_lib.debug_finish()

    def test_get_goods_list(self):
        expected_result = [{'id': 5, 'title': 'husband'}, {'id': 6, 'title': 'kittens'}]
        prms = {'page': 1, 'size': 4}

        goods_list_result = goods_lib.get_goods_list(prms['page'], prms['size'])
        self.assertEqual(goods_list_result, expected_result)

    def test_get_good_info_by_id(self):
        expected_result = {'title': 'iphone x', 'price': 59990, 'left in stock': 4, 'description': 'iphones x 256GB confiscated from customs', 'bargain': True, 'available in': ['Moscow', 'Tula', 'Sochi'], 'delivery': True, 'delivery price': 900}
        prms = {'good_id': 4}

        good_info_dict_result = goods_lib.get_good_info_by_id(prms['good_id'])
        self.assertEqual(good_info_dict_result, expected_result)

    def test_decrement_left_in_stock(self):
        expected_result = None
        prms = {'goods_list': [
        {
            'title': 'kittens',
            'quantity': 2,
            'city': 'Sochi'
        },
        {
            'title': 'iphone x',
            'quantity': 5,
            'city': 'St Petersburg' # delivery - true
        }]}

        try:
            goods_lib.decrement_left_in_stock(prms['goods_list'])
            self.fail()
        except Exception as err:
            self.assertEqual(str(err), 'Not enough items in stock')

    def test_calculate_price(self):
        expected_result = 307450
        prms = {'goods_list': [
        {
            'title': 'kittens',
            'quantity': 2,
            'city': 'Sochi'
        },
        {
            'title': 'iphone x',
            'quantity': 5,
            'city': 'St Petersburg' # delivery - true
        }]}

        price_result = goods_lib.calculate_price(prms['goods_list'])
        self.assertEqual(price_result, expected_result)


if __name__ == "__main__":
    unittest.main()
