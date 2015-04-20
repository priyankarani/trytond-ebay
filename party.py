# -*- coding: utf-8 -*-
"""
    party

    Party

    :copyright: (c) 2013-2015 by Openlabs Technologies & Consulting (P) Limited
    :license: GPLv3, see LICENSE for more details.
"""
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction


__all__ = ['Party', 'Address']
__metaclass__ = PoolMeta


class Party:
    "Party"
    __name__ = 'party.party'

    ebay_user_id = fields.Char(
        'eBay User ID',
        help="This is global and unique ID given to a user across whole ebay. "
        "Warning: Editing this might result in duplication of parties on next"
        " import"
    )

    @classmethod
    def __setup__(cls):
        """
        Setup the class before adding to pool
        """
        super(Party, cls).__setup__()
        cls._error_messages.update({
            'account_not_found': 'eBay Account does not exist in context',
        })

        cls._sql_constraints += [
            (
                'unique_ebay_user_id',
                'UNIQUE(ebay_user_id)',
                'eBay User ID must be unique for party'
            )
        ]

    @classmethod
    def find_or_create_using_ebay_id(cls, ebay_user_id, item_id=None):
        """
        This method tries to find the party with the ebay ID first and
        if not found it will fetch the info from ebay and create a new
        party with the data from ebay using create_using_ebay_data

        :param ebay_user_id: User ID sent by ebay
        :param item_id: This is needed when there is a relationship between
            the buyer and seller. eBay has security which allows a seller
            to fetch the information of a buyer via API only when there is
            a seller-buyer relationship between both via some item.
            If this item is not passed, then ebay would not return important
            informations like eMail etc.
        :return: Active record of record created/found
        """
        SaleChannel = Pool().get('sale.channel')

        ebay_parties = cls.search([
            ('ebay_user_id', '=', ebay_user_id),
        ])

        if ebay_parties:
            return ebay_parties[0]

        ebay_channel = SaleChannel(Transaction().context['current_channel'])
        ebay_channel.validate_ebay_channel()

        api = ebay_channel.get_ebay_trading_api()

        filters = {'UserID': ebay_user_id}
        if item_id:
            filters['ItemID'] = item_id
        user_data = api.execute('GetUser', filters).response_dict()

        return cls.create_using_ebay_data(user_data)

    @classmethod
    def create_using_ebay_data(cls, ebay_data):
        """
        Creates record of customer values sent by ebay

        :param ebay_data: Dictionary of values for customer sent by ebay
                          Ref: http://developer.ebay.com/DevZone/XML/docs/
                                  Reference/eBay/GetUser.html#Response
        :return: Active record of record created
        """
        return cls.create([{
            # eBay wont expose the name of the buyer to the seller.
            # What we get is the name in the shipping address in the sale order
            # and that we have no way to be sure if that is the address and
            # name of buyer or someone else.
            # Hence, we use UserID for both name and ebay_user_id.
            # This allows the user a flexibility to edit the name later
            'name': ebay_data['User']['UserID']['value'],
            'ebay_user_id': ebay_data['User']['UserID']['value'],
            'contact_mechanisms': [
                ('create', [{
                    'email': ebay_data['User']['Email']['value']
                }])
            ]
        }])[0]

    def add_phone_using_ebay_data(self, ebay_phone):
        """
        Add contact mechanism for party
        """
        ContactMechanism = Pool().get('party.contact_mechanism')

        # Create phone as contact mechanism
        if not ContactMechanism.search([
            ('party', '=', self.id),
            ('type', 'in', ['phone', 'mobile']),
            ('value', '=', ebay_phone),
        ]):
            ContactMechanism.create([{
                'party': self.id,
                'type': 'phone',
                'value': ebay_phone,
            }])

    def get_address_from_ebay_data(self, address_data):
        """
        Return address instance for data fetched from ebay
        """
        Address = Pool().get('party.address')
        Country = Pool().get('country.country')
        Subdivision = Pool().get('country.subdivision')

        country, = Country.search([
            ('code', '=', address_data['Country']['value'])
        ], limit=1)
        subdivision = Subdivision.search_using_ebay_state(
            address_data['StateOrProvince']['value'], country
        )

        return Address(
            party=self.id,
            name=address_data['Name']['value'],
            street=address_data['Street1']['value'],
            streetbis=(
                address_data.get('Street2') and
                address_data['Street2'].get('value') or None
            ),
            zip=address_data['PostalCode']['value'],
            city=address_data['CityName']['value'],
            country=country.id,
            subdivision=subdivision.id,
        )

    def find_or_create_address_using_ebay_data(self, address_data):
        """
        Look for the address in tryton corresponding to the address data fecthed
        from ebay.
        If found, return the same else create a new one and return that.

        :param address_data: Dictionary of address data from ebay
        :return: Active record of address created/found
        """
        ebay_address = self.get_address_from_ebay_data(address_data)

        for address in self.addresses:
            if address.is_match_found(ebay_address):
                return address

        # No match found. Create new one.
        ebay_address.save()
        return ebay_address


class Address:
    "Address"
    __name__ = 'party.address'

    def is_match_found(self, ebay_address):
        """
        Match the current address with the ebay address.
        Match all the fields of the address, i.e., streets, city, subdivision
        and country. For any deviation in any field, returns False.

        :param address_data: Dictionary of address data from ebay
                             Ref: http://developer.ebay.com/DevZone/XML/docs/
                                     Reference/eBay/GetUser.html#Response
        :return: True if address matches else False
        """
        return all([
            self.name == ebay_address.name,
            self.street == ebay_address.street,
            self.streetbis == ebay_address.streetbis,
            self.zip == ebay_address.zip,
            self.city == ebay_address.city,
            self.country == ebay_address.country,
            self.subdivision == ebay_address.subdivision,
        ])
