# -*- coding: UTF-8 -*-
'''
    product

    :copyright: (c) 2013-2015 by Openlabs Technologies & Consulting (P) Limited
    :license: GPLv3, see LICENSE for more details.
'''
from trytond import backend
from trytond.model import fields
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from decimal import Decimal


__all__ = [
    'Product',
]
__metaclass__ = PoolMeta


class Product:
    "Product"

    __name__ = "product.product"

    ebay_item_id = fields.Char(
        'eBay Item ID',
        help="This is global and unique ID given to an item across whole ebay."
        " Warning: Editing this might result in duplicate products on next"
        " import"
    )

    @classmethod
    def validate(cls, products):
        """
        Validate sale channel
        """
        super(Product, cls).validate(products)

        for product in products:
            product.check_unique_ebay_item_id()

    def check_unique_ebay_item_id(self):
        """
        Check if ebay user id is unique for each product
        """
        if not self.ebay_item_id:
            return
        if self.search([
            ('ebay_item_id', '=', self.ebay_item_id),
            ('id', '!=', self.id)
        ]):
            self.raise_user_error('unique_ebay_item_id')

    @classmethod
    def __register__(cls, module_name):
        super(Product, cls).__register__(module_name)

        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        # Migration
        table.drop_constraint('unique_product_ebay_item_id')

    @classmethod
    def __setup__(cls):
        """
        Setup the class before adding to pool
        """
        super(Product, cls).__setup__()
        cls._error_messages.update({
            "missing_product_code": 'Product "%s" has a missing code.',
            'unique_ebay_item_id': 'eBay Item ID must be unique for product',
        })

    @classmethod
    def extract_product_values_from_ebay_data(cls, product_data):
        """
        Extract product values from the ebay data, used for
        creation of product. This method can be overwritten by
        custom modules to store extra info to a product

        :param: product_data
        :returns: Dictionary of values
        """
        SaleChannel = Pool().get('sale.channel')

        ebay_channel = SaleChannel(Transaction().context['current_channel'])
        ebay_channel.validate_ebay_channel()
        return {
            'name': product_data['Item']['Title'],
            'list_price': Decimal(
                product_data['Item']['BuyItNowPrice']['value'] or
                product_data['Item']['StartPrice']['value']
            ),
            'cost_price': Decimal(product_data['Item']['StartPrice']['value']),
            'default_uom': ebay_channel.default_uom.id,
            'salable': True,
            'sale_uom': ebay_channel.default_uom.id,
        }

    @classmethod
    def create_using_ebay_data(cls, product_data):
        """
        Create a new product with the `product_data` from ebay.

        :param product_data: Product Data from eBay
        :returns: Browse record of product created
        """
        Template = Pool().get('product.template')

        product_values = cls.extract_product_values_from_ebay_data(
            product_data
        )

        product_values.update({
            'products': [('create', [{
                'ebay_item_id': product_data['Item']['ItemID'],
                'description': product_data['Item']['Description'],
                'code':
                    product_data['Item'].get('SKU', None) and
                    product_data['Item']['SKU'] or None,
            }])],
        })

        product_template, = Template.create([product_values])

        return product_template.products[0]
