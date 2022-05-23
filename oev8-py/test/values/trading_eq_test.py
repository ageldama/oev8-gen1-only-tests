from copy import deepcopy
from oev8.values.tradings import Trading
from oev8.values.orders import OrderOfferLine
from oev8.values.orders import MatchedOrderLine
from oev8.typedefs import TradingState, CurrencyType
from oev8.typedefs import OrderSide, OrderType, OrderOption
from oev8.typedefs import TradingType


def test_trading_eq_01():
    t_01 = Trading()
    t_01.state = TradingState.OPEN
    t_01.trading_type = TradingType.EXCHANGE

    t_01.orders[123] = OrderOfferLine(cust_id='111',
                                      side=OrderSide.SELL,
                                      order_type=OrderType.LIMIT,
                                      option=OrderOption.NONE,
                                      price=1, qty=10,
                                      fulfilled=True, cancelled=False)

    t_01.orders[456] = OrderOfferLine(cust_id='333',
                                      side=OrderSide.BUY,
                                      order_type=OrderType.LIMIT,
                                      option=OrderOption.NONE,
                                      price=2, qty=100,
                                      fulfilled=False, cancelled=False)

    t_01.orders[789] = OrderOfferLine(cust_id='222',
                                      side=OrderSide.SELL,
                                      order_type=OrderType.LIMIT,
                                      option=OrderOption.NONE,
                                      price=100, qty=10,
                                      fulfilled=False, cancelled=False)

    t_01.matches.append(MatchedOrderLine(match_id=1, price=2, qty=10,
                                         making_taking_order_pair=(123, 456,)))

    # amt -> order-id -> qty
    t_01.buys[2] = {456: 90}
    t_01.sells[100] = {789: 10}

    t_01.item_providings[111] = 10
    t_01.item_providings[222] = 20

    #
    assert t_01 is not None
    assert t_01 == t_01
    assert t_01 != []

    # curr
    t_02 = deepcopy(t_01)

    assert t_01 == t_02
    t_02.curr = 18
    assert t_01.curr != 18
    assert t_01 != t_02

    # state
    t_02 = deepcopy(t_01)
    t_02.state = TradingState.CANCELLED

    assert t_01.state != TradingState.CANCELLED
    assert t_01 != t_02

    # trading_type
    t_02 = deepcopy(t_01)
    t_02.trading_type = TradingType.AUCTION

    assert t_01.trading_type != TradingType.AUCTION
    assert t_01 != t_02

    # add to orders
    t_02 = deepcopy(t_01)
    t_02.orders[1818] = OrderOfferLine(cust_id='999',
                                       side=OrderSide.SELL,
                                       order_type=OrderType.LIMIT,
                                       option=OrderOption.NONE,
                                       price=1, qty=10,
                                       fulfilled=False, cancelled=False)
    assert len(t_01.orders) != len(t_02.orders)
    assert t_01 != t_02

    # modify an order
    t_02 = deepcopy(t_01)
    t_02.orders[123].cancelled = True

    assert t_01.orders[123].cancelled is False
    assert t_01 != t_02

    # add to matches
    t_02 = deepcopy(t_01)
    t_02.matches.append(MatchedOrderLine(
        match_id=2, price=18, qty=1818,
        making_taking_order_pair=(1818, 8181,)))
    assert len(t_01.matches) != len(t_02.matches)
    assert t_01 != t_02

    # modify a match
    t_02 = deepcopy(t_01)
    t_02.matches[0].qty = 1818
    assert t_01 != t_02

    # add to `buys`
    t_02 = deepcopy(t_01)
    t_02.buys[1818] = {}

    assert t_01 != t_02

    # add to `buys`
    t_02 = deepcopy(t_01)
    t_02.buys[2] = {456: 90}

    assert t_01 == t_02

    # add to `sells`
    t_02 = deepcopy(t_01)
    t_02.sells[1818] = {}

    assert t_01 != t_02

    # add to `auction_bids`
    t_02 = deepcopy(t_01)
    t_02.auction_bids[1818] = {}

    assert t_01 != t_02

    # add to `item_providings`
    t_02 = deepcopy(t_01)
    t_02.item_providings[777] = 172762
    assert len(t_01.item_providings) != len(t_02.item_providings)
    assert t_01 != t_02
