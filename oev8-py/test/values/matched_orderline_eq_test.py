from copy import copy
from oev8.values.orders import MatchedOrderLine


def test_matched_orderline_eq_01():
    o1 = MatchedOrderLine(match_id=777,
                          price=123, qty=456,
                          making_taking_order_pair=(100, 200,))

    assert not (o1 == None)
    assert not (o1 == "foobar")

    assert o1 == o1

    o2 = copy(o1)
    assert o1 == o2 and o1 is not o2

    #
    o2 = copy(o1)
    o2.match_id = 111
    assert o1.match_id != 111
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
    o2.making_taking_order_pair = (200, 200,)
    assert o1.making_taking_order_pair != (200, 200,)
    assert o1 != o2

    #
    o2 = copy(o1)
    o2.making_taking_order_pair = (100, 100,)
    assert o1.making_taking_order_pair != (100, 100,)
    assert o1 != o2
