# -*- coding: utf-8 -*-
"""
    sale

    Sale

    :copyright: (c) 2013-2015 by Openlabs Technologies & Consulting (P) Limited
    :license: GPLv3, see LICENSE for more details.
"""
import dateutil.parser
from decimal import Decimal

from trytond.model import fields
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool


__all__ = ['Sale']

__metaclass__ = PoolMeta


class Sale:
    "Sale"
    __name__ = 'sale.sale'

    ebay_order_id = fields.Char(
        'eBay Order ID',
        help="This is global and unique ID given to an order across whole ebay"
        " Warning: Editing this might result in duplicate orders on next"
        " import"
    )

    @classmethod
    def __setup__(cls):
        """
        Setup the class before adding to pool
        """
        super(Sale, cls).__setup__()
        cls._error_messages.update({
            "invalid_sale": 'Sale with eBay Order ID "%s" already exists',
        })

    @classmethod
    def validate(cls, sales):
        super(Sale, cls).validate(sales)
        for sale in sales:
            sale.check_ebay_order_id()

    def check_ebay_order_id(self):
        "Check the eBay Order ID for duplicates"
        if self.ebay_order_id and self.search([
            ('ebay_order_id', '=', self.ebay_order_id),
            ('id', '!=', self.id),
        ]):
            self.raise_user_error('invalid_sale', (self.ebay_order_id,))

    @classmethod
    def find_or_create_using_ebay_id(cls, order_id):
        """
        This method tries to find the sale with the order ID
        first and if not found it will fetch the info from ebay and
        create a new sale with the data from ebay using
        create_using_ebay_data

        :param order_id: Order ID from ebay
        :type order_id: string
        :returns: Active record of sale order created/found
        """
        SaleChannel = Pool().get('sale.channel')

        sales = cls.search([
            ('ebay_order_id', '=', order_id),
        ])
        if sales:
            return sales[0]

        ebay_channel = SaleChannel(Transaction().context['current_channel'])
        ebay_channel.validate_ebay_channel()

        api = ebay_channel.get_ebay_trading_api()

        order_data = api.execute(
            'GetOrders', {
                'OrderIDArray': {
                    'OrderID': order_id
                }, 'DetailLevel': 'ReturnAll'
            }
        ).dict()

        return cls.create_using_ebay_data(order_data['OrderArray']['Order'])

    @classmethod
    def create_using_ebay_data(cls, order_data):
        """
        Create a sale from ebay data

        :param order_data: Order data from ebay
                           Ref: http://developer.ebay.com/DevZone/XML/docs/\
                                   Reference/eBay/GetOrders.html#Response
        :return: Active record of record created
        """
        Party = Pool().get('party.party')
        Currency = Pool().get('currency.currency')
        SaleChannel = Pool().get('sale.channel')
        Uom = Pool().get('product.uom')
        ChannelException = Pool().get('channel.exception')

        ebay_channel = SaleChannel(Transaction().context['current_channel'])

        ebay_channel.validate_ebay_channel()

        currency, = Currency.search([
            ('code', '=', order_data['Total']['_currencyID'])
        ], limit=1)

        # Transaction is similar to order lines
        # In the if..else below we fetch the first item from the array to
        # get the item which will be used to establish a relationship
        # between seller and buyer.
        transaction = order_data['TransactionArray']['Transaction']
        if isinstance(transaction, dict):
            # If its a single line order, then the array will be dict
            item = transaction
        else:
            # In case of multi line orders, the transaction array will be
            # a list of dictionaries
            item = transaction[0]

        # Get an item ID so that ebay can establish a relationship between
        # seller and buyer.
        # eBay has a security feature which allows a seller
        # to fetch the information of a buyer via API only when there is
        # a seller-buyer relationship between both via some item.
        # If this item is not passed, then ebay would not return important
        # informations like eMail etc.
        item_id = item['Item']['ItemID']
        party = Party.find_or_create_using_ebay_id(
            order_data['BuyerUserID'], item_id=item_id
        )

        party.add_phone_using_ebay_data(
            order_data['ShippingAddress']['Phone']
        )

        party_invoice_address = party_shipping_address = \
            party.find_or_create_address_using_ebay_data(
                order_data['ShippingAddress']
            )
        unit, = Uom.search([('name', '=', 'Unit')])

        sale_data = {
            'reference': order_data['OrderID'],
            'sale_date': dateutil.parser.parse(
                order_data['CreatedTime'].split()[0]
            ).date(),
            'party': party.id,
            'currency': currency.id,
            'invoice_address': party_invoice_address.id,
            'shipment_address': party_shipping_address.id,
            'ebay_order_id': order_data['OrderID'],
            'lines': cls.get_item_line_data_using_ebay_data(order_data),
            'channel': ebay_channel.id,
        }

        sale_data['lines'].append(
            cls.get_shipping_line_data_using_ebay_data(order_data)
        )

        # TODO: Handle Discounts
        # TODO: Handle Taxes

        sale, = cls.create([sale_data])

        # Create channel exception if order total does not match
        if sale.total_amount != Decimal(order_data['Total']['value']):
            ChannelException.create([{
                'origin': '%s,%s' % (sale.__name__, sale.id),
                'log': 'Order total does not match.',
                'channel': sale.channel.id,
            }])

            return sale

        # We import only completed orders, so we can confirm them all
        cls.quote([sale])
        cls.confirm([sale])

        # TODO: Process the order for invoice as the payment info is received

        return sale

    @classmethod
    def get_item_line_data_using_ebay_data(cls, order_data):
        """
        Make data for an item line from the ebay data.

        :param order_data: Order Data from ebay
        :return: List of data of order lines in required format
        """
        Uom = Pool().get('product.uom')
        SaleChannel = Pool().get('sale.channel')

        unit, = Uom.search([('name', '=', 'Unit')])

        ebay_channel = SaleChannel(Transaction().context['current_channel'])

        ebay_channel.validate_ebay_channel()

        line_data = []
        transaction = order_data['TransactionArray']['Transaction']
        if isinstance(transaction, dict):
            # If its a single line order, then the transaction will be dict
            items = [transaction]
        else:
            # In case of multi line orders, the transaction will be
            # a list of dictionaries
            items = transaction
        for item in items:
            values = {
                'description': item['Item']['Title'],
                'unit_price': Decimal(
                    item['TransactionPrice']['value']
                ),
                'unit': unit.id,
                'quantity': Decimal(
                    item['QuantityPurchased']
                ),
                'product': ebay_channel.import_product(
                    item['Item']['ItemID'],
                ).id
            }
            line_data.append(('create', [values]))

        return line_data

    @classmethod
    def get_shipping_line_data_using_ebay_data(cls, order_data):
        """
        Create a shipping line for the given sale using ebay data

        :param order_data: Order Data from ebay
        """
        Uom = Pool().get('product.uom')

        unit, = Uom.search([('name', '=', 'Unit')])

        return ('create', [{
            'description': 'eBay Shipping and Handling',
            'unit_price': Decimal(
                order_data['ShippingServiceSelected'].get(
                    'ShippingServiceCost', 0.00
                ) and order_data[
                    'ShippingServiceSelected'
                ]['ShippingServiceCost']['value']
            ),
            'unit': unit.id,
            'note': order_data['ShippingServiceSelected'].get(
                'ShippingService', None
            ) and order_data[
                'ShippingServiceSelected']['ShippingService'],
            'quantity': 1,
        }])
