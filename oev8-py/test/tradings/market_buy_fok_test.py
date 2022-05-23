"""oev8.svcs.trading.TradingService.order_market_buy() + FoK 테스트."""
from unittest.mock import call, ANY
from pytest import fixture  # type: ignore
from oev8.consts import SERVICE_CUSTOMER
from oev8.typedefs import CustomerId, CurrencyType, CurrencyAmt
from oev8.typedefs import TradingId, ItemQty
from oev8.typedefs import BalanceType, OrderOption
from oev8.svcs.trading import TradingService
from oev8.values.event_writer import ItemCountXferToCauseBuying
from oev8.values.event_writer import TradingOrderCancelCauseFoK
from oev8.values.event_writer import BalanceXferFromCauseBuying


@fixture
def buy_fixture(trading_service: TradingService):
    """order_market_buy 기본 fixture."""
    trd_id = TradingId('1')
    trd_id_nf = TradingId('2')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')

    # setup
    trd = trading_service.start_new_trading(trd_id, curr)

    trading_service.provide_item(trd_id, cust_a, ItemQty(100))
    trading_service.provide_item(trd_id, cust_b, ItemQty(200))

    oid_1 = trading_service.order_limit_sell(
        trd_id, cust_a, CurrencyAmt(10), ItemQty(11))

    oid_2 = trading_service.order_limit_sell(
        trd_id, cust_b, CurrencyAmt(20), ItemQty(12))

    oid_3 = trading_service.order_limit_sell(
        trd_id, cust_b, CurrencyAmt(30), ItemQty(13))

    #
    return {
        'trd_id': trd_id,
        'trd_id_not_found': trd_id_nf,
        'curr': curr,
        'cust_a': cust_a,
        'cust_b': cust_b,
        'cust_c': cust_c,
        'oids': (oid_1, oid_2, oid_3),
        'trd': trd,
        'trading_service': trading_service,
        'item_count_service': trading_service.item_count_service,
        'balance_service': trading_service.balance_service,
    }


def test_order_market_buy_with_fok_cancels_with_no_match(
        trading_service: TradingService,
        event_writer_mock
):
    """order_market_buy + FoK 테스트: 매칭이 모두 되지 않았다면 아무 것도 하지 않고 취소."""
    # pylint: disable=redefined-outer-name

    trd_id = TradingId('1')
    curr = CurrencyType(1)
    trd = trading_service.start_new_trading(trd_id, curr)

    cust_c = CustomerId('1')

    item_count_service = trading_service.item_count_service
    balance_service = trading_service.balance_service

    #
    balance_service.deposit(BalanceType.BALANCE, cust_c, curr,
                            CurrencyAmt(1_000))

    oid = trading_service.order_market_buy(
        trd_id, cust_c, ItemQty(10),
        option=OrderOption.FILL_OR_KILL)

    # the order really got cancelled?
    assert oid not in trd.orders

    # empty matches?
    assert len(trd.matches) == 0

    # item-count
    assert item_count_service.get(cust_c, trd_id) == 0

    # balance-check: 잔고 되돌려 받아야함.
    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) == 1_000

    # event_writer.
    event_writer_mock.on_balance_xfer_from.assert_not_called()

    event_writer_mock.on_item_count_xfer_to.assert_not_called()

    event_writer_mock.on_trading_market_buy_order.assert_has_calls([
        call(trd_id=trd_id, ord_id=ANY, cust_id=cust_c, qty=10,
             option=OrderOption.FILL_OR_KILL)
    ])

    event_writer_mock.on_trading_order_matched.assert_not_called()

    event_writer_mock.on_trading_order_cancelled.assert_called_once()
    event_writer_mock.on_trading_order_cancelled.assert_has_calls([
        call(trd_id=trd_id, ord_id=ANY, cust_id=cust_c, price=ANY,
             qty=10, remaining_qty=10,
             why=TradingOrderCancelCauseFoK())
    ])


def test_order_market_buy_with_fok_with_partial_match(
        trading_service: TradingService,
        event_writer_mock
):
    """order_market_buy + FoK 테스트: partial matching만 있으면 취소."""
    # pylint: disable=redefined-outer-name

    trd_id = TradingId('1')
    curr = CurrencyType(1)
    trd = trading_service.start_new_trading(trd_id, curr)

    cust_a = CustomerId('1')
    cust_c = CustomerId('2')

    item_count_service = trading_service.item_count_service
    balance_service = trading_service.balance_service

    #
    trading_service.provide_item(trd_id, cust_a, ItemQty(1))

    trading_service.order_limit_sell(
        trd_id, cust_a, CurrencyAmt(5), ItemQty(1))

    #
    balance_service.deposit(BalanceType.BALANCE, cust_c, curr,
                            CurrencyAmt(1_000))

    oid = trading_service.order_market_buy(
        trd_id, cust_c, ItemQty(10),
        option=OrderOption.FILL_OR_KILL)

    # the order really got cancelled?
    assert oid not in trd.orders

    # empty matches?
    assert len(trd.matches) == 0

    # item-count
    assert item_count_service.get(cust_c, trd_id) == 0

    # balance-check: 잔고 되돌려 받아야함.
    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) == 1_000

    # event_writer.
    event_writer_mock.on_balance_xfer_from.assert_not_called()

    event_writer_mock.on_item_count_xfer_to.assert_not_called()

    event_writer_mock.on_trading_market_buy_order.assert_has_calls([
        call(trd_id=trd_id, ord_id=ANY, cust_id=cust_c, qty=10,
             option=OrderOption.FILL_OR_KILL)
    ])

    event_writer_mock.on_trading_order_matched.assert_not_called()

    event_writer_mock.on_trading_order_cancelled.assert_called_once()
    event_writer_mock.on_trading_order_cancelled.assert_has_calls([
        call(trd_id=trd_id, ord_id=ANY, cust_id=cust_c, price=ANY,
             qty=10, remaining_qty=10,
             why=TradingOrderCancelCauseFoK())
    ])


def test_order_market_buy_with_fok_fulfilled(
        trading_service: TradingService,
        event_writer_mock
):
    """order_market_buy + FoK 테스트: fulfilled일 때만 영향이 있음."""
    # pylint: disable=redefined-outer-name

    trd_id = TradingId('1')
    curr = CurrencyType(1)
    trd = trading_service.start_new_trading(trd_id, curr)

    cust_a = CustomerId('1')
    cust_c = CustomerId('2')

    item_count_service = trading_service.item_count_service
    balance_service = trading_service.balance_service

    #
    trading_service.provide_item(trd_id, cust_a, ItemQty(10))

    trading_service.order_limit_sell(
        trd_id, cust_a, CurrencyAmt(5), ItemQty(10))

    #
    balance_service.deposit(BalanceType.BALANCE, cust_c, curr,
                            CurrencyAmt(1_000))

    oid = trading_service.order_market_buy(
        trd_id, cust_c, ItemQty(10),
        option=OrderOption.FILL_OR_KILL)

    # the order really got cancelled?
    assert trd.orders[oid].fulfilled
    assert not trd.orders[oid].cancelled

    # empty matches?
    assert len(trd.matches) == 1

    # item-count
    assert item_count_service.get(cust_c, trd_id) == 10

    # balance-check?
    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) == \
        1_000 - (5 * 10)

    # event_writer.
    event_writer_mock.on_balance_xfer_from.assert_has_calls([
        call(balance_type=BalanceType.BALANCE, cust_id=cust_c, curr=curr,
             amt=50, new_amt=950, new_svc=50,
             why=BalanceXferFromCauseBuying(trd_id=trd_id, ord_id=ANY))
    ])

    event_writer_mock.on_item_count_xfer_to.assert_has_calls([
        call(cust_id=cust_c, trd_id=trd_id,
             qty=10, new_qty=10, new_svc=0,
             why=ItemCountXferToCauseBuying(match_id=ANY))
    ])

    event_writer_mock.on_trading_market_buy_order.assert_has_calls([
        call(trd_id=trd_id, ord_id=ANY, cust_id=cust_c, qty=10,
             option=OrderOption.FILL_OR_KILL)
    ])

    event_writer_mock.on_trading_order_matched.assert_has_calls([
        call(match_id=ANY, trd_id=trd_id, m_ord_id=ANY,
             t_ord_id=oid, t_cust_id=cust_c, price=5, qty=10)
    ])

    event_writer_mock.on_trading_order_cancelled.assert_not_called()
