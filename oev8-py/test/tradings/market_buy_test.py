"""oev8.svcs.trading.TradingService.order_market_buy() 테스트."""
from unittest.mock import call, ANY
from pytest import fixture, raises  # type: ignore
from oev8.consts import SERVICE_CUSTOMER
from oev8.typedefs import CustomerId, CurrencyType, CurrencyAmt
from oev8.typedefs import TradingId, ItemQty
from oev8.typedefs import BalanceType, OrderOption
from oev8.svcs.trading import TradingService
from oev8.excs import TradingIsNotFound
from oev8.excs import TradingIsNotOpened
from oev8.excs import ItemQtyShouldBePositive
from oev8.values.event_writer import ItemCountXferToCauseBuying
from oev8.values.event_writer import TradingOrderCancelCauseIoC
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


def assert_event_writer_not_called(event_writer_mock):
    "asserts no event_writer_mock interaction."
    event_writer_mock.on_item_count_xfer_to.assert_not_called()
    event_writer_mock.on_trading_market_buy_order.assert_not_called()
    event_writer_mock.on_trading_order_matched.assert_not_called()
    event_writer_mock.on_trading_order_cancelled.assert_not_called()


def reset_event_writer_mocks(event_writer_mock):
    "resets event_writer_mock."
    event_writer_mock.on_item_count_xfer_to.reset_mock()
    event_writer_mock.on_trading_market_buy_order.reset_mock()
    event_writer_mock.on_trading_order_matched.reset_mock()
    event_writer_mock.on_trading_order_cancelled.reset_mock()


def test_order_market_buy_simple_input_checks_01(
        buy_fixture,
        event_writer_mock
):
    """order_market_buy 테스트: 입력 값 검증 위주."""
    # pylint: disable=redefined-outer-name

    trd_id = buy_fixture['trd_id']
    trd_id_nf = buy_fixture['trd_id_not_found']
    cust_c = buy_fixture['cust_c']

    trd = buy_fixture['trd']
    trading_service = buy_fixture['trading_service']

    # trading_id 존재 하는 것이어야함.
    with raises(TradingIsNotFound):
        trading_service.order_market_buy(
            trd_id_nf, cust_c, ItemQty(1))

    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)

    # qty >= 0.
    with raises(ItemQtyShouldBePositive):
        trading_service.order_market_buy(
            trd_id, cust_c, ItemQty(-1))

    assert len(trd.buys) == 0
    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)


def test_order_market_buy_only_with_opened_trading(
        buy_fixture,
        event_writer_mock
):
    """order_market_buy 테스트: OPEN상태일때만."""
    # pylint: disable=redefined-outer-name

    trd_id = buy_fixture['trd_id']
    trd = buy_fixture['trd']
    cust_c = buy_fixture['cust_c']

    trading_service = buy_fixture['trading_service']

    # trading == OPEN 상태.
    trading_service.pause_trading(trd_id)

    with raises(TradingIsNotOpened):
        trading_service.order_market_buy(
            trd_id, cust_c, ItemQty(1))

    assert len(trd.buys) == 0
    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)


def test_order_buy_with_no_balance(
        buy_fixture,
        event_writer_mock
):
    """order_market_buy 시 Balance 금액 없으면 매칭도 없다."""
    # pylint: disable=redefined-outer-name

    trd_id = buy_fixture['trd_id']
    cust_c = buy_fixture['cust_c']

    trading_service = buy_fixture['trading_service']
    item_count_service = buy_fixture['item_count_service']

    # -- 구매 금액이 부족하다면, 매칭이 일어나면 안됨.
    oid = trading_service.order_market_buy(trd_id, cust_c, ItemQty(100))

    assert item_count_service.get(cust_c, trd_id) == 0

    event_writer_mock.on_item_count_xfer_to.assert_not_called()
    event_writer_mock.on_trading_order_matched.assert_not_called()
    event_writer_mock.on_trading_market_buy_order.assert_has_calls([
        call(trd_id=trd_id, ord_id=oid, cust_id=cust_c, qty=100,
             option=OrderOption.NONE)
    ])
    event_writer_mock.on_trading_order_cancelled.assert_has_calls([
        # 그리도 IoC 옵션이 없어도 기본으로 잔여 주문 취소.
        call(trd_id=trd_id, ord_id=oid, cust_id=cust_c, price=0,
             qty=100, remaining_qty=100,
             why=TradingOrderCancelCauseIoC())
    ])


def test_order_market_buy_fulfilled(
        buy_fixture,
        event_writer_mock
):
    """order_market_buy 테스트: fulfilled."""
    # pylint: disable=redefined-outer-name

    trd_id = buy_fixture['trd_id']
    trd = buy_fixture['trd']
    curr = buy_fixture['curr']
    oids = buy_fixture['oids']
    cust_c = buy_fixture['cust_c']

    trading_service = buy_fixture['trading_service']
    item_count_service = buy_fixture['item_count_service']
    balance_service = buy_fixture['balance_service']

    # qty만큼 item-count에서 증가할거라서.
    assert item_count_service.get(cust_c, trd_id) == 0

    # buy: fulfill될거임.
    balance_service.deposit(BalanceType.BALANCE, cust_c, curr,
                            CurrencyAmt(1_000))
    oid_6 = trading_service.order_market_buy(trd_id, cust_c, ItemQty(30))

    assert oid_6 in trd.orders
    order_6 = trd.orders[oid_6]
    assert not order_6.cancelled
    assert order_6.fulfilled

    assert item_count_service.get(cust_c, trd_id) == 30

    # -- 잔여량
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 6

    assert len(trd.matches) == 3

    assert trd.orders[oids[0]].fulfilled
    assert trd.orders[oids[1]].fulfilled
    assert not trd.orders[oids[2]].fulfilled

    # -- 매칭에 성공한만큼만 balance 사용.
    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) \
        == 1_000 - (10 * 11) - (20 * 12) - (30 * 7)

    assert balance_service.get(BalanceType.BALANCE, SERVICE_CUSTOMER, curr) \
        == (10 * 11) + (20 * 12) + (30 * 7)  # 수익금 이체 전.

    # event_writer.

    # fulfilled이니까 cancellation 필요 없음.
    event_writer_mock.on_trading_order_cancelled.assert_not_called()

    event_writer_mock.on_item_count_xfer_to.assert_has_calls([
        call(cust_id=cust_c, trd_id=trd_id, qty=11, new_qty=11, new_svc=25,
             why=ItemCountXferToCauseBuying(match_id=1)),
        call(cust_id=cust_c, trd_id=trd_id, qty=12, new_qty=23, new_svc=13,
             why=ItemCountXferToCauseBuying(match_id=2)),
        call(cust_id=cust_c, trd_id=trd_id, qty=7, new_qty=30, new_svc=6,
             why=ItemCountXferToCauseBuying(match_id=3))
    ])

    event_writer_mock.on_trading_market_buy_order.assert_has_calls([
        call(trd_id=trd_id, ord_id=oid_6, cust_id=cust_c, qty=30,
             option=OrderOption.NONE)
    ])

    event_writer_mock.on_trading_order_matched.assert_has_calls([
        call(match_id=1, trd_id=trd_id, m_ord_id=ANY, t_ord_id=oid_6,
             t_cust_id=cust_c, price=10, qty=11),  # 110
        call(match_id=2, trd_id=trd_id, m_ord_id=ANY, t_ord_id=oid_6,
             t_cust_id=cust_c, price=20, qty=12),  # 240
        call(match_id=3, trd_id=trd_id, m_ord_id=ANY, t_ord_id=oid_6,
             t_cust_id=cust_c, price=30, qty=7)    # 210
    ])  # 110 + 240 + 210 = 560

    event_writer_mock.on_balance_xfer_from.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=cust_c, curr=curr,
             amt=560, new_amt=1_000 - 560, new_svc=560,
             why=BalanceXferFromCauseBuying(trd_id=trd_id, ord_id=oid_6))
    ])


def test_order_market_buy_cannot_be_fulfilled_cuz_no_qty(
        buy_fixture,
        event_writer_mock
):
    """order_market_buy 테스트: 수량 부족으로 partial filled."""
    # pylint: disable=redefined-outer-name

    trd_id = buy_fixture['trd_id']
    trd = buy_fixture['trd']
    curr = buy_fixture['curr']
    oids = buy_fixture['oids']
    cust_c = buy_fixture['cust_c']

    trading_service = buy_fixture['trading_service']
    item_count_service = buy_fixture['item_count_service']
    balance_service = buy_fixture['balance_service']

    # qty만큼 item-count에서 증가할거라서.
    assert item_count_service.get(cust_c, trd_id) == 0

    # buy: fulfill될거임.
    balance_service.deposit(BalanceType.BALANCE, cust_c, curr,
                            CurrencyAmt(1_000_000))
    oid_6 = trading_service.order_market_buy(trd_id, cust_c, ItemQty(100))

    assert oid_6 in trd.orders
    order_6 = trd.orders[oid_6]
    assert not order_6.fulfilled
    assert order_6.cancelled  # fulfilled 되지 못했으니 자동 잔여량 취소.

    # 100개 구매 요청 --> 36개만 구매 --> 나머지 주문은 취소.
    assert item_count_service.get(cust_c, trd_id) == 36

    # -- 잔여량
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0

    assert len(trd.matches) == 3

    for oid in oids:
        assert trd.orders[oid].fulfilled

    # -- 매칭에 성공한만큼만 balance 사용.
    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) \
        == 1_000_000 - (10 * 11) - (20 * 12) - (30 * 13)

    # event_writer.
    event_writer_mock.on_trading_order_cancelled.assert_has_calls([
        call(trd_id=trd_id, ord_id=oid_6, cust_id=cust_c,
             price=0, qty=100, remaining_qty=100 - 36,
             why=TradingOrderCancelCauseIoC())
    ])

    event_writer_mock.on_item_count_xfer_to.assert_has_calls([
        call(cust_id=cust_c, trd_id=trd_id, qty=11, new_qty=11, new_svc=25,
             why=ItemCountXferToCauseBuying(match_id=1)),
        call(cust_id=cust_c, trd_id=trd_id, qty=12, new_qty=23, new_svc=13,
             why=ItemCountXferToCauseBuying(match_id=2)),
        call(cust_id=cust_c, trd_id=trd_id, qty=13, new_qty=36, new_svc=0,
             why=ItemCountXferToCauseBuying(match_id=3))
    ])

    event_writer_mock.on_trading_market_buy_order.assert_has_calls([
        call(trd_id=trd_id, ord_id=oid_6, cust_id=cust_c, qty=100,
             option=OrderOption.NONE)
    ])

    event_writer_mock.on_trading_order_matched.assert_has_calls([
        call(match_id=1, trd_id=trd_id, m_ord_id=ANY, t_ord_id=oid_6,
             t_cust_id=cust_c, price=10, qty=11),  # 110
        call(match_id=2, trd_id=trd_id, m_ord_id=ANY, t_ord_id=oid_6,
             t_cust_id=cust_c, price=20, qty=12),  # 240
        call(match_id=3, trd_id=trd_id, m_ord_id=ANY, t_ord_id=oid_6,
             t_cust_id=cust_c, price=30, qty=13)    # 390
    ])  # 110 + 240 + 390 = 740

    event_writer_mock.on_balance_xfer_from.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=cust_c, curr=curr,
             amt=740, new_amt=1_000_000 - 740, new_svc=740,
             why=BalanceXferFromCauseBuying(trd_id=trd_id, ord_id=oid_6))
    ])


def test_order_market_buy_cannot_be_fulfilled_cuz_no_balance_01(
        buy_fixture,
        event_writer_mock
):
    """order_market_buy 테스트: 계좌잔액 부족으로 partial filled."""
    # pylint: disable=redefined-outer-name

    trd = buy_fixture['trd']
    trd_id = buy_fixture['trd_id']
    curr = buy_fixture['curr']
    cust_c = buy_fixture['cust_c']

    trading_service = buy_fixture['trading_service']
    item_count_service = buy_fixture['item_count_service']
    balance_service = buy_fixture['balance_service']

    # qty만큼 item-count에서 증가할거라서.
    assert item_count_service.get(cust_c, trd_id) == 0

    # buy: partial-filled
    balance_service.deposit(BalanceType.BALANCE, cust_c, curr,
                            CurrencyAmt(25))
    ord_id = trading_service.order_market_buy(trd_id, cust_c, ItemQty(100))

    #
    order = trd.orders[ord_id]
    assert not order.fulfilled
    assert order.cancelled

    # 10-amt 짜리 2-qty 만 매칭됨.
    assert item_count_service.get(cust_c, trd_id) == 2

    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) \
        == CurrencyAmt(5)

    event_writer_mock.on_trading_order_cancelled.assert_called_once()

    event_writer_mock.on_trading_order_cancelled.assert_has_calls([
        call(trd_id=ANY, ord_id=ord_id, cust_id=ANY, price=ANY,
             qty=ANY, remaining_qty=ANY,
             why=TradingOrderCancelCauseIoC())
    ])


def test_order_market_buy_cannot_be_fulfilled_cuz_no_balance_02(
        buy_fixture,
        event_writer_mock
):
    """order_market_buy 테스트: 계좌잔액 부족으로 partial filled."""
    # pylint: disable=redefined-outer-name

    trd_id = buy_fixture['trd_id']
    curr = buy_fixture['curr']
    cust_c = buy_fixture['cust_c']

    trading_service = buy_fixture['trading_service']
    item_count_service = buy_fixture['item_count_service']
    balance_service = buy_fixture['balance_service']

    # qty만큼 item-count에서 증가할거라서.
    assert item_count_service.get(cust_c, trd_id) == 0

    # buy: partial-filled
    balance_service.deposit(BalanceType.BALANCE, cust_c, curr,
                            CurrencyAmt(9))
    trading_service.order_market_buy(trd_id, cust_c, ItemQty(100))

    # cannot be matched!
    assert item_count_service.get(cust_c, trd_id) == 0

    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) \
        == CurrencyAmt(9)

    event_writer_mock.on_trading_order_cancelled.assert_called_once()


def test_order_market_buy_no_match_no_spent(
        trading_service: TradingService,
        event_writer_mock
):
    """order_market_buy 테스트: 주문 filled 없으면 balance 사용도 없어야한다."""
    # pylint: disable=redefined-outer-name

    trd_id = TradingId('1')
    curr = CurrencyType(1)
    trd = trading_service.start_new_trading(trd_id, curr)
    cust_c = CustomerId('1')

    balance_service = trading_service.balance_service
    item_count_service = trading_service.item_count_service

    # buy: partial-filled
    balance_service.deposit(BalanceType.BALANCE, cust_c, curr,
                            CurrencyAmt(100))

    oid = trading_service.order_market_buy(trd_id, cust_c, ItemQty(100))

    #
    assert item_count_service.get(cust_c, trd_id) == 0  # 구매 못함.

    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) \
        == CurrencyAmt(100)

    # -- 시장가 주문은 오더북에 들어가면 안됨.
    assert len(trd.buys) == 0
    assert len(trd.sells) == 0

    # 매칭은 안 됐고,
    event_writer_mock.on_trading_order_matched.assert_not_called()

    # 그러니 바로 취소되어야 함. (시장가 주문)
    event_writer_mock.on_trading_order_cancelled.assert_called_once()

    event_writer_mock.on_trading_order_cancelled.assert_has_calls([
        call(trd_id=trd_id, ord_id=oid, cust_id=cust_c, price=0,
             qty=100, remaining_qty=100,
             why=TradingOrderCancelCauseIoC())
    ])


def test_order_market_buy_its_status_partial_filled(
        buy_fixture,
        event_writer_mock
):
    """order_market_buy 테스트: 주문 filled 상태에 따라 취소 여부. (partial)"""
    # pylint: disable=redefined-outer-name

    trd_id = buy_fixture['trd_id']
    trd = buy_fixture['trd']
    curr = buy_fixture['curr']
    cust_c = buy_fixture['cust_c']

    trading_service = buy_fixture['trading_service']
    balance_service = trading_service.balance_service
    item_count_service = trading_service.item_count_service

    # buy: partial-filled
    balance_service.deposit(BalanceType.BALANCE, cust_c, curr,
                            CurrencyAmt(25))

    oid = trading_service.order_market_buy(trd_id, cust_c, ItemQty(100))

    # 10-amt 짜리 2-qty 만 매칭됨.
    assert item_count_service.get(cust_c, trd_id) == 2

    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) \
        == CurrencyAmt(5)

    # -- 시장가 주문은 오더북에 들어가면 안됨.
    assert len(trd.buys) == 0
    assert len(trd.sells) == 3

    #
    assert not trd.orders[oid].fulfilled
    assert trd.orders[oid].cancelled  # partial-filled이므로 바로 취소됨.

    #
    event_writer_mock.on_trading_order_matched.assert_has_calls([
        call(match_id=1, trd_id=trd_id, m_ord_id=ANY, t_ord_id=oid,
             t_cust_id=ANY, price=10, qty=2)
    ])

    event_writer_mock.on_trading_order_cancelled.assert_has_calls([
        call(trd_id=trd_id, ord_id=oid, cust_id=cust_c, price=0, qty=100,
             remaining_qty=100 - 2, why=TradingOrderCancelCauseIoC())
    ])


def test_order_market_buy_its_status_fulfilled(
        buy_fixture,
        event_writer_mock
):
    """order_market_buy 테스트: 주문 filled 상태에 따라 취소 여부. (fulfilled)"""
    # pylint: disable=redefined-outer-name

    trd_id = buy_fixture['trd_id']
    trd = buy_fixture['trd']
    curr = buy_fixture['curr']
    cust_c = buy_fixture['cust_c']

    trading_service = buy_fixture['trading_service']
    balance_service = trading_service.balance_service
    item_count_service = trading_service.item_count_service

    # buy: partial-filled
    balance_service.deposit(BalanceType.BALANCE, cust_c, curr,
                            CurrencyAmt(25))

    oid = trading_service.order_market_buy(trd_id, cust_c, ItemQty(1))

    # 10-amt 짜리 1-qty 만 매칭됨.
    assert item_count_service.get(cust_c, trd_id) == 1

    assert balance_service.get(BalanceType.BALANCE, cust_c, curr) \
        == CurrencyAmt(15)

    # -- 시장가 주문은 오더북에 들어가면 안됨.
    assert len(trd.buys) == 0
    assert len(trd.sells) == 3

    #
    assert trd.orders[oid].fulfilled
    assert not trd.orders[oid].cancelled

    #
    event_writer_mock.on_trading_order_matched.assert_has_calls([
        call(match_id=1, trd_id=trd_id, m_ord_id=ANY, t_ord_id=oid,
             t_cust_id=ANY, price=10, qty=1)
    ])
    event_writer_mock.on_trading_order_cancelled.assert_not_called()


def test_order_market_buy_matches_cheapest_first(
        trading_service: TradingService
):
    """싸게 제시된 sell부터 matching."""
    # pylint: disable=redefined-outer-name

    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')
    cust_d = CustomerId('4')  # 구매자

    # setup
    balance_service = trading_service.balance_service
    trd = trading_service.start_new_trading(trd_id, curr)
    sell_oids = []

    for (idx, cust_id) in enumerate([cust_a, cust_b, cust_c]):
        trading_service.provide_item(trd_id, cust_id, ItemQty(5))
        oid = trading_service.order_limit_sell(
            trd_id, cust_id,
            CurrencyAmt(10 - idx), ItemQty(5))
        sell_oids.append(oid)

    balance_service.deposit(BalanceType.BALANCE, cust_d, curr,
                            CurrencyAmt(1_000))

    #
    trading_service.order_market_buy(trd_id, cust_d, ItemQty(5))

    assert not trd.orders[sell_oids[0]].fulfilled
    assert not trd.orders[sell_oids[1]].fulfilled
    assert trd.orders[sell_oids[2]].fulfilled  # 맨 마지막이 가장 싸니까.

    #
    trading_service.order_market_buy(trd_id, cust_d, ItemQty(5))

    assert not trd.orders[sell_oids[0]].fulfilled
    assert trd.orders[sell_oids[1]].fulfilled  # 그 다음으로 싼 가격.

    #
    trading_service.order_market_buy(trd_id, cust_d, ItemQty(5))

    assert trd.orders[sell_oids[0]].fulfilled


def test_order_market_buy_matches_oldest_first(
        trading_service: TradingService
):
    """같은 가격이면 먼저 제시된 sell부터 matching."""
    # pylint: disable=redefined-outer-name

    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')
    cust_d = CustomerId('4')

    # setup
    balance_service = trading_service.balance_service
    trd = trading_service.start_new_trading(trd_id, curr)
    sell_oids = []

    for cust_id in [cust_a, cust_b, cust_c]:
        trading_service.provide_item(trd_id, cust_id, ItemQty(5))
        oid = trading_service.order_limit_sell(
            trd_id, cust_id, CurrencyAmt(5), ItemQty(5))
        sell_oids.append(oid)

    balance_service.deposit(BalanceType.BALANCE, cust_d, curr, CurrencyAmt(51))

    #
    trading_service.order_market_buy(trd_id, cust_d, ItemQty(5))

    assert trd.orders[sell_oids[0]].fulfilled
    assert not trd.orders[sell_oids[1]].fulfilled
    assert not trd.orders[sell_oids[2]].fulfilled

    #
    trading_service.order_market_buy(trd_id, cust_d, ItemQty(2))

    assert not trd.orders[sell_oids[1]].fulfilled
    assert not trd.orders[sell_oids[2]].fulfilled

    #
    trading_service.order_market_buy(trd_id, cust_d, ItemQty(5))

    assert trd.orders[sell_oids[1]].fulfilled
    assert not trd.orders[sell_oids[2]].fulfilled

    #
    trading_service.order_market_buy(trd_id, cust_d, ItemQty(5))
    assert not trd.orders[sell_oids[2]].fulfilled


def test_order_market_buy_matches_no_cancelled_nor_fulfilled(
        trading_service: TradingService
):
    """sell중에서,  cancelled 아닌 항목과만 매칭이 이루어져야 한다."""
    # pylint: disable=redefined-outer-name

    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')
    cust_d = CustomerId('4')

    # setup
    balance_service = trading_service.balance_service
    trd = trading_service.start_new_trading(trd_id, curr)
    sell_oids = []

    for (idx, cust_id) in enumerate([cust_a, cust_b, cust_c]):
        trading_service.provide_item(trd_id, cust_id, ItemQty(5))
        oid = trading_service.order_limit_sell(
            trd_id, cust_id, CurrencyAmt(5 + idx), ItemQty(5))
        sell_oids.append(oid)

    balance_service.deposit(BalanceType.BALANCE, cust_d, curr,
                            CurrencyAmt(1_000))

    trading_service.cancel_remaining_offer(trd_id, sell_oids[0])

    # cancelled이랑은 매칭이 안되어야지.
    trading_service.order_market_buy(trd_id, cust_d, ItemQty(5))

    assert not sell_oids[0] in trd.orders  # 첫 번째는 취소했으니까.
    assert trd.orders[sell_oids[1]].fulfilled
    assert not trd.orders[sell_oids[2]].fulfilled

    # 두 번째와 매칭된 가격:
    assert balance_service.get(BalanceType.BALANCE, cust_d, curr) == \
        1_000 - (5 * 6)

    # fulfilled이랑도 매칭이 되면 안되지.
    trading_service.order_market_buy(trd_id, cust_d, ItemQty(5))

    # 세 번째와 매칭된 가격:
    assert balance_service.get(BalanceType.BALANCE, cust_d, curr) == \
        1_000 - (5 * 6) - (5 * 7)


def test_order_market_buy_matches_no_later_match(
        trading_service: TradingService
):
    """시장가 주문의 다음에 지정가 주문이 제출되어도 매칭되지 않는다."""
    # pylint: disable=redefined-outer-name

    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')

    # setup
    balance_service = trading_service.balance_service
    item_count_service = trading_service.item_count_service
    trd = trading_service.start_new_trading(trd_id, curr)

    # 시장가 주문 먼저.
    balance_service.deposit(BalanceType.BALANCE, cust_a, curr,
                            CurrencyAmt(1_000))

    oid_mkt = trading_service.order_market_buy(trd_id, cust_a, ItemQty(5))

    assert oid_mkt not in trd.orders

    # 지정가 주문.
    trading_service.provide_item(trd_id, cust_b, ItemQty(100))

    oid_lim = trading_service.order_limit_sell(
        trd_id, cust_b, CurrencyAmt(1), ItemQty(1))

    assert len(trd.matches) == 0

    #
    assert item_count_service.get(cust_a, trd_id) == 0  # 구매 못함.
    assert item_count_service.get(cust_b, trd_id) == 100 - 1  # 물량 올려놓은 상태.


def test_order_market_buy_matches_not_enough_balance(
        trading_service: TradingService,
        event_writer_mock
):
    """시장가 buy주문이 not-enough-balance으로 취소되는지."""
    # pylint: disable=redefined-outer-name

    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')

    # setup
    balance_service = trading_service.balance_service
    item_count_service = trading_service.item_count_service
    trd = trading_service.start_new_trading(trd_id, curr)

    # 지정가 주문 먼저.
    trading_service.provide_item(trd_id, cust_a, ItemQty(10))

    trading_service.order_limit_sell(
        trd_id, cust_a, CurrencyAmt(5), ItemQty(10))

    # 시장가 주문.
    balance_service.deposit(BalanceType.BALANCE, cust_b, curr,
                            CurrencyAmt(14))  # 2-qty 살 돈.
    # 잔여가 4-amt이니, 14/5=2.8, round(2.8)=3이니, 3-qty 가능.
    # 하지만 여기서는 round일어나면 안되니까, 확인.

    oid_mkt = trading_service.order_market_buy(trd_id, cust_b, ItemQty(10))

    # 잔여 물량이 있어도 잔액부족이고, market-buy이니까 취소되어야.
    assert oid_mkt in trd.orders
    assert trd.orders[oid_mkt].cancelled

    #
    assert balance_service.get(BalanceType.BALANCE, cust_b, curr) == 4
    assert balance_service.get(BalanceType.BALANCE,
                               SERVICE_CUSTOMER, curr) == 10
    assert item_count_service.get(cust_b, trd_id) == 2  # 구매 2-qty.
    assert item_count_service.get(cust_a, trd_id) == 0  # 물량 올려놓은 상태.

    #
    event_writer_mock.on_trading_order_cancelled.assert_called_once()


def test_order_market_buy_without_any_match(
        trading_service: TradingService,
        event_writer_mock
):
    """시장가 buy주문이 not-enough-balance으로 취소되는지."""
    # pylint: disable=redefined-outer-name

    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')

    # setup
    balance_service = trading_service.balance_service
    item_count_service = trading_service.item_count_service
    trd = trading_service.start_new_trading(trd_id, curr)

    # 시장가 주문.
    balance_service.deposit(BalanceType.BALANCE, cust_a, curr,
                            CurrencyAmt(11))

    oid_mkt = trading_service.order_market_buy(trd_id, cust_a, ItemQty(10))

    # 아무 매칭이 없었고, market-buy이니까 취소되어야.
    assert oid_mkt not in trd.orders

    #
    assert balance_service.get(BalanceType.BALANCE, cust_a, curr) == 11
    assert balance_service.get(BalanceType.BALANCE,
                               SERVICE_CUSTOMER, curr) == 0
    assert item_count_service.get(cust_a, trd_id) == 0

    #
    event_writer_mock.on_trading_order_cancelled.assert_called_once()
