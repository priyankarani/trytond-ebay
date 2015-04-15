# -*- coding: utf-8 -*-
"""
    test_party

    Tests party

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
from trytond.tests.test_tryton import USER, DB_NAME, CONTEXT
from test_base import TestBase, load_json
from trytond.transaction import Transaction
from trytond.exceptions import UserError


class TestParty(TestBase):
    """
    Tests party
    """

    def test0010_create_party(self):
        """
        Tests if users imported from ebay is created as party in tryton
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):

            self.setup_defaults()

            ebay_data = load_json('users', 'testuser_shalabhaggarwal')

            self.assertFalse(
                self.Party.search([
                    ('name', '=', 'testuser_shalabhaggarwal')
                ])
            )

            # Create party
            party = self.Party.create_using_ebay_data(ebay_data)
            self.assert_(party)

            self.assertTrue(
                self.Party.search([
                    ('name', '=', 'testuser_shalabhaggarwal')
                ])
            )
            party, = self.Party.search([
                ('name', '=', 'testuser_shalabhaggarwal')
            ])
            self.assertTrue(len(party.contact_mechanisms), 1)
            self.assertTrue(party.contact_mechanisms[0].email)

            # Create party with same data again and it will raise error
            with self.assertRaises(UserError):
                self.Party.create_using_ebay_data(ebay_data)

    def test0030_import_addresses_from_ebay(self):
        """
        Test address import as party addresses and make sure no duplication
        is there.
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):

            self.setup_defaults()

            # Load json of address data
            ebay_data = load_json('users', 'testuser_shalabhaggarwal')
            address_data = ebay_data['User']['RegistrationAddress']

            party = self.Party.create_using_ebay_data(ebay_data)

            # Check party address before address import
            self.assertFalse(party.addresses)

            # Import address for party1 from ebay
            address1 = party.find_or_create_address_using_ebay_data(
                address_data
            )

            # Check address after import
            self.assertEqual(len(party.addresses), 1)
            self.assertEqual(address1.party, party)
            self.assertEqual(
                address1.name, address_data['Name']['value']
            )
            self.assertEqual(address1.street, address_data['Street']['value'])
            self.assertEqual(address1.zip, address_data['PostalCode']['value'])
            self.assertEqual(address1.city, address_data['CityName']['value'])
            self.assertEqual(
                address1.country.code, address_data['Country']['value']
            )
            self.assertEqual(
                address1.subdivision.name.lower(),
                address_data['StateOrProvince']['value'].lower()
            )

            # Try to import same address again. and it wont create new one
            address2 = party.find_or_create_address_using_ebay_data(
                address_data
            )
            self.assertEqual(address1, address2)
            self.assertEqual(len(party.addresses), 1)

    def test0035_import_phone_from_ebay(self):
        """
        Test address import as party addresses and make sure no duplication
        is there.
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):

            self.setup_defaults()

            # Load json of address data
            ebay_data = load_json('users', 'testuser_shalabhaggarwal')
            address_data = ebay_data['User']['RegistrationAddress']

            # Check party phone before import
            self.assertFalse(self.party.phone)
            self.assertEqual(len(self.party.contact_mechanisms), 0)

            # Add phone to party using ebay data
            self.party.add_phone_using_ebay_data(
                address_data['Phone']['value']
            )
            self.assertTrue(self.party.phone)

            self.assertEqual(len(self.party.contact_mechanisms), 1)

            # Add same phone again to party using ebay data, it wont
            # create new one
            self.party.add_phone_using_ebay_data(
                address_data['Phone']['value']
            )
            self.assertEqual(len(self.party.contact_mechanisms), 1)

    def test0040_match_address(self):
        """
        Tests if address matching works as expected
        """
        with Transaction().start(DB_NAME, USER, CONTEXT):

            self.setup_defaults()

            self.Subdivision.create([{
                'name': 'New Delhi',
                'code': 'IN-DL',
                'type': 'state',
                'country': self.country_in.id,
            }])
            self.Subdivision.create([{
                'name': 'Goa',
                'code': 'IN-GA',
                'type': 'state',
                'country': self.country_in.id,
            }])
            self.Subdivision.create([{
                'name': 'New York',
                'code': 'US-NY',
                'type': 'state',
                'country': self.country_us.id,
            }])

            # Import address for self.party from ebay
            address = self.party.find_or_create_address_using_ebay_data(
                load_json('addresses', '1a')
            )

            # Same address imported again
            self.assertTrue(
                address.is_match_found(
                    self.party.get_address_from_ebay_data(
                        load_json('addresses', '1b')
                    )
                )
            )

            # Similar with different country and state
            self.assertFalse(
                address.is_match_found(
                    self.party.get_address_from_ebay_data(
                        load_json('addresses', '1c')
                    )
                )
            )

            # Similar with different state
            self.assertFalse(
                address.is_match_found(
                    self.party.get_address_from_ebay_data(
                        load_json('addresses', '1d')
                    )
                )
            )

            # Similar with different city
            self.assertFalse(
                address.is_match_found(
                    self.party.get_address_from_ebay_data(
                        load_json('addresses', '1e')
                    )
                )
            )

            # Similar with different street
            self.assertFalse(
                address.is_match_found(
                    self.party.get_address_from_ebay_data(
                        load_json('addresses', '1f')
                    )
                )
            )


def suite():
    """
    Test Suite
    """
    test_suite = trytond.tests.test_tryton.suite()
    test_suite.addTests(
        unittest.TestLoader().loadTestsFromTestCase(TestParty)
    )
    return test_suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
