"""oev8.svcs.trading.TradingService.order_limit_buy() + IoC 테스트."""
from unittest.mock import call
from pytest import fixture  # type:ignore
from oev8.svcs.trading import TradingService
from oev8.svcs.balance import BalanceService
from oev8.svcs.item_count import ItemCountService
from oev8.typedefs import TradingId, CurrencyType, CustomerId
from oev8.typedefs import ItemQty, BalanceType, CurrencyAmt
from oev8.typedefs import OrderOption
from oev8.values.event_writer import TradingOrderCancelCauseIoC, \
    ItemCountXferToCauseBuying, BalanceXferFromCauseBuying


@fixture
def order_buy_basic_fixture(trading_service: TradingService):
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


def test_order_buy_with_ioc_cancels(
        order_buy_basic_fixture,
        event_writer_mock
):
    """order_limit_buy 테스트."""
    # pylint: disable=redefined-outer-name

    trd_id = order_buy_basic_fixture['trd_id']
    trd = order_buy_basic_fixture['trd']
    curr = order_buy_basic_fixture['curr']
    cust_c = order_buy_basic_fixture['cust_c']

    trading_service = order_buy_basic_fixture['trading_service']
    item_count_service = order_buy_basic_fixture['item_count_service']
    balance_service = order_buy_basic_fixture['balance_service']

    #
    oid = trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(1), ItemQty(100),
        option=OrderOption.IMMEDIATE_OR_CANCEL)

    # the order really got cancelled?
    assert oid not in trd.orders

    # empty matches?
    assert len(trd.matches) == 0

    # item-count
    assert item_count_service.get(cust_c, trd_id) == 0

    # balance-check: 다시 환불.
    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) == 1_000

    # event_writer.
    event_writer_mock.on_item_count_xfer_to.assert_not_called()
    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_buy_order.assert_has_calls([
        call(trd_id='1', ord_id=4, cust_id='3', price=1, qty=100,
             option=OrderOption.IMMEDIATE_OR_CANCEL)
    ])
    event_writer_mock.on_trading_order_matched.assert_not_called()
    event_writer_mock.on_trading_order_cancelled.assert_has_calls([
        call(trd_id='1', ord_id=4, cust_id='3', price=1,
             qty=100, remaining_qty=100,
             why=TradingOrderCancelCauseIoC())
    ])


def test_order_buy_with_ioc_with_partial_match(
        order_buy_basic_fixture,
        event_writer_mock
):
    """order_limit_buy 테스트."""
    # pylint: disable=redefined-outer-name

    trd_id = order_buy_basic_fixture['trd_id']
    trd = order_buy_basic_fixture['trd']
    curr = order_buy_basic_fixture['curr']
    cust_c = order_buy_basic_fixture['cust_c']

    trading_service = order_buy_basic_fixture['trading_service']
    item_count_service = order_buy_basic_fixture['item_count_service']
    balance_service = order_buy_basic_fixture['balance_service']

    #
    oid = trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(5), ItemQty(10),
        option=OrderOption.IMMEDIATE_OR_CANCEL)

    # the order really got cancelled?
    assert oid in trd.orders
    assert not trd.orders[oid].cancelled
    assert not trd.orders[oid].fulfilled

    # empty matches?
    assert len(trd.matches) == 1

    # item-count: only 5, not 10.
    assert item_count_service.get(cust_c, trd_id) == 5

    # balance-check?
    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) \
        == 1_000 - (10 * 5)  # all paid in advance.

    # event_writer.
    event_writer_mock.on_balance_xfer_from.assert_has_calls([
        call(balance_type=BalanceType.BALANCE, cust_id='3', curr=1,
             amt=50, new_amt=950, new_svc=50,
             why=BalanceXferFromCauseBuying(trd_id='1', ord_id=4))
    ])
    event_writer_mock.on_item_count_xfer_to.assert_has_calls([
        call(cust_id='3', trd_id='1', qty=5, new_qty=5, new_svc=12,
             why=ItemCountXferToCauseBuying(match_id=1))
    ])
    event_writer_mock.on_trading_limit_buy_order.assert_has_calls([
        call(trd_id='1', ord_id=4, cust_id='3', price=5, qty=10,
             option=OrderOption.IMMEDIATE_OR_CANCEL)
    ])
    event_writer_mock.on_trading_order_matched.assert_has_calls([
        call(match_id=1, trd_id='1', m_ord_id=2, t_ord_id=4, t_cust_id='3',
             price=5, qty=5)
    ])
    event_writer_mock.on_trading_order_cancelled.assert_not_called()


def test_order_buy_with_ioc_with_fulfilled(
        order_buy_basic_fixture,
        event_writer_mock
):
    """order_limit_buy 테스트."""
    # pylint: disable=redefined-outer-name

    trd_id = order_buy_basic_fixture['trd_id']
    trd = order_buy_basic_fixture['trd']
    curr = order_buy_basic_fixture['curr']
    cust_c = order_buy_basic_fixture['cust_c']

    trading_service = order_buy_basic_fixture['trading_service']
    item_count_service = order_buy_basic_fixture['item_count_service']
    balance_service = order_buy_basic_fixture['balance_service']

    #
    oid = trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(10), ItemQty(15),
        option=OrderOption.IMMEDIATE_OR_CANCEL)

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


def test_order_limit_buy_ioc_partial_match_cancel(
        order_buy_basic_fixture
):
    """order_limit_buy 테스트 + IoC + partial-match을 취소하기."""
    # pylint: disable=redefined-outer-name

    trd_id = order_buy_basic_fixture['trd_id']
    trd = order_buy_basic_fixture['trd']
    curr = order_buy_basic_fixture['curr']
    cust_c = order_buy_basic_fixture['cust_c']

    trading_service: TradingService = \
        order_buy_basic_fixture['trading_service']
    item_count_service: ItemCountService = \
        order_buy_basic_fixture['item_count_service']
    balance_service: BalanceService = \
        order_buy_basic_fixture['balance_service']

    #
    oid = trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(5), ItemQty(10),
        option=OrderOption.IMMEDIATE_OR_CANCEL)

    # the order really got cancelled?
    assert oid in trd.orders
    assert not trd.orders[oid].cancelled
    assert not trd.orders[oid].fulfilled

    # empty matches?
    assert len(trd.matches) == 1

    # item-count: only 5, not 10.
    assert item_count_service.get(cust_c, trd_id) == 5

    # balance-check?
    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) \
        == 1_000 - (10 * 5)  # all paid in advance.

    # CANCEL
    trading_service.cancel_remaining_offer(trd_id, oid)

    # AFTER
    assert trd.orders[oid].cancelled
    assert item_count_service.get(cust_c, trd_id) == 5
    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) \
        == 1_000 - (5 * 5)  # 5개 만큼만 매칭되어서, 나머지 환불됨.


def test_order_limit_buy_ioc_partial_rematch(
        order_buy_basic_fixture
):
    """order_limit_buy 테스트 + IoC + partial-match을 다시 매칭하기."""
    # pylint: disable=redefined-outer-name

    trd_id = order_buy_basic_fixture['trd_id']
    trd = order_buy_basic_fixture['trd']
    curr = order_buy_basic_fixture['curr']
    cust_c = order_buy_basic_fixture['cust_c']
    cust_x = CustomerId(999)

    trading_service: TradingService = \
        order_buy_basic_fixture['trading_service']
    item_count_service: ItemCountService = \
        order_buy_basic_fixture['item_count_service']
    balance_service: BalanceService = \
        order_buy_basic_fixture['balance_service']

    #
    oid = trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(5), ItemQty(10),
        option=OrderOption.IMMEDIATE_OR_CANCEL)

    # 부분만 매칭된 상황.
    assert not trd.orders[oid].fulfilled
    assert len(trd.matches) == 1

    # 새로운 판매로 매치 추가.
    trading_service.provide_item(trd_id, cust_x, ItemQty(100))

    trading_service.order_limit_sell(
        trd_id, cust_x, CurrencyAmt(3), ItemQty(10))

    # AFTER
    assert trd.orders[oid].fulfilled
    assert len(trd.matches) == 2  # 매칭됐네.
