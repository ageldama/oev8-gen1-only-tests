from pytest import raises  # type:ignore
from oev8.excs import TradingIsNotFound
from oev8.typedefs import ItemQty, BalanceType
from oev8.typedefs import OrderSide, OrderType, OrderOption
from oev8.values.orders import OrderOfferLine, MatchedOrderLine


def test_count_trading_id__empty(trading_service):
    assert 0 == trading_service.count_trading_id()


def test_count_trading_id(trading_service):
    trading_service.start_new_trading(trd_id='1', curr=1)
    assert 1 == trading_service.count_trading_id()

    trading_service.start_new_trading(trd_id='2', curr=2)
    assert 2 == trading_service.count_trading_id()

    trading_service.cancel_trading(trd_id='2')
    trading_service.evict_trading(trd_id='2')

    assert 1 == trading_service.count_trading_id()


def test_list_trading_id__empty(trading_service):
    assert [] == list(trading_service.list_trading_id(
        offset=0, limit=10))


def test_list_trading_id(trading_service):
    for i in range(100):
        trading_service.start_new_trading(trd_id=str(i), curr=i)

    assert ['3', '4', '5', '6'] == list(trading_service.list_trading_id(
        offset=3, limit=4))


def test_list_trading_id__over(trading_service):
    for i in range(100):
        trading_service.start_new_trading(trd_id=str(i), curr=i)

    assert [] == list(trading_service.list_trading_id(
        offset=200, limit=3))


def test_get_trading_info__not_found(trading_service):
    with raises(TradingIsNotFound):
        trading_service.get_trading(trd_id='1')


def test_get_trading_info(trading_service):
    for i in range(10):
        trading_service.start_new_trading(trd_id=str(i), curr=i)

    assert trading_service.get_trading(trd_id='0') is not None
    assert trading_service.get_trading(trd_id='1') is not None
    assert trading_service.get_trading(trd_id='9') is not None

    with raises(TradingIsNotFound):
        trading_service.get_trading(trd_id='10')


def test_count_item_providing__not_found(trading_service):
    with raises(TradingIsNotFound):
        trading_service.count_item_providing(trd_id='1')


def test_count_item_providing__empty(trading_service):
    trading_service.start_new_trading(trd_id='1', curr=1)
    assert 0 == trading_service.count_item_providing(trd_id='1')


def test_count_item_providing(trading_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    trading_service.provide_item(trd_id='1', cust_id='2', qty=ItemQty(123))
    assert 1 == trading_service.count_item_providing(trd_id='1')

    trading_service.provide_item(trd_id='1', cust_id='3', qty=ItemQty(123))
    assert 2 == trading_service.count_item_providing(trd_id='1')


def test_list_item_providing__empty(trading_service):
    with raises(TradingIsNotFound):
        trading_service.list_item_providing(
            trd_id='1', offset=0, limit=10)


def test_count_item_providing__same_cust(trading_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    for i in range(10):
        # with same `cust_id`.
        trading_service.provide_item(trd_id='1', cust_id='2',
                                     qty=ItemQty(10))

    assert 1 == trading_service.count_item_providing(trd_id='1')
    assert [('2', 10 * 10)] == list(trading_service.list_item_providing(
        trd_id='1', offset=0, limit=3))


def test_count_item_providing__diff_cust(trading_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    for i in range(10):
        trading_service.provide_item(trd_id=str(1), cust_id=str(i),
                                     qty=ItemQty(10 + i))

    assert [('0', 10), ('1', 11), ('2', 12)] == \
        list(trading_service.list_item_providing(trd_id='1', offset=0, limit=3))


def test_count_item_providing__over(trading_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    for i in range(10):
        trading_service.provide_item(trd_id=str(1), cust_id=str(i),
                                     qty=ItemQty(10 + i))

    assert [] == \
        list(trading_service.list_item_providing(trd_id=str(1), offset=100, limit=3))


def test_count_order__empty(trading_service):
    trading_service.start_new_trading(trd_id='1', curr=1)
    assert 0 == trading_service.count_order(trd_id='1')


def test_count_order__not_found(trading_service):
    with raises(TradingIsNotFound):
        trading_service.count_order(trd_id='1')


def test_count_order(trading_service, balance_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    balance_service.deposit(BalanceType.BALANCE, cust_id='1', curr=1,
                            amt=1_000)

    trading_service.order_market_buy(trd_id='1', cust_id='1', qty=13)

    # market-buy이니까 gone.
    assert 0 == trading_service.count_order(trd_id='1')

    oid_1 = trading_service.order_limit_buy(trd_id='1', cust_id='1',
                                            price=11, qty=3)
    assert 1 == trading_service.count_order(trd_id='1')

    oid_2 = trading_service.order_limit_buy(trd_id='1', cust_id='1',
                                            price=2, qty=5)
    assert 2 == trading_service.count_order(trd_id='1')

    trading_service.cancel_remaining_offer(trd_id='1', ord_id=oid_2)
    assert 1 == trading_service.count_order(trd_id='1')


def test_list_order__not_found(trading_service):
    with raises(TradingIsNotFound):
        trading_service.list_order(trd_id='1', offset=0, limit=10)


def test_list_order__empty(trading_service):
    trading_service.start_new_trading(trd_id='1', curr=1)
    assert [] == list(trading_service.list_order(trd_id='1', offset=0, limit=10))


def test_list_order(trading_service, balance_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    balance_service.deposit(BalanceType.BALANCE, cust_id='1', curr=1,
                            amt=1_000_000)

    trading_service.order_limit_buy(trd_id='1', cust_id='1',
                                    price=11, qty=3)
    trading_service.order_limit_buy(trd_id='1', cust_id='1',
                                    price=2, qty=5)

    result = dict(trading_service.list_order(
        trd_id='1', offset=1, limit=10))

    o = OrderOfferLine(cust_id='1', side=OrderSide.BUY,
                       order_type=OrderType.LIMIT,
                       option=OrderOption.NONE,
                       qty=5, price=2,
                       fulfilled=False, cancelled=False)
    assert {2: o} == result

    result = dict(trading_service.list_order(
        trd_id='1', offset=10, limit=10))
    assert {} == result


def test_count_match__not_found(trading_service):
    with raises(TradingIsNotFound):
        trading_service.count_match(trd_id='1')


def test_count_match__empty(trading_service, balance_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    assert 0 == trading_service.count_match(trd_id='1')

    balance_service.deposit(BalanceType.BALANCE, cust_id='1', curr=1,
                            amt=1_000_000)

    trading_service.order_limit_buy(trd_id='1', cust_id='1',
                                    price=11, qty=3)

    assert 0 == trading_service.count_match(trd_id='1')


def test_count_match(trading_service, balance_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    balance_service.deposit(BalanceType.BALANCE, cust_id='1', curr=1,
                            amt=1_000_000)

    trading_service.provide_item(trd_id='1', cust_id='2', qty=ItemQty(123))

    trading_service.provide_item(trd_id='1', cust_id='3', qty=ItemQty(10))

    trading_service.order_limit_buy(trd_id='1', cust_id='1',
                                    price=11, qty=3)

    trading_service.order_market_sell(trd_id='1', cust_id='2', qty=1)

    assert 1 == trading_service.count_match(trd_id='1')

    trading_service.order_limit_sell(trd_id='1', cust_id='3',
                                     price=10, qty=1)

    assert 2 == trading_service.count_match(trd_id='1')


def test_list_match__not_found(trading_service):
    with raises(TradingIsNotFound):
        trading_service.list_match(trd_id='1', offset=0, limit=10)


def test_list_match__empty(trading_service):
    trading_service.start_new_trading(trd_id='1', curr=1)
    assert [] == list(trading_service.list_match(trd_id='1', offset=0, limit=10))


def test_list_match__over(trading_service, balance_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    balance_service.deposit(BalanceType.BALANCE, cust_id='1', curr=1,
                            amt=1_000_000)

    trading_service.provide_item(trd_id='1', cust_id='2', qty=ItemQty(123))

    trading_service.provide_item(trd_id='1', cust_id='3', qty=ItemQty(10))

    trading_service.order_limit_buy(trd_id='1', cust_id='1',
                                    price=11, qty=3)

    trading_service.order_market_sell(trd_id='1', cust_id='2', qty=1)

    trading_service.order_limit_sell(trd_id='1', cust_id='3',
                                     price=10, qty=1)

    assert [] == list(trading_service.list_match(trd_id='1', offset=10, limit=2))


def test_list_match(trading_service, balance_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    balance_service.deposit(BalanceType.BALANCE, cust_id='1', curr=1,
                            amt=1_000_000)

    trading_service.provide_item(trd_id='1', cust_id='2', qty=ItemQty(123))

    trading_service.provide_item(trd_id='1', cust_id='3', qty=ItemQty(10))

    trading_service.provide_item(trd_id='1', cust_id='4', qty=ItemQty(10))

    trading_service.order_limit_buy(trd_id='1', cust_id='1',
                                    price=11, qty=10)

    trading_service.order_market_sell(trd_id='1', cust_id='2', qty=1)

    trading_service.order_limit_sell(trd_id='1', cust_id='3',
                                     price=10, qty=1)

    trading_service.order_limit_sell(trd_id='1', cust_id='4',
                                     price=10, qty=3)

    matches = list(trading_service.list_match(trd_id='1', offset=1, limit=2))

    assert [
        MatchedOrderLine(match_id=2, qty=1, price=11,
                         making_taking_order_pair=(1, 3,)),
        MatchedOrderLine(match_id=3, qty=3, price=11,
                         making_taking_order_pair=(1, 4,)),
    ] == matches


def test_count_price__not_found(trading_service):
    with raises(TradingIsNotFound):
        trading_service.count_price(trd_id='1', order_side=OrderSide.BUY)


def test_count_price__empty(trading_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    assert 0 == trading_service.count_price(
        trd_id='1', order_side=OrderSide.BUY)


def test_count_price(trading_service, balance_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    balance_service.deposit(BalanceType.BALANCE, cust_id='1', curr=1,
                            amt=1_000_000)

    trading_service.provide_item(trd_id='1', cust_id='2', qty=ItemQty(10))

    trading_service.provide_item(trd_id='1', cust_id='3', qty=ItemQty(10))

    trading_service.order_limit_buy(trd_id='1', cust_id='1',
                                    price=11, qty=1)

    trading_service.order_limit_buy(trd_id='1', cust_id='1',
                                    price=12, qty=2)

    trading_service.order_limit_buy(trd_id='1', cust_id='1',
                                    price=13, qty=3)

    trading_service.order_limit_sell(trd_id='1', cust_id='2',
                                     price=12, qty=3)

    assert 2 == trading_service.count_price(
        trd_id='1', order_side=OrderSide.BUY)

    assert 0 == trading_service.count_price(
        trd_id='1', order_side=OrderSide.SELL)


def test_list_price__not_found(trading_service):
    with raises(TradingIsNotFound):
        trading_service.list_price(
            trd_id='1', order_side=OrderSide.BUY,
            offset=0, limit=10)


def test_list_price__empty(trading_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    result = list(trading_service.list_price(
        trd_id='1', order_side=OrderSide.BUY,
        offset=0, limit=10))

    assert [] == result


def test_list_price__over(trading_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    trading_service.provide_item(trd_id='1', cust_id='1', qty=ItemQty(11))

    trading_service.provide_item(trd_id='1', cust_id='2', qty=ItemQty(12))

    trading_service.provide_item(trd_id='1', cust_id='3', qty=ItemQty(13))

    trading_service.order_limit_sell(trd_id='1', cust_id='1',
                                     price=10, qty=11)

    trading_service.order_limit_sell(trd_id='1', cust_id='2',
                                     price=20, qty=12)

    trading_service.order_limit_sell(trd_id='1', cust_id='3',
                                     price=30, qty=13)

    result = list(trading_service.list_price(
        trd_id='1', order_side=OrderSide.SELL,
        offset=10, limit=3))

    assert [] == result


def test_list_price(trading_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    trading_service.provide_item(trd_id='1', cust_id='1', qty=ItemQty(11))

    trading_service.provide_item(trd_id='1', cust_id='2', qty=ItemQty(12))

    trading_service.provide_item(trd_id='1', cust_id='3', qty=ItemQty(13))

    trading_service.provide_item(trd_id='1', cust_id='4', qty=ItemQty(14))

    trading_service.order_limit_sell(trd_id='1', cust_id='1',
                                     price=10, qty=11)

    trading_service.order_limit_sell(trd_id='1', cust_id='2',
                                     price=20, qty=12)

    trading_service.order_limit_sell(trd_id='1', cust_id='3',
                                     price=30, qty=13)

    trading_service.order_limit_sell(trd_id='1', cust_id='4',
                                     price=40, qty=14)

    result = list(trading_service.list_price(
        trd_id='1', order_side=OrderSide.SELL,
        offset=2, limit=3))

    assert [30, 40] == result


def test_count_order_by_price__not_found(trading_service):
    with raises(TradingIsNotFound):
        trading_service.count_order_id_by_price(
            trd_id='1', order_side=OrderSide.BUY, price=10)


def test_count_order_by_price__empty(trading_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    result = trading_service.count_order_id_by_price(
        trd_id='1', order_side=OrderSide.BUY, price=10)

    assert 0 == result


def test_count_order_by_price(trading_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    trading_service.provide_item(trd_id='1', cust_id='1', qty=ItemQty(11))

    trading_service.provide_item(trd_id='1', cust_id='2', qty=ItemQty(12))

    trading_service.provide_item(trd_id='1', cust_id='3', qty=ItemQty(13))

    trading_service.provide_item(trd_id='1', cust_id='4', qty=ItemQty(14))

    trading_service.order_limit_sell(trd_id='1', cust_id='1',
                                     price=10, qty=11)

    trading_service.order_limit_sell(trd_id='1', cust_id='2',
                                     price=20, qty=12)

    trading_service.order_limit_sell(trd_id='1', cust_id='3',
                                     price=10, qty=13)

    trading_service.order_limit_sell(trd_id='1', cust_id='4',
                                     price=40, qty=14)

    assert 2 == trading_service.count_order_id_by_price(
        trd_id='1', order_side=OrderSide.SELL, price=10)

    assert 0 == trading_service.count_order_id_by_price(
        trd_id='1', order_side=OrderSide.SELL, price=15)

    assert 0 == trading_service.count_order_id_by_price(
        trd_id='1', order_side=OrderSide.BUY, price=10)


def test_list_order_by_price__not_found(trading_service):
    with raises(TradingIsNotFound):
        trading_service.list_order_id_by_price(
            trd_id='1', order_side=OrderSide.BUY, price=10,
            offset=0, limit=10)


def test_list_order_by_price__empty(trading_service):
    trading_service.start_new_trading(trd_id='1', curr=1)
    result = dict(trading_service.list_order_id_by_price(
            trd_id='1', order_side=OrderSide.BUY, price=10,
            offset=0, limit=10))
    assert {} == result


def test_count_order_by_price(trading_service, balance_service):
    trading_service.start_new_trading(trd_id='1', curr=1)

    trading_service.provide_item(trd_id='1', cust_id='1', qty=ItemQty(11))

    trading_service.provide_item(trd_id='1', cust_id='2', qty=ItemQty(12))

    trading_service.provide_item(trd_id='1', cust_id='3', qty=ItemQty(13))

    trading_service.provide_item(trd_id='1', cust_id='4', qty=ItemQty(14))

    balance_service.deposit(BalanceType.BALANCE, cust_id='10', curr=1,
                            amt=1_000_000)

    balance_service.deposit(BalanceType.BALANCE, cust_id='11', curr=1,
                            amt=1_000_000)

    oid_1 = trading_service.order_limit_sell(trd_id='1', cust_id='1',
                                             price=11, qty=11)

    oid_2 = trading_service.order_limit_sell(trd_id='1', cust_id='2',
                                             price=11, qty=12)

    oid_3 = trading_service.order_limit_sell(trd_id='1', cust_id='3',
                                             price=11, qty=13)

    oid_4 = trading_service.order_limit_sell(trd_id='1', cust_id='4',
                                             price=50, qty=14)

    oid_5 = trading_service.order_limit_buy(trd_id='1', cust_id='10',
                                            price=11, qty=3)

    result = dict(trading_service.list_order_id_by_price(
        trd_id='1', order_side=OrderSide.SELL, price=11,
        offset=1, limit=3))

    assert {oid_2: 12, oid_3: 13} == result

    result = dict(trading_service.list_order_id_by_price(
        trd_id='1', order_side=OrderSide.BUY, price=11,
        offset=0, limit=3))

    assert {} == result
