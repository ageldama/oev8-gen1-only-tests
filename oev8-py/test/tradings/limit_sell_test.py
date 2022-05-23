"""oev8.svcs.trading.TradingService.order_limit_sell() 테스트."""
from unittest.mock import call
from pytest import fixture, raises  # type: ignore
from oev8.consts import SERVICE_CUSTOMER
from oev8.typedefs import CustomerId, CurrencyType, CurrencyAmt
from oev8.typedefs import TradingId, ItemQty, MatchId
from oev8.typedefs import BalanceType, OrderOption
from oev8.svcs.trading import TradingService
from oev8.excs import TradingIsNotFound
from oev8.excs import TradingIsNotOpened
from oev8.excs import ItemQtyShouldBePositive
from oev8.excs import CurrencyAmtShouldBePositive, NotEnoughItemCount
from oev8.values.event_writer import ItemCountXferFromCauseSelling
from oev8.values.event_writer import ItemCountXferToCauseBuying
from test.testsup import assert_orderbook


@fixture
def order_sell_basic_fixture(trading_service: TradingService):
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

    balance_service.deposit(BalanceType.BALANCE, cust_a, curr,
                            CurrencyAmt(1_000))

    balance_service.deposit(BalanceType.BALANCE, cust_b, curr,
                            CurrencyAmt(1_000))

    balance_service.deposit(BalanceType.BALANCE, cust_c, curr,
                            CurrencyAmt(1_000))

    oid_1 = trading_service.order_limit_buy(
        trd_id, cust_a, CurrencyAmt(10), ItemQty(23))

    oid_2 = trading_service.order_limit_buy(
        trd_id, cust_b, CurrencyAmt(9), ItemQty(22))

    oid_3 = trading_service.order_limit_buy(
        trd_id, cust_b, CurrencyAmt(8), ItemQty(21))

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


def assert_event_writer_not_called(event_writer_mock):
    "asserts no event_writer_mock interaction."
    event_writer_mock.on_item_count_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_sell_order.assert_not_called()
    event_writer_mock.on_trading_order_matched.assert_not_called()


def reset_event_writer_mocks(event_writer_mock):
    "resets event_writer_mock."
    event_writer_mock.on_item_count_xfer_from.reset_mock()
    event_writer_mock.on_trading_limit_sell_order.reset_mock()
    event_writer_mock.on_trading_order_matched.reset_mock()


def test_order_sell_simple_input_checks_01(
        order_sell_basic_fixture,
        event_writer_mock
):
    """order_buy 테스트: 입력 값 검증 위주."""
    # pylint: disable=redefined-outer-name
    trd_id = order_sell_basic_fixture['trd_id']
    trd_id_nf = order_sell_basic_fixture['trd_id_not_found']
    cust_c = order_sell_basic_fixture['cust_c']

    trd = order_sell_basic_fixture['trd']
    trading_service = order_sell_basic_fixture['trading_service']

    # trading_id 존재 하는 것이어야함.
    with raises(TradingIsNotFound):
        trading_service.order_limit_sell(
            trd_id_nf, cust_c, CurrencyAmt(1), ItemQty(1))

    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)

    # qty >= 0.
    with raises(ItemQtyShouldBePositive):
        trading_service.order_limit_sell(
            trd_id, cust_c, CurrencyAmt(1), ItemQty(-1))

    assert len(trd.sells) == 0
    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)

    # price >= 0.
    with raises(CurrencyAmtShouldBePositive):
        trading_service.order_limit_sell(
            trd_id, cust_c, CurrencyAmt(-1), ItemQty(1))

    assert len(trd.sells) == 0
    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)


def test_order_sell_only_with_opened_trading(
        order_sell_basic_fixture,
        event_writer_mock
):
    """order_sell 테스트: OPEN상태일때만."""
    # pylint: disable=redefined-outer-name
    trd_id = order_sell_basic_fixture['trd_id']
    trd = order_sell_basic_fixture['trd']
    cust_c = order_sell_basic_fixture['cust_c']

    trading_service = order_sell_basic_fixture['trading_service']

    # trading == OPEN 상태.
    trading_service.pause_trading(trd_id)

    with raises(TradingIsNotOpened):
        trading_service.order_limit_sell(
            trd_id, cust_c, CurrencyAmt(1), ItemQty(1))

    assert len(trd.sells) == 0
    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)


def test_order_sell_not_enough_item_count(
        order_sell_basic_fixture,
        event_writer_mock
):
    """order_sell 시 NotEnoughItemCount 발생."""
    # pylint: disable=redefined-outer-name
    trd_id = order_sell_basic_fixture['trd_id']
    cust_c = order_sell_basic_fixture['cust_c']

    trading_service = order_sell_basic_fixture['trading_service']
    item_count_service = order_sell_basic_fixture['item_count_service']

    # -- 주문 금액이 부족하다면, 차감이 일어나서도, svc-cust에 이체가 되어서도 안됨.
    with raises(NotEnoughItemCount):
        trading_service.order_limit_sell(
            trd_id, cust_c, CurrencyAmt(100), ItemQty(1))

    assert item_count_service.get(cust_c, trd_id) == 0

    assert item_count_service.get(
        SERVICE_CUSTOMER, trd_id) == 0  # no-chg.

    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)


def test_order_sell_basic_01(
        order_sell_basic_fixture,
        event_writer_mock
):
    """order_sell 테스트 기본 01."""
    # pylint: disable=redefined-outer-name
    trd_id = order_sell_basic_fixture['trd_id']
    curr = order_sell_basic_fixture['curr']
    cust_c = order_sell_basic_fixture['cust_c']

    trading_service = order_sell_basic_fixture['trading_service']
    item_count_service = order_sell_basic_fixture['item_count_service']
    balance_service = order_sell_basic_fixture['balance_service']

    # qty만큼 item-count에서 차감 -> svc-cust에 증가.
    # -- 그 수량만큼 갖고 있지 않다면, 차감이 일어나서도 안되고, svc-cust에 증가가 일어나서도 안됨.
    assert item_count_service.get(cust_c, trd_id) == 0

    with raises(NotEnoughItemCount):
        trading_service.order_limit_sell(
            trd_id, cust_c, CurrencyAmt(10), ItemQty(1))

    assert item_count_service.get(cust_c, trd_id) == 0
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0

    assert_event_writer_not_called(event_writer_mock)

    # qty 만큼 item_count에서 차감.
    trading_service.provide_item(trd_id, cust_c, ItemQty(10))

    with raises(NotEnoughItemCount):
        trading_service.order_limit_sell(
            trd_id, cust_c, CurrencyAmt(11), ItemQty(20))

    oid_6 = trading_service.order_limit_sell(
        trd_id, cust_c, CurrencyAmt(200), ItemQty(7))

    assert item_count_service.get(cust_c, trd_id) == 3

    # -- 차감해서 svc-cust에게 이체됨.
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 7

    oid_7 = trading_service.order_limit_sell(
        trd_id, cust_c, CurrencyAmt(3_000), ItemQty(1))

    assert item_count_service.get(cust_c, trd_id) == 2
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 8

    # -- 매칭에 성공한만큼 earnings 증가 아직 없음. (판매정산 이후에 이체)
    assert balance_service.get(BalanceType.EARNING, cust_c, curr) == 0

    oid_8 = trading_service.order_limit_sell(
        trd_id, cust_c, CurrencyAmt(15), ItemQty(1))

    assert balance_service.get(
        BalanceType.EARNING, cust_c, curr) == 0      # no-chg.

    # event_writer.
    event_writer_mock.on_item_count_xfer_from.assert_has_calls([
        call(cust_id=cust_c, trd_id=trd_id, qty=7, new_qty=3, new_svc=7,
             why=ItemCountXferFromCauseSelling(ord_id=oid_6)),
        call(cust_id=cust_c, trd_id=trd_id, qty=1, new_qty=2, new_svc=8,
             why=ItemCountXferFromCauseSelling(ord_id=oid_7)),
        call(cust_id=cust_c, trd_id=trd_id, qty=1, new_qty=1, new_svc=9,
             why=ItemCountXferFromCauseSelling(ord_id=oid_8))
    ])

    event_writer_mock.on_trading_limit_sell_order.assert_has_calls([
        call(trd_id=trd_id, ord_id=oid_6, cust_id=cust_c, price=200, qty=7,
             option=OrderOption.NONE),
        call(trd_id=trd_id, ord_id=oid_7, cust_id=cust_c, price=3000, qty=1,
             option=OrderOption.NONE),
        call(trd_id=trd_id, ord_id=oid_8, cust_id=cust_c, price=15, qty=1,
             option=OrderOption.NONE)
    ])

    event_writer_mock.on_trading_order_matched.assert_not_called()

    # 적절한 오더북 상태인지?
    # -- 정렬이 제대로 가능한지 (integer-keyed, sorted-dicts)
    trd = trading_service.tradings[trd_id]
    assert_orderbook(trd.buys)
    assert_orderbook(trd.sells)


def test_order_sell_cleans_orderbook_01(order_sell_basic_fixture):
    """order_sell 테스트: fulfilled 주문되면 orderbook, price-set에서 사라지는지."""
    # pylint: disable=redefined-outer-name
    trd_id = order_sell_basic_fixture['trd_id']
    trd = order_sell_basic_fixture['trd']
    cust_a = order_sell_basic_fixture['cust_a']
    cust_c = order_sell_basic_fixture['cust_c']

    trading_service = order_sell_basic_fixture['trading_service']

    trading_service.provide_item(trd_id, cust_c, ItemQty(100))

    # -- 매칭된 주문은 오더북과 price-set에서 빠져야함.
    assert len(trd.buys) == 3  # 구매: 기본 셋업.
    assert len(trd.sells) == 0  # 판매: 아직.

    # fulfilled 될 주문을 만들어보자.
    oid_ff = trading_service.order_limit_sell(
        trd_id, cust_c, CurrencyAmt(10), ItemQty(2))

    assert trd.orders[oid_ff].fulfilled  # fulfilled
    assert CurrencyAmt(10) not in trd.sells  # and gone.

    # -- 부분매칭은 냅둬.
    oid_p1 = trading_service.order_limit_sell(
        trd_id, cust_c, CurrencyAmt(10), ItemQty(23))

    assert not trd.orders[oid_p1].fulfilled  # not fulfilled
    assert CurrencyAmt(10) in trd.sells  # still there.

    # -- 잔여물량을 소진시키면,
    # buy중에서, partially matched되어 남은 잔여 수량과도 매칭이 되어야 한다.
    trading_service.order_limit_buy(
        trd_id, cust_a, CurrencyAmt(10), ItemQty(10))

    assert trd.orders[oid_p1].fulfilled  # now it's fulfilled
    assert CurrencyAmt(10) not in trd.sells  # and gone.


def test_order_sell_matches_with_highest_first(order_sell_basic_fixture):
    """더 비 싼 buy부터 매칭."""
    # pylint: disable=redefined-outer-name
    trd_id = order_sell_basic_fixture['trd_id']
    trd = order_sell_basic_fixture['trd']
    cust_a = order_sell_basic_fixture['cust_a']
    cust_b = order_sell_basic_fixture['cust_b']
    cust_c = order_sell_basic_fixture['cust_c']

    buy_oids = order_sell_basic_fixture['oids']

    trading_service = order_sell_basic_fixture['trading_service']
    item_count_service = order_sell_basic_fixture['item_count_service']

    trading_service.provide_item(trd_id, cust_c, ItemQty(100))

    # 판매 #1: 7-amt에, 먼저 {10-amt / 23-qty} 전량 소진.
    trading_service.order_limit_sell(
        trd_id, cust_c, CurrencyAmt(7), ItemQty(23))

    assert CurrencyAmt(10) not in trd.buys  # 먼저 모두 소진.
    assert CurrencyAmt(9) in trd.buys  # 나머지는 그대로.
    assert CurrencyAmt(8) in trd.buys

    assert item_count_service.get(cust_c, trd_id) == 100 - 23
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 23 - 23
    assert item_count_service.get(cust_a, trd_id) == 23
    assert item_count_service.get(cust_b, trd_id) == 0

    assert trd.orders[buy_oids[0]].fulfilled
    assert not trd.orders[buy_oids[1]].fulfilled
    assert not trd.orders[buy_oids[2]].fulfilled

    # 판매 #2: 7-amt에, 먼저 {9-amt / 22-qty} 전량 + {8-amt / 21-qty}에서 1개.
    trading_service.order_limit_sell(
        trd_id, cust_c, CurrencyAmt(7), ItemQty(23))

    assert CurrencyAmt(9) not in trd.buys  # gone
    assert CurrencyAmt(8) in trd.buys  # still there.

    assert item_count_service.get(cust_c, trd_id) == 100 - (23 * 2)
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0
    assert item_count_service.get(cust_a, trd_id) == 23
    assert item_count_service.get(cust_b, trd_id) == 22 + 1

    assert trd.orders[buy_oids[1]].fulfilled
    assert not trd.orders[buy_oids[2]].fulfilled

    # 판매 #3: 8-amt에, 먼저 남은 구매량 소진. (같은 가격 매칭)
    trading_service.order_limit_sell(
        trd_id, cust_c, CurrencyAmt(8), ItemQty(23))

    assert CurrencyAmt(8) not in trd.buys  # now it's gone!

    assert item_count_service.get(cust_c, trd_id) == 100 - (23 * 3)
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 3  # remain
    assert item_count_service.get(cust_a, trd_id) == 23
    assert item_count_service.get(cust_b, trd_id) == 23 + (21 - 1)

    assert trd.orders[buy_oids[2]].fulfilled


def test_order_sell_oldest_first(trading_service: TradingService):
    """같은 가격이면 먼저 제시된 buy부터."""
    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')
    cust_d = CustomerId('4')

    # setup
    balance_service = trading_service.balance_service
    trd = trading_service.start_new_trading(trd_id, curr)
    buy_oids = []

    for cust_id in [cust_a, cust_b, cust_c]:
        balance_service.deposit(BalanceType.BALANCE, cust_id, curr,
                                CurrencyAmt(1_000))
        oid = trading_service.order_limit_buy(
            trd_id, cust_id, CurrencyAmt(5), ItemQty(10))
        buy_oids.append(oid)

    trading_service.provide_item(trd_id, cust_d, ItemQty(100))

    #
    trading_service.order_limit_sell(
        trd_id, cust_d, CurrencyAmt(5), ItemQty(10))

    assert trd.orders[buy_oids[0]].fulfilled
    assert not trd.orders[buy_oids[1]].fulfilled
    assert not trd.orders[buy_oids[2]].fulfilled

    #
    trading_service.order_limit_sell(
        trd_id, cust_d, CurrencyAmt(5), ItemQty(10))

    assert trd.orders[buy_oids[1]].fulfilled
    assert not trd.orders[buy_oids[2]].fulfilled

    #
    trading_service.order_limit_sell(
        trd_id, cust_d, CurrencyAmt(5), ItemQty(10))

    assert trd.orders[buy_oids[2]].fulfilled


def test_order_sell_matches_on_no_cancelled_01(
        trading_service: TradingService
):
    """buy중에서,  cancelled 아닌 항목과만 매칭이 이루어져야 한다."""
    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')
    cust_d = CustomerId('4')

    # setup
    balance_service = trading_service.balance_service
    trd = trading_service.start_new_trading(trd_id, curr)
    buy_oids = []

    for cust_id in [cust_a, cust_b, cust_c]:
        balance_service.deposit(BalanceType.BALANCE, cust_id, curr,
                                CurrencyAmt(1_000))
        oid = trading_service.order_limit_buy(
            trd_id, cust_id, CurrencyAmt(5), ItemQty(10))
        buy_oids.append(oid)

    trading_service.provide_item(trd_id, cust_d, ItemQty(100))

    # oid #1을 부분 매칭 + cancel.
    trading_service.order_limit_sell(
        trd_id, cust_d, CurrencyAmt(5), ItemQty(7))

    trading_service.cancel_remaining_offer(trd_id, buy_oids[0])

    # 그리고 13-qty을 매칭 시도. --> {oid #2=fulfilled, oid #3=partially filled}
    trading_service.order_limit_sell(
        trd_id, cust_d, CurrencyAmt(5), ItemQty(13))

    assert trd.orders[buy_oids[1]].fulfilled
    assert not trd.orders[buy_oids[2]].fulfilled
    assert trd.buys[CurrencyAmt(5)][buy_oids[2]] < trd.orders[buy_oids[2]].qty


def test_order_sell_matches_on_no_cancelled_02(
        trading_service: TradingService
):
    """buy중에서,  cancelled 아닌 항목과만 매칭이 이루어져야 한다."""
    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')

    # setup
    balance_service = trading_service.balance_service
    trd = trading_service.start_new_trading(trd_id, curr)
    buy_oids = []

    for cust_id in [cust_a, cust_b]:
        balance_service.deposit(BalanceType.BALANCE, cust_id, curr,
                                CurrencyAmt(1_000))
        oid = trading_service.order_limit_buy(
            trd_id, cust_id, CurrencyAmt(5), ItemQty(10))
        buy_oids.append(oid)

    trading_service.provide_item(trd_id, cust_c, ItemQty(100))

    # oid #1을 전체 취소.
    trading_service.cancel_remaining_offer(trd_id, buy_oids[0])

    # 20개 판매: 10개만 매칭. (전체 20개 구매 중 10개는 취소했으니까)
    sell_oid = trading_service.order_limit_sell(
        trd_id, cust_c, CurrencyAmt(5), ItemQty(20))

    assert buy_oids[0] not in trd.orders
    assert trd.orders[buy_oids[1]].fulfilled
    assert trd.sells[CurrencyAmt(5)][sell_oid] < trd.orders[sell_oid].qty
    assert trd.sells[CurrencyAmt(5)][sell_oid] == 10


def test_order_sell_matching_calls_event_writer(
        trading_service: TradingService,
        event_writer_mock
):
    """매칭이 있을 때 event_writer_mock을 호출."""
    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')

    # setup
    balance_service = trading_service.balance_service
    trading_service.start_new_trading(trd_id, curr)

    buy_oids = []
    for cust_id in [cust_a, cust_b]:
        balance_service.deposit(BalanceType.BALANCE, cust_id, curr,
                                CurrencyAmt(1_000))
        oid = trading_service.order_limit_buy(
            trd_id, cust_id, CurrencyAmt(5), ItemQty(10))
        buy_oids.append(oid)

    trading_service.provide_item(trd_id, cust_c, ItemQty(100))

    # 13개 판매 + 매칭.
    sell_oid_1 = trading_service.order_limit_sell(
        trd_id, cust_c, CurrencyAmt(4), ItemQty(13))

    # 5개 판매 + 매칭.
    sell_oid_2 = trading_service.order_limit_sell(
        trd_id, cust_c, CurrencyAmt(2), ItemQty(5))

    # event_writer.
    event_writer_mock.on_item_count_xfer_to.assert_has_calls([
        call(cust_id=cust_a, trd_id=trd_id,
             qty=10, new_qty=10, new_svc=3,
             why=ItemCountXferToCauseBuying(match_id=MatchId(1))),
        call(cust_id=cust_b, trd_id=trd_id,
             qty=3, new_qty=3, new_svc=0,
             why=ItemCountXferToCauseBuying(match_id=MatchId(2))),
        # order_sell + svc-acct에 올리자마자 매칭 됐으니 new_svc=0.
        call(cust_id=cust_b, trd_id=trd_id,
             qty=5, new_qty=8, new_svc=0,
             why=ItemCountXferToCauseBuying(match_id=MatchId(3)))
    ])

    event_writer_mock.on_trading_order_matched.assert_has_calls([
        call(match_id=1, trd_id=trd_id,
             m_ord_id=buy_oids[0], t_ord_id=sell_oid_1,
             t_cust_id=cust_c,
             price=5, qty=10),
        call(match_id=2, trd_id=trd_id,
             m_ord_id=buy_oids[1], t_ord_id=sell_oid_1,
             t_cust_id=cust_c,
             price=5, qty=3),
        call(match_id=3, trd_id=trd_id,
             m_ord_id=buy_oids[1], t_ord_id=sell_oid_2,
             t_cust_id=cust_c,
             price=5, qty=5)
    ])


def test_order_sell_partial_matching(
        trading_service: TradingService,
        event_writer_mock
):
    """partial matching만 있는 limit-sell."""
    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')

    # setup
    balance_service = trading_service.balance_service
    trading_service.start_new_trading(trd_id, curr)

    buy_oids = []
    for cust_id in [cust_a, cust_b]:
        balance_service.deposit(BalanceType.BALANCE, cust_id, curr,
                                CurrencyAmt(1_000))
        oid = trading_service.order_limit_buy(
            trd_id, cust_id, CurrencyAmt(5), ItemQty(10))
        buy_oids.append(oid)

    # 100개 판매 --> 20개만 매칭.
    trading_service.provide_item(trd_id, cust_c, ItemQty(100))

    sell_oid = trading_service.order_limit_sell(
        trd_id, cust_c, CurrencyAmt(4), ItemQty(100))

    # 잔여상태
    trd = trading_service.tradings[trd_id]
    sell_order = trd.orders[sell_oid]
    assert sell_order is not None
    assert not sell_order.cancelled
    assert not sell_order.fulfilled


def test_cancel_on_limit_sell_returns_item_count_01(
        trading_service: TradingService,
        event_writer_mock
):
    """매칭 안 된 limit-sell 주문을 취소하면 아이템을 전부 되돌려준다."""

    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')

    item_count_service = trading_service.item_count_service

    trading_service.start_new_trading(trd_id, curr)

    trading_service.provide_item(trd_id, cust_a, ItemQty(100))

    oid = trading_service.order_limit_sell(
        trd_id, cust_a, CurrencyAmt(5), ItemQty(10))

    # Before
    assert item_count_service.get(cust_a, trd_id) == 100 - 10
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 10

    #
    trading_service.cancel_remaining_offer(trd_id, oid)

    # After
    assert item_count_service.get(cust_a, trd_id) == 100
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0

    event_writer_mock.on_trading_order_cancelled.assert_called_once()


def test_cancel_on_limit_sell_returns_item_count_02(
        trading_service: TradingService
):
    """부분 매칭 된 limit-sell 주문을 취소하면 남은 아이템을 되돌려준다."""

    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')

    item_count_service = trading_service.item_count_service
    balance_service = trading_service.balance_service

    trading_service.start_new_trading(trd_id, curr)

    balance_service.deposit(BalanceType.BALANCE, cust_a,
                            curr, CurrencyAmt(100))

    trading_service.provide_item(trd_id, cust_b, ItemQty(100))

    oid_sell = trading_service.order_limit_sell(
        trd_id, cust_b, CurrencyAmt(5), ItemQty(10))

    trading_service.order_limit_buy(
        trd_id, cust_a, CurrencyAmt(5), ItemQty(2))

    # Before
    assert item_count_service.get(cust_a, trd_id) == 2  # 구매
    assert item_count_service.get(cust_b, trd_id) == 100 - 10  # 판매
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 10 - 2

    #
    trading_service.cancel_remaining_offer(trd_id, oid_sell)

    # After
    assert item_count_service.get(cust_a, trd_id) == 2  # 구매: 그대로.
    # 판매: 매칭된 것 빼고 돌려받음.
    assert item_count_service.get(cust_b, trd_id) == 100 - 2
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0
