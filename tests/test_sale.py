# -*- coding: utf-8 -*-
"""
    test_sale

    Tests sale

    :copyright: (c) 2013-2015 by Openlabs Technologies & Consulting (P) Limited
    :license: GPLv3, see LICENSE for more details.
"""
import os
import sys
import unittest
DIR = os.path.abspath(os.path.normpath(
    os.path.join(
        __file__,
        '..', '..', '..', '..', '..', 'trytond'
    )
))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import trytond.tests.test_tryton
from trytond.tests.test_tryton import POOL, USER, DB_NAME, CONTEXT
from test_base import TestBase, load_json
from trytond.transaction import Transaction


class TestSale(TestBase):
    """
    Tests import of sale order
    """

    def test_0010_import_sale_order(self):
        """
        Tests import of sale order using ebay data with ebay state as new
        """
        Sale = POOL.get('sale.sale')
        Party = POOL.get('party.party')
        Product = POOL.get('product.product')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            with Transaction().set_context({
                'current_channel': self.ebay_channel.id,
                'company': self.company
            }):

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                order_data = load_json(
                    'orders', '110122281466-0'
                )['OrderArray']['Order']

                Party.create_using_ebay_data(
                    load_json('users', 'testuser_shalabhopenlabs')
                )

                Product.create_using_ebay_data(
                    load_json('products', '110122281466')
                )

                order = Sale.create_using_ebay_data(order_data)

                self.assertEqual(order.state, 'confirmed')

                orders = Sale.search([])
                self.assertEqual(len(orders), 1)

                # Item lines + shipping line should be equal to lines on tryton
                self.assertEqual(len(order.lines), 2)

    def test_0020_import_sale_order_with_exception(self):
        """
        Tests if exception is created for sale order when order total mismatch
        """
        Sale = POOL.get('sale.sale')
        Party = POOL.get('party.party')
        Product = POOL.get('product.product')
        ChannelException = POOL.get('channel.exception')

        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            with Transaction().set_context({
                'current_channel': self.ebay_channel.id,
                'company': self.company
            }):

                orders = Sale.search([])
                self.assertEqual(len(orders), 0)

                order_data = load_json(
                    'orders', '110122281466-0'
                )['OrderArray']['Order']

                Party.create_using_ebay_data(
                    load_json('users', 'testuser_shalabhopenlabs')
                )

                Product.create_using_ebay_data(
                    load_json('products', '110122281466')
                )

                self.assertEqual(order_data['Total']['value'], '4.5')

                self.assertFalse(ChannelException.search([]))

                # Lets Change order total to make it raise exception
                order_data['Total']['value'] = '8.5'

                order = Sale.create_using_ebay_data(order_data)

                self.assertTrue(ChannelException.search([]))

                self.assertTrue(order.has_channel_exception)

                self.assertNotEqual(order.state, 'confirmed')

                orders = Sale.search([])
                self.assertEqual(len(orders), 1)

                # Item lines + shipping line should be equal to lines on tryton
                self.assertEqual(len(order.lines), 2)


def suite():
    """
    Test Suite
    """
    test_suite = trytond.tests.test_tryton.suite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestSale)
    )
    return test_suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
