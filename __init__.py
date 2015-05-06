# -*- coding: utf-8 -*-
"""
    test_views

    Tests views and depends

    :copyright: (c) 2013 by Openlabs Technologies & Consulting (P) Limited
    :license: GPLv3, see LICENSE for more details.
"""
from trytond.pool import Pool
from .country import Subdivision
from .party import Party, Address
from .product import Product
from .sale import Sale
from channel import (
    SaleChannel, CheckEbayTokenStatusView, CheckEbayTokenStatus,
    ImportEbayOrders, ImportEbayOrdersView
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
        ImportEbayOrdersView,
        module='ebay', type_='model'
    )
    Pool.register(
        CheckEbayTokenStatus,
        ImportEbayOrders,
        module='ebay', type_='wizard'
    )
