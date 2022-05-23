"""oev8.svcs.trading.TradingService.order_limit_buy() + FoK 테스트."""
from unittest.mock import call
from pytest import mark, fixture  # type:ignore
from oev8.svcs.trading import TradingService
from oev8.typedefs import TradingId, CurrencyType, CustomerId
from oev8.typedefs import ItemQty, BalanceType, CurrencyAmt
from oev8.typedefs import OrderOption
from oev8.values.event_writer import TradingOrderCancelCauseFoK, \
    ItemCountXferToCauseBuying, BalanceXferFromCauseBuying


@fixture
def buy_fixture(trading_service: TradingService):
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

    trading_service.provide_item(trd_id, cust_a, ItemQty(10))
    trading_service.provide_item(trd_id, cust_b, ItemQty(7))

    balance_service.deposit(BalanceType.BALANCE, cust_c, curr,
                            CurrencyAmt(1_000))

    oid_1 = trading_service.order_limit_sell(
        trd_id, cust_a, CurrencyAmt(10), ItemQty(10))

    oid_2 = trading_service.order_limit_sell(
        trd_id, cust_b, CurrencyAmt(5), ItemQty(5))

    oid_3 = trading_service.order_limit_sell(
        trd_id, cust_b, CurrencyAmt(15), ItemQty(2))

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


def test_order_buy_with_fok_cancels(
        buy_fixture,
        event_writer_mock
):
    """order_limit_buy + fok + no-matches 테스트."""
    # pylint: disable=redefined-outer-name

    trd_id = buy_fixture['trd_id']
    trd = buy_fixture['trd']
    curr = buy_fixture['curr']
    cust_c = buy_fixture['cust_c']

    trading_service = buy_fixture['trading_service']
    item_count_service = buy_fixture['item_count_service']
    balance_service = buy_fixture['balance_service']

    #
    oid = trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(1), ItemQty(100),
        option=OrderOption.FILL_OR_KILL)

    # the order really got cancelled?
    assert oid not in trd.orders

    # empty matches?
    assert len(trd.matches) == 0

    # item-count
    assert item_count_service.get(cust_c, trd_id) == 0

    # balance-check: 잔고 되돌려 받음 or 건드리지 않아야함.
    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) == 1_000

    # event_writer.
    event_writer_mock.on_item_count_xfer_to.assert_not_called()
    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_buy_order.assert_has_calls([
        call(trd_id='1', ord_id=4, cust_id='3', price=1, qty=100,
             option=OrderOption.FILL_OR_KILL)
    ])
    event_writer_mock.on_trading_order_matched.assert_not_called()
    event_writer_mock.on_trading_order_cancelled.assert_has_calls([
        call(trd_id='1', ord_id=4, cust_id='3', price=1,
             qty=100, remaining_qty=100,
             why=TradingOrderCancelCauseFoK())
    ])


def test_order_buy_with_fok_with_partial_match(
        buy_fixture,
        event_writer_mock
):
    """order_limit_buy 테스트."""
    # pylint: disable=redefined-outer-name

    trd_id = buy_fixture['trd_id']
    trd = buy_fixture['trd']
    curr = buy_fixture['curr']
    cust_c = buy_fixture['cust_c']

    trading_service = buy_fixture['trading_service']
    item_count_service = buy_fixture['item_count_service']
    balance_service = buy_fixture['balance_service']

    #
    oid = trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(5), ItemQty(10),
        option=OrderOption.FILL_OR_KILL)

    # the order really got cancelled?
    assert oid not in trd.orders

    # empty matches?
    assert len(trd.matches) == 0

    # item-count
    assert item_count_service.get(cust_c, trd_id) == 0

    # balance-check: 잔고 되돌려 받음 or 건드리지 않아야함.
    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) == 1_000

    # event_writer.
    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_item_count_xfer_to.assert_not_called()
    event_writer_mock.on_trading_limit_buy_order.assert_has_calls([
        call(trd_id='1', ord_id=4, cust_id='3', price=5, qty=10,
             option=OrderOption.FILL_OR_KILL)
    ])
    event_writer_mock.on_trading_order_matched.assert_not_called()
    event_writer_mock.on_trading_order_cancelled.assert_has_calls([
        call(trd_id='1', ord_id=4, cust_id='3', price=5, qty=10,
             remaining_qty=10, why=TradingOrderCancelCauseFoK())
    ])


def test_order_buy_with_fok_with_fulfilled(
        buy_fixture,
        event_writer_mock
):
    """order_limit_buy 테스트."""
    # pylint: disable=redefined-outer-name

    trd_id = buy_fixture['trd_id']
    trd = buy_fixture['trd']
    curr = buy_fixture['curr']
    cust_c = buy_fixture['cust_c']

    trading_service = buy_fixture['trading_service']
    item_count_service = buy_fixture['item_count_service']
    balance_service = buy_fixture['balance_service']

    #
    oid = trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(10), ItemQty(15),
        option=OrderOption.FILL_OR_KILL)

    # the order really got cancelled?
    assert oid in trd.orders
    assert not trd.orders[oid].cancelled
    assert trd.orders[oid].fulfilled

    # empty matches?
    assert len(trd.matches) == 2

    # item-count
    assert item_count_service.get(cust_c, trd_id) == 15

    # balance-check?
    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) \
        == 1_000 - (10 * 15)  # all paid

    # event_writer.
    event_writer_mock.on_item_count_xfer_to.assert_has_calls([
        call(cust_id='3', trd_id='1', qty=5, new_qty=5, new_svc=12,
             why=ItemCountXferToCauseBuying(match_id=1)),
        call(cust_id='3', trd_id='1', qty=10, new_qty=15, new_svc=2,
             why=ItemCountXferToCauseBuying(match_id=2))
    ])
    event_writer_mock.on_balance_xfer_from.assert_called_once()
    event_writer_mock.on_trading_limit_buy_order.assert_called_once()
    event_writer_mock.on_trading_order_matched.assert_has_calls([
        call(match_id=1, trd_id='1', m_ord_id=2, t_ord_id=4, t_cust_id='3',
             price=10, qty=5),
        call(match_id=2, trd_id='1', m_ord_id=1, t_ord_id=4, t_cust_id='3',
             price=10, qty=10)
    ])
    event_writer_mock.on_trading_order_cancelled.assert_not_called()
