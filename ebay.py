# -*- coding: utf-8 -*-
"""
    ebay

    :copyright: (c) 2013-2015 by Openlabs Technologies & Consulting (P) Limited
    :license: GPLv3, see LICENSE for more details.
"""
import dateutil.parser

from ebaysdk import trading
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, Button
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.pyson import Eval


__all__ = ['SellerAccount', 'CheckTokenStatusView', 'CheckTokenStatus']


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
        cls._buttons.update({
            'check_token_status': {},
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
