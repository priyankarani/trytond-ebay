# -*- coding: utf-8 -*-
"""
    channel.py

    :copyright: (c) 2015 by Openlabs Technologies & Consulting (P) Limited
    :license: GPLv3, see LICENSE for more details.
"""
import dateutil.parser
from datetime import datetime
from dateutil.relativedelta import relativedelta

from ebaysdk.trading import Connection as trading
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, Button
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval


__all__ = [
    'SaleChannel', 'CheckEbayTokenStatusView', 'CheckEbayTokenStatus',
]
__metaclass__ = PoolMeta

EBAY_STATES = {
    'required': Eval('source') == 'ebay',
    'invisible': ~(Eval('source') == 'ebay')
}


class SaleChannel:
    "Sale Channel"
    __name__ = 'sale.channel'

    ebay_app_id = fields.Char(
        'eBay AppID', states=EBAY_STATES, depends=['source'],
        help="APP ID of the account - provided by eBay",
    )

    ebay_dev_id = fields.Char(
        'eBay DevID', help="Dev ID of account - provided by eBay",
        states=EBAY_STATES, depends=['source']
    )

    ebay_cert_id = fields.Char(
        'eBay CertID', help="Cert ID of account - provided by eBay",
        states=EBAY_STATES, depends=['source']
    )

    ebay_token = fields.Text(
        'eBay Token', states=EBAY_STATES, depends=['source'],
        help="Token for this user account - to be generated from eBay "
        "developer home. If it expirees, then a new one should be generated",
    )

    is_ebay_sandbox = fields.Boolean(
        'Is eBay sandbox ?',
        help="Select this if this account is a sandbox account",
        states={
            'invisible': ~(Eval('source') == 'ebay')
        }, depends=['source']
    )

    last_ebay_order_import_time = fields.DateTime(
        'Last eBay Order Import Time', states=EBAY_STATES, depends=['source']
    )

    @staticmethod
    def default_last_ebay_order_import_time():
        """
        Set default last order import time
        """
        return datetime.utcnow() - relativedelta(days=30)

    @classmethod
    def get_source(cls):
        """
        Get the source
        """
        sources = super(SaleChannel, cls).get_source()

        sources.append(('ebay', 'eBay'))

        return sources

    @classmethod
    def __setup__(cls):
        """
        Setup the class before adding to pool
        """
        super(SaleChannel, cls).__setup__()
        cls._error_messages.update({
            "no_orders":
                'No new orders have been placed on eBay for this '
                'Channel after %s',
            "invalid_channel": "Current channel does not belong to eBay!",
            'same_ebay_credentials':
                'All the ebay credentials should be unique.'
        })
        cls._buttons.update({
            'check_ebay_token_status': {},
        })

    @classmethod
    def validate(cls, channels):
        """
        Validate sale channel
        """
        super(SaleChannel, cls).validate(channels)

        for channel in channels:
            channel.check_unique_app_dev_cert_token()

    def check_unique_app_dev_cert_token(self):
        """
        App ID, Dev ID, Cert ID and Token must be unique
        """
        if not all([
            self.ebay_app_id, self.ebay_dev_id,
            self.ebay_cert_id, self.ebay_token
        ]):
            return
        if self.search([
            ('ebay_app_id', '=', self.ebay_app_id),
            ('ebay_dev_id', '=', self.ebay_dev_id),
            ('ebay_cert_id', '=', self.ebay_cert_id),
            ('ebay_token', '=', self.ebay_token),
            ('id', '!=', self.id)
        ]):
            self.raise_user_error("same_ebay_credentials")

    def get_ebay_trading_api(self):
        """Create an instance of ebay trading api

        :return: ebay trading api instance
        """
        domain = 'api.sandbox.ebay.com' if \
            self.is_ebay_sandbox else 'api.ebay.com'
        return trading(
            appid=self.ebay_app_id,
            certid=self.ebay_cert_id,
            devid=self.ebay_dev_id,
            token=self.ebay_token,
            domain=domain,
            config_file=None,
        )

    @classmethod
    @ModelView.button_action('ebay.wizard_check_ebay_token_status')
    def check_ebay_token_status(cls, channels):
        """
        Check the status of token and display to user
        """
        pass

    def validate_ebay_channel(self):
        """
        Check if current channel belongs to ebay
        """
        if self.source != 'ebay':
            self.raise_user_error("invalid_channel")

    @classmethod
    def import_ebay_orders_using_cron(cls):
        """
        Cron method to import ebay orders
        """
        channels = cls.search([('source', '=', 'ebay')])

        for channel in channels:
            channel.import_orders()

    def import_orders(self):
        """
        Downstream implementation of channel.import_orders
        :return: List of active record of sale imported
        """
        if self.source != 'ebay':
            return super(SaleChannel, self).import_orders()

        self.validate_ebay_channel()

        sales = []
        api = self.get_ebay_trading_api()
        now = datetime.utcnow()

        last_import_time = self.last_ebay_order_import_time

        # Update current time for order update
        self.write([self], {'last_ebay_order_import_time': now})

        response = api.execute(
            'GetOrders', {
                'CreateTimeFrom': last_import_time,
                'CreateTimeTo': now
            }
        ).dict()
        if not response.get('OrderArray'):
            self.raise_user_error(
                'no_orders', (last_import_time, )
            )

        # Orders are returned as dictionary for single order and as
        # list for multiple orders.
        # Convert to list if dictionary is returned
        if isinstance(response['OrderArray']['Order'], dict):
            orders = [response['OrderArray']['Order']]
        else:
            orders = response['OrderArray']['Order']

        with Transaction().set_context({'current_channel': self.id}):
            for order_data in orders:
                sales.append(self.import_order(order_data))

        return sales

    def import_order(self, order_data):
        "Downstream implementation of channel.import_order from sale channel"
        if self.source != 'ebay':
            return super(SaleChannel, self).import_order(order_data)

        Sale = Pool().get('sale.sale')

        sales = Sale.search([
            ('ebay_order_id', '=', order_data['OrderID']['value']),
        ])
        if sales:
            return sales[0]

        return Sale.create_using_ebay_data(order_data)


class CheckEbayTokenStatusView(ModelView):
    "Check Token Status View"
    __name__ = 'channel.ebay.check_token_status.view'

    status = fields.Char('Status', readonly=True)
    expiry_date = fields.DateTime('Expiry Date', readonly=True)


class CheckEbayTokenStatus(Wizard):
    """
    Check Token Status Wizard

    Check token status for the current ebay channel's token.
    """
    __name__ = 'channel.ebay.check_token_status'

    start = StateView(
        'channel.ebay.check_token_status.view',
        'ebay.check_ebay_token_status_view_form',
        [
            Button('OK', 'end', 'tryton-ok'),
        ]
    )

    def default_start(self, data):
        """
        Check the status of the token of the ebay channel

        :param data: Wizard data
        """
        SaleChannel = Pool().get('sale.channel')

        ebay_channel = SaleChannel(Transaction().context.get('active_id'))

        api = ebay_channel.get_ebay_trading_api()
        response = api.execute('GetTokenStatus').dict()

        return {
            'status': response['TokenStatus']['Status'],
            'expiry_date': dateutil.parser.parse(
                response['TokenStatus']['ExpirationTime']
            ),
        }
