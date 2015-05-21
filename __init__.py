# -*- coding: utf-8 -*-
"""
    test_views

    Tests views and depends

    :copyright: (c) 2013-2015 by Openlabs Technologies & Consulting (P) Limited
    :license: GPLv3, see LICENSE for more details.
"""
from trytond.pool import Pool
from .country import Subdivision
from .party import Party, Address
from .product import Product
from .sale import Sale
from channel import (
    SaleChannel, CheckEbayTokenStatusView, CheckEbayTokenStatus,
)


def register():
    "Register classes with pool"
    Pool.register(
        Subdivision,
        Party,
        Address,
        SaleChannel,
        Product,
        Sale,
        CheckEbayTokenStatusView,
        module='ebay', type_='model'
    )
    Pool.register(
        CheckEbayTokenStatus,
        module='ebay', type_='wizard'
    )
