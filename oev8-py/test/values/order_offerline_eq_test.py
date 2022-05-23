from copy import copy
from oev8.values.orders import OrderOfferLine
from oev8.typedefs import OrderSide, OrderType, OrderOption


def test_order_offerline_eq_01():
    o1 = OrderOfferLine(cust_id='123',
                        side=OrderSide.BUY,
                        order_type=OrderType.LIMIT,
                        option=OrderOption.NONE,
                        price=123, qty=456,
                        fulfilled=False, cancelled=False)

    assert not (o1 == None)
    assert not (o1 == "foobar")

    assert o1 == o1

    o2 = copy(o1)
    assert o1 == o2 and o1 is not o2

    #
    o2 = copy(o1)
    o2.cust_id = '111'
    assert o1.cust_id != '111'
    assert o1 != o2

    #
    o2 = copy(o1)
    o2.side = OrderSide.SELL
    assert o1.side != OrderSide.SELL
    assert o1 != o2

    #
    o2 = copy(o1)
    o2.order_type = OrderType.MARKET
    assert o1.order_type != OrderType.MARKET
    assert o1 != o2

    #
    o2 = copy(o1)
    o2.option = OrderOption.FILL_OR_KILL
    assert o1.option != OrderOption.FILL_OR_KILL
    assert o1 != o2

    #
    o2 = copy(o1)
    o2.price = 11111
    assert o1.price != 11111
    assert o1 != o2

    #
    o2 = copy(o1)
    o2.qty = 999
    assert o1.qty != 999
    assert o1 != o2

    #
    o2 = copy(o1)
    o2.fulfilled = True
    assert o1.fulfilled != True
    assert o1 != o2

    #
    o2 = copy(o1)
    o2.cancelled = True
    assert o1.cancelled != True
    assert o1 != o2
