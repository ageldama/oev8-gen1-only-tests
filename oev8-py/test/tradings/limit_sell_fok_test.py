"""oev8.svcs.trading.TradingService.order_limit_sell() + FoK 테스트."""
from unittest.mock import call, ANY
from pytest import fixture  # type:ignore
from oev8.svcs.trading import TradingService
from oev8.typedefs import TradingId, CurrencyType, CustomerId
from oev8.typedefs import ItemQty, BalanceType, CurrencyAmt
from oev8.typedefs import OrderOption
from oev8.values.event_writer import TradingOrderCancelCauseFoK, \
    ItemCountXferToCauseBuying


@fixture
def sell_fixture(trading_service: TradingService):
    """order_buy 기본 fixture."""
    trd_id = TradingId('1')
    trd_id_nf = TradingId('2')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')

    # setup
    trd = trading_service.start_new_trading(trd_id, curr)
    balance_service = trading_service.balance_service

    for cust_id in (cust_a, cust_b, cust_c):
        balance_service.deposit(
            BalanceType.BALANCE, cust_id, curr, CurrencyAmt(1_000))

    oid_1 = trading_service.order_limit_buy(
        trd_id, cust_a, CurrencyAmt(5), ItemQty(5))

    oid_2 = trading_service.order_limit_buy(
        trd_id, cust_b, CurrencyAmt(10), ItemQty(2))

    oid_3 = trading_service.order_limit_buy(
        trd_id, cust_b, CurrencyAmt(15), ItemQty(3))

    #
    return {
        'trd_id': trd_id,
        'trd_id_not_found': trd_id_nf,
        'curr': curr,
        'cust_a': cust_a,
        'cust_b': cust_b,
        'cust_c': cust_c,
        'trd': trd,
        'oids': (oid_1, oid_2, oid_3),
        'trading_service': trading_service,
        'item_count_service': trading_service.item_count_service,
        'balance_service': trading_service.balance_service,
    }


def test_order_sell_with_fok_cancels(
        sell_fixture,
        event_writer_mock
):
    """order_limit_sell + FoK 테스트."""
    # pylint: disable=redefined-outer-name

    trd_id = sell_fixture['trd_id']
    trd = sell_fixture['trd']
    curr = sell_fixture['curr']
    cust_c = sell_fixture['cust_c']

    trading_service = sell_fixture['trading_service']
    item_count_service = sell_fixture['item_count_service']
    balance_service = sell_fixture['balance_service']

    #
    trading_service.provide_item(trd_id, cust_c, ItemQty(10))

    oid = trading_service.order_limit_sell(
        trd_id, cust_c, CurrencyAmt(99999), ItemQty(10),
        option=OrderOption.FILL_OR_KILL)

    # the order really got cancelled?
    assert oid not in trd.orders

    # empty matches?
    assert len(trd.matches) == 0

    # item-count
    assert item_count_service.get(cust_c, trd_id) == 10  # all returned.

    # balance-check?
    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) == 1_000

    # event_writer.
    event_writer_mock.on_item_count_xfer_to.assert_not_called()
    event_writer_mock.on_trading_limit_sell_order.assert_has_calls([
        call(trd_id='1', ord_id=4, cust_id='3', price=99999, qty=10,
             option=OrderOption.FILL_OR_KILL)
    ])
    event_writer_mock.on_trading_order_matched.assert_not_called()
    event_writer_mock.on_trading_order_cancelled.assert_has_calls([
        call(trd_id='1', ord_id=4, cust_id='3', price=99999,
             qty=10, remaining_qty=10,
             why=TradingOrderCancelCauseFoK())
    ])


def test_order_sell_with_fok_with_partial_match(
        sell_fixture,
        event_writer_mock
):
    """order_limit_sell + FoK / Partial match 테스트."""
    # pylint: disable=redefined-outer-name

    trd_id = sell_fixture['trd_id']
    trd = sell_fixture['trd']
    curr = sell_fixture['curr']
    cust_c = sell_fixture['cust_c']

    trading_service = sell_fixture['trading_service']
    item_count_service = sell_fixture['item_count_service']
    balance_service = sell_fixture['balance_service']

    #
    trading_service.provide_item(trd_id, cust_c, ItemQty(10))

    oid = trading_service.order_limit_sell(
        trd_id, cust_c, CurrencyAmt(15), ItemQty(10),
        option=OrderOption.FILL_OR_KILL)

    # the order really got cancelled?
    assert oid not in trd.orders

    # empty matches?
    assert len(trd.matches) == 0

    # item-count: 모두 되돌려 받음.
    assert item_count_service.get(cust_c, trd_id) == 10

    # balance-check?
    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) == 1_000

    # event_writer.
    event_writer_mock.on_item_count_xfer_to.assert_not_called()
    event_writer_mock.on_trading_limit_sell_order.assert_called_once()
    event_writer_mock.on_trading_order_matched.assert_not_called()
    event_writer_mock.on_trading_order_cancelled.assert_has_calls([
        call(trd_id='1', ord_id=4, cust_id='3', price=ANY,
             qty=10, remaining_qty=10,
             why=TradingOrderCancelCauseFoK())
    ])


def test_order_sell_with_fok_with_fulfilled(
        sell_fixture,
        event_writer_mock
):
    """order_limit_sell + FoK / Fulfilled 테스트."""
    # pylint: disable=redefined-outer-name

    trd_id = sell_fixture['trd_id']
    trd = sell_fixture['trd']
    curr = sell_fixture['curr']
    cust_c = sell_fixture['cust_c']

    trading_service = sell_fixture['trading_service']
    item_count_service = sell_fixture['item_count_service']
    balance_service = sell_fixture['balance_service']

    #
    trading_service.provide_item(trd_id, cust_c, ItemQty(10))

    oid = trading_service.order_limit_sell(
        trd_id, cust_c, CurrencyAmt(15), ItemQty(3),
        option=OrderOption.FILL_OR_KILL)

    # the order really got cancelled?
    assert oid in trd.orders
    assert not trd.orders[oid].cancelled
    assert trd.orders[oid].fulfilled

    # empty matches?
    assert len(trd.matches) == 1

    # item-count
    assert item_count_service.get(cust_c, trd_id) == 7

    # balance-check?
    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) == 1_000

    # event_writer.
    event_writer_mock.on_item_count_xfer_to.assert_has_calls([
        call(cust_id='2', trd_id='1', qty=3, new_qty=3, new_svc=0,
             why=ItemCountXferToCauseBuying(match_id=1))
    ])
    event_writer_mock.on_trading_limit_sell_order.assert_called_once()
    event_writer_mock.on_trading_order_matched.assert_has_calls([
        call(match_id=1, trd_id='1', m_ord_id=3, t_ord_id=4, t_cust_id='3',
             price=15, qty=3)
    ])
    event_writer_mock.on_trading_order_cancelled.assert_not_called()
