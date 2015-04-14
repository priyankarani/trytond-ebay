# -*- coding: utf-8 -*-
"""
    ebay

    :copyright: (c) 2013-2015 by Openlabs Technologies & Consulting (P) Limited
    :license: GPLv3, see LICENSE for more details.
"""
import dateutil.parser
from datetime import datetime
from dateutil.relativedelta import relativedelta

from ebaysdk import trading
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, Button, StateAction
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.pyson import Eval, PYSONEncoder


__all__ = [
    'SellerAccount', 'CheckTokenStatusView', 'CheckTokenStatus',
    'ImportOrders', 'ImportOrdersView'
]


class SellerAccount(ModelSQL, ModelView):
    "eBay Seller Account"
    __name__ = 'ebay.seller.account'

    name = fields.Char(
        'Name', required=True, help="A name which defines this account",
    )

    company = fields.Many2One(
        'company.company', 'Company', required=True,
        help="Company to which this account is linked",
    )

    app_id = fields.Char(
        'AppID', required=True,
        help="APP ID of the account - provided by eBay",
    )

    dev_id = fields.Char(
        'DevID', required=True, help="Dev ID of account - provided by eBay",
    )

    cert_id = fields.Char(
        'CertID', required=True, help="Cert ID of account - provided by eBay",
    )

    token = fields.Text(
        'Token', required=True,
        help="Token for this user account - to be generated from eBay "
        "developer home. If it expirees, then a new one should be generated",
    )

    is_sandbox = fields.Boolean(
        'Is sandbox ?',
        help="Select this if this account is a sandbox account",
    )

    default_uom = fields.Many2One(
        'product.uom', 'Default Product UOM', required=True
    )

    default_account_expense = fields.Property(fields.Many2One(
        'account.account', 'Account Expense', domain=[
            ('kind', '=', 'expense'),
            ('company', '=', Eval('company')),
        ], depends=['company'], required=True
    ))

    default_account_revenue = fields.Property(fields.Many2One(
        'account.account', 'Account Revenue', domain=[
            ('kind', '=', 'revenue'),
            ('company', '=', Eval('company')),
        ], depends=['company'], required=True
    ))

    last_order_import_time = fields.DateTime(
        'Last Order Import Time', required=True
    )

    @staticmethod
    def default_last_order_import_time():
        """
        Set default last order import time
        """
        return datetime.utcnow() - relativedelta(days=30)

    @staticmethod
    def default_default_uom():
        UoM = Pool().get('product.uom')

        unit = UoM.search([
            ('name', '=', 'Unit'),
        ])
        return unit and unit[0].id or None

    @classmethod
    def __setup__(cls):
        """
        Setup the class before adding to pool
        """
        super(SellerAccount, cls).__setup__()
        cls._sql_constraints += [
            (
                'unique_app_dev_cert_token',
                'UNIQUE(app_id, dev_id, cert_id, token)',
                'All the ebay credentials should be unique.'
            )
        ]
        cls._error_messages.update({
            "no_orders": 'No new orders have been placed on eBay for this ' +
                'seller account after %s'
        })
        cls._buttons.update({
            'check_token_status': {},
            'import_orders_button': {},
        })

    def get_trading_api(self):
        """Create an instance of ebay trading api

        :return: ebay trading api instance
        """
        domain = 'api.sandbox.ebay.com' if self.is_sandbox else 'api.ebay.com'
        return trading(
            appid=self.app_id,
            certid=self.cert_id,
            devid=self.dev_id,
            token=self.token,
            domain=domain
        )

    @classmethod
    @ModelView.button_action('ebay.check_token_status')
    def check_token_status(cls, accounts):
        """
        Check the status of token and display to user

        :param accounts: Active record list of seller accounts
        """
        pass

    @classmethod
    @ModelView.button_action('ebay.import_orders')
    def import_orders_button(cls, accounts):
        """
        Import orders for current account

        :param accounts: Active record list of seller accounts
        """
        pass

    def import_orders(self):
        """
        Imports orders for current MWS account

        :return: List of active records of sale
        """
        Sale = Pool().get('sale.sale')

        sales = []
        api = self.get_trading_api()
        now = datetime.utcnow()

        last_import_time = self.last_order_import_time

        self.write([self], {'last_order_import_time': now})

        response = api.execute(
            'GetOrders', {
                'CreateTimeFrom': last_import_time,
                'CreateTimeTo': now
            }
        ).response_dict()
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

        with Transaction().set_context(
            {'ebay_seller_account': self.id}
        ):
            for order_data in orders:
                sales.append(Sale.create_using_ebay_data(order_data))

        return sales


class CheckTokenStatusView(ModelView):
    "Check Token Status View"
    __name__ = 'ebay.check_token_status.view'

    status = fields.Char('Status', readonly=True)
    expiry_date = fields.DateTime('Expiry Date', readonly=True)


class CheckTokenStatus(Wizard):
    """
    Check Token Status Wizard

    Check token status for the current seller account's token.
    """
    __name__ = 'ebay.check_token_status'

    start = StateView(
        'ebay.check_token_status.view',
        'ebay.check_token_status_view_form',
        [
            Button('OK', 'end', 'tryton-ok'),
        ]
    )

    def default_start(self, data):
        """Check the status of the token of the seller account

        :param data: Wizard data
        """
        SellerAccount = Pool().get('ebay.seller.account')

        account = SellerAccount(Transaction().context.get('active_id'))

        api = account.get_trading_api()
        response = api.execute('GetTokenStatus').response_dict()

        return {
            'status': response['TokenStatus']['Status']['value'],
            'expiry_date': dateutil.parser.parse(
                response['TokenStatus']['ExpirationTime']['value']
            ),
        }


class ImportOrdersView(ModelView):
    "Import Orders View"
    __name__ = 'ebay.import_orders.view'

    message = fields.Text("Message", readonly=True)


class ImportOrders(Wizard):
    """
    Import Orders Wizard

    Import orders for the current seller account
    """
    __name__ = 'ebay.import_orders'

    start = StateView(
        'ebay.import_orders.view',
        'ebay.import_orders_view_form',
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
            'message': 'This wizard will import orders for this seller ' +
                'account. It imports orders updated after Last Order ' +
                'Import Time.'
        }

    def do_import_(self, action):
        """Handles the transition"""

        SellerAccount = Pool().get('ebay.seller.account')

        account = SellerAccount(Transaction().context.get('active_id'))

        sales = account.import_orders()

        action['pyson_domain'] = PYSONEncoder().encode([
            ('id', 'in', map(int, sales))
        ])
        return action, {}

    def transition_import_(self):
        return 'end'
