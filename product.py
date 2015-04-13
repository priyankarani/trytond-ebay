# -*- coding: UTF-8 -*-
'''
    product

    :copyright: (c) 2013-2015 by Openlabs Technologies & Consulting (P) Limited
    :license: GPLv3, see LICENSE for more details.
'''
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
    def __setup__(cls):
        """
        Setup the class before adding to pool
        """
        super(Product, cls).__setup__()
        cls._error_messages.update({
            "invalid_product": 'Product with eBay Item ID "%s" already exists',
            "missing_product_code": 'Product "%s" has a missing code.',
        })

    @classmethod
    def validate(cls, products):
        super(Product, cls).validate(products)
        for product in products:
            product.check_ebay_item_id()

    def check_ebay_item_id(self):
        "Check the eBay Item ID for duplicates"
        if self.ebay_item_id and len(
            self.search([('ebay_item_id', '=', self.ebay_item_id)])
        ) > 1:
            self.raise_user_error('invalid_product', (self.ebay_item_id,))

    @classmethod
    def find_or_create_using_ebay_id(cls, ebay_id):
        """
        Find or create a product using ebay ID. This method looks
        for an existing product using the ebay ID provided. If found, it
        returns the product found, else creates a new one and returns that

        :param ebay_id: Product ID from eBay
        :returns: Active record of Product Created
        """
        SellerAccount = Pool().get('ebay.seller.account')

        products = cls.search([('ebay_item_id', '=', ebay_id)])

        if products:
            return products[0]

        # if product is not found get the info from ebay and
        # delegate to create_using_ebay_data
        seller_account = SellerAccount(
            Transaction().context.get('ebay_seller_account')
        )
        api = seller_account.get_trading_api()

        product_data = api.execute(
            'GetItem', {'ItemID': ebay_id, 'DetailLevel': 'ReturnAll'}
        ).response_dict()

        return cls.create_using_ebay_data(product_data)

    @classmethod
    def extract_product_values_from_ebay_data(cls, product_data):
        """
        Extract product values from the ebay data, used for
        creation of product. This method can be overwritten by
        custom modules to store extra info to a product

        :param: product_data
        :returns: Dictionary of values
        """
        SellerAccount = Pool().get('ebay.seller.account')

        account = SellerAccount(
            Transaction().context.get('ebay_seller_account')
        )
        return {
            'name': product_data['Item']['Title']['value'],
            'list_price': Decimal(
                product_data['Item']['BuyItNowPrice']['value'] or
                product_data['Item']['StartPrice']['value']
            ),
            'cost_price': Decimal(product_data['Item']['StartPrice']['value']),
            'default_uom': account.default_uom.id,
            'salable': True,
            'sale_uom': account.default_uom.id,
            'account_expense': account.default_account_expense.id,
            'account_revenue': account.default_account_revenue.id,
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
                'ebay_item_id': product_data['Item']['ItemID']['value'],
                'description': product_data['Item']['Description']['value'],
                'code':
                    product_data['Item'].get('SKU', None) and
                    product_data['Item']['SKU']['value'],
            }])],
        })

        product_template, = Template.create([product_values])

        return product_template.products[0]
