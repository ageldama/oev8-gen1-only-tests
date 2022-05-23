"""oev8.svcs.trading.TradingService.order_limit_buy() 테스트."""
from unittest.mock import call
from pytest import fixture, raises  # type: ignore
from oev8.consts import SERVICE_CUSTOMER
from oev8.typedefs import CustomerId, CurrencyType, CurrencyAmt
from oev8.typedefs import TradingId, ItemQty
from oev8.typedefs import BalanceType, OrderOption
from oev8.svcs.trading import TradingService
from oev8.excs import TradingIsNotFound
from oev8.excs import TradingIsNotOpened
from oev8.excs import ItemQtyShouldBePositive
from oev8.excs import CurrencyAmtShouldBePositive
from oev8.excs import NotEnoughBalance
from oev8.values.event_writer import ItemCountXferToCauseBuying
from oev8.values.event_writer import BalanceXferFromCauseBuying
from test.testsup import assert_orderbook



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

    trading_service.order_limit_sell(
        trd_id, cust_a, CurrencyAmt(10), ItemQty(10))

    trading_service.order_limit_sell(
        trd_id, cust_b, CurrencyAmt(5), ItemQty(5))

    trading_service.order_limit_sell(
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
        'trading_service': trading_service,
        'item_count_service': trading_service.item_count_service,
        'balance_service': trading_service.balance_service,
    }


def assert_event_writer_not_called(event_writer_mock):
    "asserts no event_writer_mock interaction."
    event_writer_mock.on_item_count_xfer_to.assert_not_called()
    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_buy_order.assert_not_called()
    event_writer_mock.on_trading_order_matched.assert_not_called()


def reset_event_writer_mocks(event_writer_mock):
    "resets event_writer_mock."
    event_writer_mock.on_item_count_xfer_to.reset_mock()
    event_writer_mock.on_balance_xfer_from.reset_mock()
    event_writer_mock.on_trading_limit_buy_order.reset_mock()
    event_writer_mock.on_trading_order_matched.reset_mock()


def test_order_buy_simple_input_checks_01(
        order_buy_basic_fixture,
        event_writer_mock
):
    """order_buy 테스트: 입력 값 검증 위주."""
    # pylint: disable=redefined-outer-name
    trd_id = order_buy_basic_fixture['trd_id']
    trd_id_nf = order_buy_basic_fixture['trd_id_not_found']
    curr = order_buy_basic_fixture['curr']
    cust_c = order_buy_basic_fixture['cust_c']

    trd = order_buy_basic_fixture['trd']
    trading_service = order_buy_basic_fixture['trading_service']
    item_count_service = order_buy_basic_fixture['item_count_service']
    balance_service = order_buy_basic_fixture['balance_service']

    # trading_id 존재 하는 것이어야함.
    with raises(TradingIsNotFound):
        trading_service.order_limit_buy(
            trd_id_nf, cust_c, CurrencyAmt(1), ItemQty(1))

    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)

    assert balance_service.get(
        BalanceType.BALANCE, cust_c, curr) == 1_000  # no chg.

    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 17  # no chg.

    # qty >= 0.
    assert len(trd.buys) == 0

    with raises(ItemQtyShouldBePositive):
        trading_service.order_limit_buy(
            trd_id, cust_c, CurrencyAmt(1), ItemQty(-1))

    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)

    assert balance_service.get(
        BalanceType.BALANCE, cust_c, curr) == 1_000  # no chg.

    assert len(trd.buys) == 0

    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 17  # no chg.

    # price >= 0.
    with raises(CurrencyAmtShouldBePositive):
        trading_service.order_limit_buy(
            trd_id, cust_c, CurrencyAmt(-1), ItemQty(1))

    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)

    assert balance_service.get(
        BalanceType.BALANCE, cust_c, curr) == 1_000  # no chg.

    assert len(trd.buys) == 0

    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 17  # no chg.


def test_order_buy_only_with_opened_trading(
        order_buy_basic_fixture,
        event_writer_mock
):
    """order_buy 테스트: OPEN상태일때만."""
    # pylint: disable=redefined-outer-name
    trd_id = order_buy_basic_fixture['trd_id']
    curr = order_buy_basic_fixture['curr']
    cust_c = order_buy_basic_fixture['cust_c']

    trading_service = order_buy_basic_fixture['trading_service']
    balance_service = order_buy_basic_fixture['balance_service']

    # trading == OPEN 상태.
    trading_service.pause_trading(trd_id)

    with raises(TradingIsNotOpened):
        trading_service.order_limit_buy(
            trd_id, cust_c, CurrencyAmt(1), ItemQty(1))

    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)

    assert balance_service.get(
        BalanceType.BALANCE, cust_c, curr) == 1_000  # no chg.


def test_order_buy_not_enough_balance(
        order_buy_basic_fixture,
        event_writer_mock
):
    """order_buy 시 NotEnoughBalance 발생."""
    # pylint: disable=redefined-outer-name
    trd_id = order_buy_basic_fixture['trd_id']
    curr = order_buy_basic_fixture['curr']
    cust_c = order_buy_basic_fixture['cust_c']

    trading_service = order_buy_basic_fixture['trading_service']
    balance_service = order_buy_basic_fixture['balance_service']

    # -- 주문 금액이 부족하다면, 차감이 일어나서도, svc-cust에 이체가 되어서도 안됨.
    with raises(NotEnoughBalance):
        trading_service.order_limit_buy(
            trd_id, cust_c, CurrencyAmt(100), ItemQty(20))  # == 2_000

    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)

    assert balance_service.get(
        BalanceType.BALANCE, cust_c, curr) == 1_000  # no-chg.

    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 0  # no-chg.


def test_order_buy_basic_01(
        order_buy_basic_fixture,
        event_writer_mock
):
    """order_buy 테스트."""
    # pylint: disable=redefined-outer-name
    trd_id = order_buy_basic_fixture['trd_id']
    curr = order_buy_basic_fixture['curr']
    cust_c = order_buy_basic_fixture['cust_c']

    trading_service = order_buy_basic_fixture['trading_service']
    item_count_service = order_buy_basic_fixture['item_count_service']
    balance_service = order_buy_basic_fixture['balance_service']

    # (qty x price) 만큼 balance에서 차감한다. (trading.curr)
    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 0

    oid_4 = trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(11), ItemQty(20))

    assert balance_service.get(
        BalanceType.BALANCE, cust_c, curr) == 780  # 1000 - (20 * 11)

    # -- 차감해서 svc-cust에게 이체됨.
    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 220

    # 매칭에 성공한 수량만큼 cust의 item-count에 증가되어야 한다.
    assert item_count_service.get(cust_c, trd_id) == 15
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 2

    # -- 기존 가진 수량에 더해져야함. not overwritten.
    oid_5 = trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(20), ItemQty(1))

    assert item_count_service.get(cust_c, trd_id) == 16
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 1
    assert balance_service.get(
        BalanceType.BALANCE, cust_c, curr) == 780 - 20
    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 220 + 20

    # event_writer.
    event_writer_mock.on_trading_limit_buy_order.assert_has_calls([
        call(trd_id=trd_id, ord_id=oid_4, cust_id=cust_c, price=11, qty=20,
             option=OrderOption.NONE),
        call(trd_id=trd_id, ord_id=oid_5, cust_id=cust_c, price=20, qty=1,
             option=OrderOption.NONE)
    ])

    event_writer_mock.on_item_count_xfer_to.assert_has_calls([
        call(cust_id=cust_c, trd_id=trd_id,
             qty=5, new_qty=5, new_svc=12,
             why=ItemCountXferToCauseBuying(match_id=1)),
        call(cust_id=cust_c, trd_id=trd_id,
             qty=10, new_qty=15, new_svc=2,
             why=ItemCountXferToCauseBuying(match_id=2)),
        call(cust_id=cust_c, trd_id=trd_id,
             qty=1, new_qty=16, new_svc=1,
             why=ItemCountXferToCauseBuying(match_id=3))
    ])

    event_writer_mock.on_balance_xfer_from.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=cust_c, curr=curr, amt=220, new_amt=780, new_svc=220,
             why=BalanceXferFromCauseBuying(trd_id=trd_id, ord_id=oid_4)),
        call(balance_type=BalanceType.BALANCE,
             cust_id=cust_c, curr=curr, amt=20, new_amt=760, new_svc=240,
             why=BalanceXferFromCauseBuying(trd_id=trd_id, ord_id=oid_5))
    ])

    # 매칭 순서: 싼 sell부터 선택해서 oid_2이 oid_1보다 먼저 매칭됨.
    event_writer_mock.on_trading_order_matched.assert_has_calls([
        call(match_id=1, trd_id=trd_id,
             m_ord_id=2, t_ord_id=oid_4, t_cust_id=cust_c, price=11, qty=5),
        call(match_id=2, trd_id=trd_id,
             m_ord_id=1, t_ord_id=oid_4, t_cust_id=cust_c, price=11, qty=10),
        call(match_id=3, trd_id=trd_id,
             m_ord_id=3, t_ord_id=oid_5, t_cust_id=cust_c, price=20, qty=1)
    ])

    # 적절한 오더북 상태인지?
    # -- 정렬이 제대로 가능한지 (integer-keyed, sorted-dicts)
    trd = trading_service.tradings[trd_id]
    assert_orderbook(trd.buys)
    assert_orderbook(trd.sells)


def test_order_buy_cleans_orderbook_01(order_buy_basic_fixture):
    """order_buy 테스트: fulfilled 주문이 orderbook, price-set에서 사라지는지."""
    # pylint: disable=redefined-outer-name
    trd_id = order_buy_basic_fixture['trd_id']
    trd = order_buy_basic_fixture['trd']
    cust_c = order_buy_basic_fixture['cust_c']

    trading_service = order_buy_basic_fixture['trading_service']

    # -- 매칭된 주문은 오더북과 price-set에서 빠져야함.
    assert len(trd.buys) == 0  # 구매: 아직 5개 매칭 안됨.
    assert len(trd.sells) == 3  # 판매: 모두 매칭 됐으니까.

    # 5-qty / 5-amt을 소진시켜보자.
    buy_ord_id = trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(7), ItemQty(5))

    assert len(trd.buys) == 0  # 구매: 모두 소진.
    assert len(trd.sells) == 2  # 판매: 5-qty / 5-amt은 소진.

    # -- buy-qty->0이 될 때까지, 이 상태까지 매칭했다면, order.fulfilled<-True.
    buy_order = trd.orders[buy_ord_id]
    assert buy_order.fulfilled

    # buy-price >= sale-price인 오더들과 매칭.
    assert len(trd.sells) == 2  # 즉, amt=10, 15이 남음.
    assert len(trd.sells[10]) == 1
    assert len(trd.sells[15]) == 1

    # 남은 sell 모두 소진.
    trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(15), ItemQty(12))
    assert len(trd.buys) == 0  # 구매: 모두 소진.
    assert len(trd.sells) == 0  # 판매: 모두 소진.


def test_order_buy_cleans_orderbook_02(
        order_buy_basic_fixture
):
    """order_buy 테스트: fulfilled 주문이 orderbook, price-set에서 사라지는지,
    partial-match에 대해서는?"""
    # pylint: disable=redefined-outer-name
    trd_id = order_buy_basic_fixture['trd_id']
    trd = order_buy_basic_fixture['trd']
    cust_c = order_buy_basic_fixture['cust_c']

    trading_service = order_buy_basic_fixture['trading_service']

    # -- 매칭된 주문은 오더북과 price-set에서 빠져야함.
    assert len(trd.buys) == 0  # 구매: 아직 5개 매칭 안됨.
    assert len(trd.sells) == 3  # 판매: 모두 매칭 됐으니까.

    # 판매를 모두 소진시키고 구매는 partial으로 남기기.
    buy_ord_id = trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(30), ItemQty(20))

    assert len(trd.buys) == 1  # 구매: partially matched.
    remaining_qty = trd.buys[CurrencyAmt(30)][buy_ord_id]
    assert remaining_qty == 3

    buy_order = trd.orders[buy_ord_id]
    assert buy_order
    assert not buy_order.fulfilled
    assert not buy_order.cancelled
    assert buy_order.price == 30
    assert buy_order.qty == 20

    assert CurrencyAmt(30) in trd.buys

    assert len(trd.sells) == 0  # 판매: 모두 소진.


def test_order_buy_cheapest_first(order_buy_basic_fixture):
    """더 싼 sell부터 매칭."""
    # pylint: disable=redefined-outer-name
    trd_id = order_buy_basic_fixture['trd_id']
    trd = order_buy_basic_fixture['trd']
    cust_c = order_buy_basic_fixture['cust_c']

    trading_service = order_buy_basic_fixture['trading_service']

    # 구매 #1: 10-amt에 구매해서, 먼저 5-amt 전량 소진, 그리고 10-amt에서 부분 소진.
    buy_oid_1 = trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(10), ItemQty(7))

    assert trd.orders[buy_oid_1].fulfilled
    assert 5 not in trd.sells  # 5-amt은 전량 소진했음.
    assert 10 in trd.sells  # 10-amt 물량은 아직 남아있음.

    # 구매 #2: 10-amt에 구매해서, 그리고 10-amt 잔여 8-qty 소진.
    # -- sell중에서, partially matched되어 남은 잔여 수량과도 매칭이 되어야 한다.
    buy_oid_2 = trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(10), ItemQty(9))

    assert not trd.orders[buy_oid_2].fulfilled
    assert 10 not in trd.sells  # 10-amt 소진.


def test_order_buy_oldest_first(trading_service: TradingService):
    """같은 가격이면 먼저 제시된 sale부터."""
    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')
    cust_d = CustomerId('4')

    # setup
    trd = trading_service.start_new_trading(trd_id, curr)
    balance_service = trading_service.balance_service

    trading_service.provide_item(trd_id, cust_a, ItemQty(10))
    trading_service.provide_item(trd_id, cust_b, ItemQty(10))
    trading_service.provide_item(trd_id, cust_c, ItemQty(10))

    oid_1 = trading_service.order_limit_sell(
        trd_id, cust_a, CurrencyAmt(5), ItemQty(10))

    oid_2 = trading_service.order_limit_sell(
        trd_id, cust_b, CurrencyAmt(5), ItemQty(10))

    oid_3 = trading_service.order_limit_sell(
        trd_id, cust_c, CurrencyAmt(5), ItemQty(10))

    balance_service.deposit(BalanceType.BALANCE, cust_d, curr,
                            CurrencyAmt(1_000))

    #
    trading_service.order_limit_buy(
        trd_id, cust_d, CurrencyAmt(5), ItemQty(10))
    assert trd.orders[oid_1].fulfilled
    assert not trd.orders[oid_2].fulfilled
    assert not trd.orders[oid_3].fulfilled

    trading_service.order_limit_buy(
        trd_id, cust_d, CurrencyAmt(5), ItemQty(10))
    assert trd.orders[oid_1].fulfilled
    assert trd.orders[oid_2].fulfilled
    assert not trd.orders[oid_3].fulfilled

    trading_service.order_limit_buy(
        trd_id, cust_d, CurrencyAmt(5), ItemQty(10))
    assert trd.orders[oid_1].fulfilled
    assert trd.orders[oid_2].fulfilled
    assert trd.orders[oid_3].fulfilled


def test_order_buy_no_fulfilled_nor_cancelled(
        trading_service: TradingService
):
    """sell중에서, fulfilled 아니고 cancelled 아닌 항목과만 매칭이 이루어져야 한다."""
    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')
    cust_d = CustomerId('4')

    # setup
    trd = trading_service.start_new_trading(trd_id, curr)
    balance_service = trading_service.balance_service

    trading_service.provide_item(trd_id, cust_a, ItemQty(10))
    trading_service.provide_item(trd_id, cust_b, ItemQty(10))
    trading_service.provide_item(trd_id, cust_c, ItemQty(10))

    oid_1 = trading_service.order_limit_sell(
        trd_id, cust_a, CurrencyAmt(2), ItemQty(10))

    oid_2 = trading_service.order_limit_sell(
        trd_id, cust_b, CurrencyAmt(3), ItemQty(10))

    oid_3 = trading_service.order_limit_sell(
        trd_id, cust_c, CurrencyAmt(4), ItemQty(10))

    balance_service.deposit(BalanceType.BALANCE, cust_d, curr,
                            CurrencyAmt(1_000))

    # oid_1을 fulfill, fulfilled 된 것과는 매칭 안됨.
    assert not trd.orders[oid_1].fulfilled

    trading_service.order_limit_buy(
        trd_id, cust_d, CurrencyAmt(2), ItemQty(10))

    assert trd.orders[oid_1].fulfilled

    oid_cant_1 = trading_service.order_limit_buy(
        trd_id, cust_d, CurrencyAmt(2), ItemQty(10))

    assert trd.buys[CurrencyAmt(2)][oid_cant_1] \
        == trd.orders[oid_cant_1].qty  # 수량 그대로. 매칭 실패.

    # oid_2을 전체 취소. 매칭 안 되어야함.
    assert not trd.orders[oid_2].cancelled

    trading_service.cancel_remaining_offer(trd_id, oid_2)

    assert oid_2 not in trd.orders  # 전체 취소라 아예 사라짐.

    oid_cant_2 = trading_service.order_limit_buy(
        trd_id, cust_d, CurrencyAmt(3), ItemQty(10))

    assert trd.buys[CurrencyAmt(3)][oid_cant_2] \
        == trd.orders[oid_cant_2].qty  # 수량 그대로. 매칭 실패.

    # oid_3을 부분 매칭+취소 후 매칭 시도.
    assert not trd.orders[oid_3].cancelled and \
        not trd.orders[oid_3].fulfilled

    trading_service.order_limit_buy(
        trd_id, cust_d, CurrencyAmt(4), ItemQty(3))

    assert trd.orders[oid_3].qty == 10  # 최초 전체 수량.
    assert trd.sells[CurrencyAmt(4)][oid_3] == 7  # 현재 잔여 수량.

    trading_service.cancel_remaining_offer(trd_id, oid_3)
    assert trd.orders[oid_3].cancelled

    # 부분 취소 이후에는 오더북에는 없어도,
    assert CurrencyAmt(4) not in trd.sells \
        or oid_3 not in trd.sells[CurrencyAmt(4)]
    assert oid_3 in trd.orders  # 주문목록에는 아직 있음.

    oid_cant_3 = trading_service.order_limit_buy(
        trd_id, cust_d, CurrencyAmt(4), ItemQty(7))

    assert trd.buys[CurrencyAmt(4)][oid_cant_3] \
        == trd.orders[oid_cant_3].qty  # 수량 그대로. 매칭 실패.


def test_cancel_on_limit_buy_returns_balance_01(
        trading_service: TradingService,
        event_writer_mock
):
    """매칭 안 된 limit-buy 주문을 취소하면 잔액 돌려준다."""

    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_d = CustomerId('4')

    # setup
    trd = trading_service.start_new_trading(trd_id, curr)
    balance_service = trading_service.balance_service

    balance_service.deposit(BalanceType.BALANCE, cust_d, curr,
                            CurrencyAmt(1_000))

    oid = trading_service.order_limit_buy(
        trd_id, cust_d, CurrencyAmt(2), ItemQty(10))

    order = trd.orders[oid]

    # Before
    assert balance_service.get(BalanceType.BALANCE, cust_d, curr) == \
        1_000 - (2 * 10)

    assert not order.fulfilled
    assert not order.cancelled
    assert len(trd.matches) == 0

    trading_service.cancel_remaining_offer(trd_id, oid)

    # After
    assert order.cancelled
    assert balance_service.get(BalanceType.BALANCE, cust_d, curr) == 1_000

    event_writer_mock.on_trading_order_cancelled.assert_called_once()


def test_cancel_on_limit_buy_returns_balance_02(
        trading_service: TradingService
):
    """부분 매칭된 limit-buy 주문을 취소하면 잔액을 돌려준다."""

    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_d = CustomerId('4')

    # setup
    trd = trading_service.start_new_trading(trd_id, curr)
    balance_service = trading_service.balance_service

    trading_service.provide_item(trd_id, cust_a, ItemQty(10))

    oid_1 = trading_service.order_limit_sell(
        trd_id, cust_a, CurrencyAmt(2), ItemQty(5))

    balance_service.deposit(BalanceType.BALANCE, cust_d, curr,
                            CurrencyAmt(1_000))

    oid = trading_service.order_limit_buy(
        trd_id, cust_d, CurrencyAmt(2), ItemQty(10))

    order = trd.orders[oid]

    # Before
    assert balance_service.get(BalanceType.BALANCE, cust_d, curr) == \
        1_000 - (2 * 10)  # 가격 x 요청뮬량

    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 2 * 10

    assert not order.fulfilled
    assert not order.cancelled
    assert len(trd.matches) == 1

    trading_service.cancel_remaining_offer(trd_id, oid)

    # After
    assert order.cancelled
    assert balance_service.get(BalanceType.BALANCE, cust_d, curr) == \
        1_000 - (2 * 5)  # 가격 x 매칭물량

    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 2 * 5


def test_order_buy_partial_match(trading_service: TradingService):
    """limit-buy의 partial-match."""
    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')

    # setup
    trd = trading_service.start_new_trading(trd_id, curr)
    balance_service = trading_service.balance_service

    trading_service.provide_item(trd_id, cust_a, ItemQty(10))
    trading_service.provide_item(trd_id, cust_b, ItemQty(10))

    oid_1 = trading_service.order_limit_sell(
        trd_id, cust_a, CurrencyAmt(5), ItemQty(10))

    oid_2 = trading_service.order_limit_sell(
        trd_id, cust_b, CurrencyAmt(5), ItemQty(10))

    balance_service.deposit(BalanceType.BALANCE, cust_c, curr,
                            CurrencyAmt(1_000))

    # 30-qty -> 10-qty matching 안됨.
    oid_buy = trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(5), ItemQty(30))
    assert trd.orders[oid_1].fulfilled
    assert trd.orders[oid_2].fulfilled
    assert not trd.orders[oid_buy].fulfilled
