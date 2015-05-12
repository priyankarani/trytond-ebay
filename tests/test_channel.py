# -*- coding: utf-8 -*-
"""
    test_channel

    :copyright: (c) 2015 by Openlabs Technologies & Consulting (P) Limited
    :license: GPLv3, see LICENSE for more details.
"""
import unittest

import trytond.tests.test_tryton
from trytond.tests.test_tryton import USER, DB_NAME, CONTEXT
from test_base import TestBase
from trytond.transaction import Transaction
from trytond.exceptions import UserError


class TestChannel(TestBase):
    """
    Tests Channel
    """

    def test_0010_check_unique_ebay_credentials(self):
        """
        Tests if error is raised for using same ebay credentials more than one
        time
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            warehouse, = self.Location.search([
                ('type', '=', 'warehouse')
            ], limit=1)

            # Manual channel with none values
            self.SaleChannel.create([{
                'name': 'eBay Account',
                'warehouse': warehouse.id,
                'company': self.company.id,
                'source': 'manual',
                'currency': self.company.currency.id,
                'price_list': self.price_list,
                'invoice_method': 'manual',
                'shipment_method': 'manual',
                'payment_term': self.payment_term,
                'ebay_app_id': None,
                'ebay_dev_id': None,
                'ebay_cert_id': None,
                'ebay_token': None,
                'is_ebay_sandbox': False,
                'default_uom': self.uom.id,
                'default_account_expense': self.get_account_by_kind('expense'),
                'default_account_revenue': self.get_account_by_kind('revenue'),
            }])

            # Manual channel again with none values should not raise error
            self.SaleChannel.create([{
                'name': 'eBay Account',
                'warehouse': warehouse.id,
                'company': self.company.id,
                'source': 'manual',
                'currency': self.company.currency.id,
                'price_list': self.price_list,
                'invoice_method': 'manual',
                'shipment_method': 'manual',
                'payment_term': self.payment_term,
                'ebay_app_id': None,
                'ebay_dev_id': None,
                'ebay_cert_id': None,
                'ebay_token': None,
                'is_ebay_sandbox': False,
                'default_uom': self.uom.id,
                'default_account_expense': self.get_account_by_kind('expense'),
                'default_account_revenue': self.get_account_by_kind('revenue'),
            }])

            # eBay channel with credentials
            self.SaleChannel.create([{
                'name': 'eBay Account',
                'warehouse': warehouse.id,
                'company': self.company.id,
                'source': 'ebay',
                'currency': self.company.currency.id,
                'price_list': self.price_list,
                'invoice_method': 'manual',
                'shipment_method': 'manual',
                'payment_term': self.payment_term,
                'ebay_app_id': 'test_app_id',
                'ebay_dev_id': 'test_dev_id',
                'ebay_cert_id': 'test_cert_id',
                'ebay_token': 'a long test token',
                'is_ebay_sandbox': True,
                'default_uom': self.uom.id,
                'default_account_expense': self.get_account_by_kind('expense'),
                'default_account_revenue': self.get_account_by_kind('revenue'),
            }])

            # eBay channel with same credentials again should raise error
            with self.assertRaises(UserError):
                self.SaleChannel.create([{
                    'name': 'eBay Account',
                    'warehouse': warehouse.id,
                    'company': self.company.id,
                    'source': 'ebay',
                    'currency': self.company.currency.id,
                    'price_list': self.price_list,
                    'invoice_method': 'manual',
                    'shipment_method': 'manual',
                    'payment_term': self.payment_term,
                    'ebay_app_id': 'test_app_id',
                    'ebay_dev_id': 'test_dev_id',
                    'ebay_cert_id': 'test_cert_id',
                    'ebay_token': 'a long test token',
                    'is_ebay_sandbox': True,
                    'default_uom': self.uom.id,
                    'default_account_expense':
                        self.get_account_by_kind('expense'),
                    'default_account_revenue':
                        self.get_account_by_kind('revenue'),
                }])


def suite():
    """
    Test Suite
    """
    test_suite = trytond.tests.test_tryton.suite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestChannel)
    )
    return test_suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
