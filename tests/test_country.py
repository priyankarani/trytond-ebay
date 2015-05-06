# -*- coding: utf-8 -*-
"""
    test_country

    Tests country

    :copyright: (c) 2013 by Openlabs Technologies & Consulting (P) Limited
    :license: GPLv3, see LICENSE for more details.
"""
import sys
import os
DIR = os.path.abspath(os.path.normpath(
    os.path.join(
        __file__, '..', '..', '..', '..', '..', 'trytond'
    )
))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest

import trytond.tests.test_tryton
from trytond.tests.test_tryton import DB_NAME, USER, CONTEXT
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from tests.test_base import TestBase


class TestCountry(TestBase):
    """
    Tests country
    """

    def test_0010_search_state_with_valid_code(self):
        """
        Tests if state can be searched using ebay region
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            country, = self.Country.search([
                ('code', '=', 'US')
            ])
            subdivision, = self.Subdivision.search([
                ('code', '=', 'US-FL')
            ])

            self.assertEqual(
                self.Subdivision.search_using_ebay_state('FL', country),
                subdivision
            )

    def test_0015_search_state_with_valid_name(self):
        """
        Tests if state can be searched using ebay region
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            country, = self.Country.search([
                ('code', '=', 'US')
            ])
            subdivision, = self.Subdivision.search([
                ('code', '=', 'US-FL')
            ])

            self.assertEqual(
                self.Subdivision.search_using_ebay_state('FlorIda', country),
                subdivision
            )

    def test_0020_search_state_with_invalid_region(self):
        """
        Tests if error is raised for searching state with invalid region
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):
            self.setup_defaults()

            country, = self.Country.search([
                ('code', '=', 'US')
            ])

            code = 'abc'

            self.assertFalse(
                self.Subdivision.search([
                    ('code', '=', code),
                    ('country', '=', country.id)
                ])
            )

            self.assertRaises(
                UserError,
                self.Subdivision.search_using_ebay_state, code, country
            )


def suite():
    """
    Test Suite
    """
    test_suite = trytond.tests.test_tryton.suite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestCountry)
    )
    return test_suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
