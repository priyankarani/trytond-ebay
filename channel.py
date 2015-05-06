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
from trytond.wizard import Wizard, StateView, Button, StateAction
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, PYSONEncoder


__all__ = [
    'SaleChannel', 'CheckEbayTokenStatusView', 'CheckEbayTokenStatus',
    'ImportEbayOrders', 'ImportEbayOrdersView'
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
        states=EBAY_STATES, depends=['source']
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
        cls._sql_constraints += [
            (
                'unique_app_dev_cert_token',
                'UNIQUE(ebay_app_id, ebay_dev_id, ebay_cert_id, ebay_token)',
                'All the ebay credentials should be unique.'
            )
        ]
        cls._error_messages.update({
            "no_orders":
                'No new orders have been placed on eBay for this '
                'Channel after %s',
            "invalid_channel": "Current channel does not belong to eBay!"
        })
        cls._buttons.update({
            'check_ebay_token_status': {},
            'import_ebay_orders_button': {},
        })

    def get_ebay_trading_api(self):
        """Create an instance of ebay trading api

        :return: ebay trading api instance
        """
        domain = 'api.sandbox.ebay.com' if self.is_ebay_sandbox else 'api.ebay.com'
        return trading(
            appid=self.ebay_app_id,
            certid=self.ebay_cert_id,
            devid=self.ebay_dev_id,
            token=self.ebay_token,
            domain=domain
        )

    @classmethod
    @ModelView.button_action('ebay.wizard_check_ebay_token_status')
    def check_ebay_token_status(cls, channels):
        """
        Check the status of token and display to user
        """
        pass

    @classmethod
    @ModelView.button_action('ebay.wizard_import_ebay_orders')
    def import_ebay_orders_button(cls, channels):
        """
        Import orders for current account
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
            channel.import_ebay_orders()

    def import_ebay_orders(self):
        """
        Imports orders for current channel

        """
        Sale = Pool().get('sale.sale')

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
                sales.append(Sale.create_using_ebay_data(order_data))

        return sales


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


class ImportEbayOrdersView(ModelView):
    "Import Orders View"
    __name__ = 'channel.ebay.import_orders.view'

    message = fields.Text("Message", readonly=True)


class ImportEbayOrders(Wizard):
    """
    Import Orders Wizard

    Import orders for the current ebay channel
    """
    __name__ = 'channel.ebay.import_orders'

    start = StateView(
        'channel.ebay.import_orders.view',
        'ebay.import_ebay_orders_view_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Continue', 'import_', 'tryton-ok', default=True),
        ]
    )

    import_ = StateAction('sale.act_sale_form')

    def default_start(self, data):
        """
        Sets default data for wizard
        """
        return {
            'message':
                'This wizard will import orders for this channel ' +
                'It imports orders updated after Last Order Import Time.'
        }

    def do_import_(self, action):
        """
        Import eBay orders for current channel
        """
        SaleChannel = Pool().get('sale.channel')

        ebay_channel = SaleChannel(Transaction().context.get('active_id'))

        sales = ebay_channel.import_ebay_orders()

        action['pyson_domain'] = PYSONEncoder().encode([
            ('id', 'in', map(int, sales))
        ])
        return action, {}

    def transition_import_(self):
        return 'end'
