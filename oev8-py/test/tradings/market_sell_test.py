"""oev8.svcs.trading.TradingService.order_market_sell() 테스트."""
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
from oev8.excs import NotEnoughItemCount
from oev8.values.event_writer import ItemCountXferFromCauseSelling
from oev8.values.event_writer import ItemCountXferToCauseBuying
from oev8.values.event_writer import TradingOrderCancelCauseIoC


@fixture
def sell_fixture(trading_service: TradingService):
    """order_market_sell 기본 fixture."""
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
        'oids': (oid_1, oid_2, oid_3),
        'trd': trd,
        'trading_service': trading_service,
        'item_count_service': trading_service.item_count_service,
        'balance_service': trading_service.balance_service,
    }


def assert_event_writer_not_called(event_writer_mock):
    "asserts no event_writer_mock interaction."
    event_writer_mock.on_item_count_xfer_from.assert_not_called()
    event_writer_mock.on_trading_market_sell_order.assert_not_called()
    event_writer_mock.on_trading_order_matched.assert_not_called()
    event_writer_mock.on_trading_order_cancelled.assert_not_called()


def reset_event_writer_mocks(event_writer_mock):
    "resets event_writer_mock."
    event_writer_mock.on_item_count_xfer_from.reset_mock()
    event_writer_mock.on_trading_market_sell_order.reset_mock()
    event_writer_mock.on_trading_order_matched.reset_mock()
    event_writer_mock.on_trading_order_cancelled.reset_mock()


def test_order_market_sell_simple_input_checks_01(
        sell_fixture,
        event_writer_mock
):
    """order_market_sell 테스트: 입력 값 검증 위주."""
    # pylint: disable=redefined-outer-name
    trd_id = sell_fixture['trd_id']
    trd_id_nf = sell_fixture['trd_id_not_found']
    cust_c = sell_fixture['cust_c']

    trd = sell_fixture['trd']
    trading_service = sell_fixture['trading_service']

    # trading_id 존재 하는 것이어야함.
    with raises(TradingIsNotFound):
        trading_service.order_market_sell(
            trd_id_nf, cust_c, ItemQty(1))

    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)

    # qty >= 0.
    with raises(ItemQtyShouldBePositive):
        trading_service.order_market_sell(
            trd_id, cust_c, ItemQty(-1))

    assert len(trd.sells) == 0
    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)


def test_order_market_sell_only_with_opened_trading(
        sell_fixture,
        event_writer_mock
):
    """order_market_sell 테스트: OPEN상태일때만."""
    # pylint: disable=redefined-outer-name

    trd_id = sell_fixture['trd_id']
    trd = sell_fixture['trd']
    cust_c = sell_fixture['cust_c']

    trading_service = sell_fixture['trading_service']

    # trading == OPEN 상태.
    trading_service.pause_trading(trd_id)

    with raises(TradingIsNotOpened):
        trading_service.order_market_sell(
            trd_id, cust_c, ItemQty(1))

    assert len(trd.sells) == 0
    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)


def test_order_sell_not_enough_item_count(
        sell_fixture,
        event_writer_mock
):
    """order_market_sell 시 NotEnoughItemCount 발생."""
    # pylint: disable=redefined-outer-name

    trd_id = sell_fixture['trd_id']
    cust_c = sell_fixture['cust_c']

    trading_service = sell_fixture['trading_service']
    item_count_service = sell_fixture['item_count_service']

    # -- 주문 금액이 부족하다면, 차감이 일어나서도, svc-cust에 이체가 되어서도 안됨.
    with raises(NotEnoughItemCount):
        trading_service.order_market_sell(
            trd_id, cust_c, ItemQty(1))

    assert item_count_service.get(cust_c, trd_id) == 0

    assert item_count_service.get(
        SERVICE_CUSTOMER, trd_id) == 0  # no-chg.

    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)


def test_order_sell_basic_fulfilled(
        sell_fixture,
        event_writer_mock
):
    """order_sell 테스트 기본 01."""
    # pylint: disable=redefined-outer-name

    trd_id = sell_fixture['trd_id']
    trd = sell_fixture['trd']
    curr = sell_fixture['curr']
    oids = sell_fixture['oids']
    cust_a = sell_fixture['cust_a']
    cust_b = sell_fixture['cust_b']
    cust_c = sell_fixture['cust_c']

    trading_service = sell_fixture['trading_service']
    item_count_service = sell_fixture['item_count_service']
    balance_service = sell_fixture['balance_service']

    # qty만큼 item-count에서 차감 -> svc-cust에 증가.
    # -- 그 수량만큼 갖고 있지 않다면, 차감이 일어나서도 안되고, svc-cust에 증가가 일어나서도 안됨.
    assert item_count_service.get(cust_c, trd_id) == 0

    with raises(NotEnoughItemCount):
        trading_service.order_market_sell(
            trd_id, cust_c, ItemQty(1))

    assert item_count_service.get(cust_c, trd_id) == 0
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0

    assert_event_writer_not_called(event_writer_mock)

    # qty 만큼 item_count에서 차감.
    trading_service.provide_item(trd_id, cust_c, ItemQty(50))

    with raises(NotEnoughItemCount):
        trading_service.order_market_sell(
            trd_id, cust_c, ItemQty(5_000))

    oid_6 = trading_service.order_market_sell(trd_id, cust_c, ItemQty(50))

    assert item_count_service.get(cust_c, trd_id) == 0

    # -- 모두 팔렸음.
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0

    assert oid_6 in trd.orders
    order_6 = trd.orders[oid_6]
    assert not order_6.cancelled
    assert order_6.fulfilled

    assert len(trd.matches) == 3

    assert trd.orders[oids[0]].fulfilled
    assert trd.orders[oids[1]].fulfilled
    assert not trd.orders[oids[2]].fulfilled

    # 구매량.
    assert item_count_service.get(cust_a, trd_id) == 23
    assert item_count_service.get(cust_b, trd_id) == 27  # from oid_2 and oid3

    # -- 매칭에 성공한만큼 earnings 증가 아직 없음. (판매정산 이후에 이체)
    assert balance_service.get(BalanceType.EARNING, cust_c, curr) == 0

    # event_writer.

    # fulfilled 되면 취소 안함.
    event_writer_mock.on_trading_order_cancelled.assert_not_called()

    event_writer_mock.on_item_count_xfer_from.assert_has_calls([
        call(cust_id=cust_c, trd_id=trd_id, qty=50, new_qty=0, new_svc=50,
             why=ItemCountXferFromCauseSelling(ord_id=oid_6))
    ])

    event_writer_mock.on_item_count_xfer_to.assert_has_calls([
        call(cust_id=cust_a, trd_id=trd_id, qty=23, new_qty=23, new_svc=27,
             why=ItemCountXferToCauseBuying(match_id=1)),
        call(cust_id=cust_b, trd_id=trd_id, qty=22, new_qty=22, new_svc=5,
             why=ItemCountXferToCauseBuying(match_id=2)),
        call(cust_id=cust_b, trd_id=trd_id, qty=5, new_qty=27, new_svc=0,
             why=ItemCountXferToCauseBuying(match_id=3))
    ])

    event_writer_mock.on_trading_market_sell_order.assert_has_calls([
        call(trd_id=trd_id, ord_id=oid_6, cust_id=cust_c, qty=50,
             option=OrderOption.NONE)
    ])

    event_writer_mock.on_trading_order_matched.assert_has_calls([
        # buy측 가격을 따름을 확인.
        call(match_id=1, trd_id=trd_id, m_ord_id=oids[0],
             t_ord_id=oid_6, t_cust_id=cust_c,
             price=10, qty=23),
        call(match_id=2, trd_id=trd_id, m_ord_id=oids[1],
             t_ord_id=oid_6, t_cust_id=cust_c,
             price=9, qty=22),
        call(match_id=3, trd_id=trd_id, m_ord_id=oids[2],
             t_ord_id=oid_6, t_cust_id=cust_c,
             price=8, qty=5)
    ])


def test_order_market_sell_its_status_01(
        sell_fixture,
        event_writer_mock
):
    """order_market_sell 테스트: 주문 filled 상태에 따라 취소 여부."""
    # pylint: disable=redefined-outer-name

    trd_id = sell_fixture['trd_id']
    trd = sell_fixture['trd']
    cust_c = sell_fixture['cust_c']

    trading_service = sell_fixture['trading_service']

    trading_service.provide_item(trd_id, cust_c, ItemQty(10_000))

    # -- 시장가 주문은 오더북에 들어가면 안됨.
    assert len(trd.buys) == 3  # 구매: 기본 셋업.
    assert len(trd.sells) == 0  # 판매: 아직.

    # fulfilled 될 주문을 만들어보자.
    oid_ff = trading_service.order_market_sell(trd_id, cust_c, ItemQty(2))

    assert trd.orders[oid_ff].fulfilled
    assert not trd.orders[oid_ff].cancelled
    assert len(trd.sells) == 0

    event_writer_mock.on_trading_order_matched.assert_has_calls([
        call(match_id=1, trd_id=trd_id, m_ord_id=ANY, t_ord_id=oid_ff,
             t_cust_id=ANY, price=10, qty=2)
    ])
    event_writer_mock.on_trading_order_cancelled.assert_not_called()
    event_writer_mock.on_trading_order_matched.reset_mock()
    event_writer_mock.on_trading_order_cancelled.reset_mock()

    # -- 부분매칭은 자동으로 취소된다.
    oid_p1 = trading_service.order_market_sell(trd_id, cust_c, ItemQty(2_000))

    assert not trd.orders[oid_p1].fulfilled
    assert trd.orders[oid_p1].cancelled
    assert len(trd.sells) == 0

    event_writer_mock.on_trading_order_matched.assert_has_calls([
        # 가격 비싼 순서부터 매칭되었음을 확인.
        call(match_id=ANY, trd_id=trd_id, m_ord_id=ANY, t_ord_id=oid_p1,
             t_cust_id=cust_c, price=10, qty=21),
        call(match_id=ANY, trd_id=trd_id, m_ord_id=ANY, t_ord_id=oid_p1,
             t_cust_id=cust_c, price=9, qty=22),
        call(match_id=ANY, trd_id=trd_id, m_ord_id=ANY, t_ord_id=oid_p1,
             t_cust_id=cust_c, price=8, qty=21)
    ])

    # 부분매칭 --> 나머지는 취소.
    event_writer_mock.on_trading_order_cancelled.assert_called_once()
    event_writer_mock.on_trading_order_cancelled.assert_has_calls([
        call(trd_id=trd_id, ord_id=oid_p1, cust_id=cust_c,
             price=0, qty=2_000,
             remaining_qty=ANY, why=TradingOrderCancelCauseIoC())
    ])


def test_order_market_sell_matches_oldest_first(
        trading_service: TradingService
):
    """같은 가격이면 먼저 제시된 buy부터 matching."""
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
    buy_oids = []

    for cust_id in [cust_a, cust_b, cust_c]:
        balance_service.deposit(BalanceType.BALANCE, cust_id, curr,
                                CurrencyAmt(1_000))
        oid = trading_service.order_limit_buy(
            trd_id, cust_id, CurrencyAmt(5), ItemQty(10))
        buy_oids.append(oid)

    #
    trading_service.provide_item(trd_id, cust_d, ItemQty(100))

    trading_service.order_market_sell(
        trd_id, cust_d, ItemQty(25))

    assert trd.orders[buy_oids[0]].fulfilled
    assert trd.orders[buy_oids[1]].fulfilled
    assert not trd.orders[buy_oids[2]].fulfilled

    #
    trading_service.order_market_sell(
        trd_id, cust_d, ItemQty(5))

    assert trd.orders[buy_oids[2]].fulfilled


def test_order_market_sell_matches_highest_buy_first(
        trading_service: TradingService
):
    """비싸게 사려는 buy부터 matching."""
    # pylint: disable=redefined-outer-name

    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')  # 구매자들
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')
    cust_d = CustomerId('4')  # 판매자

    # setup
    balance_service = trading_service.balance_service
    trd = trading_service.start_new_trading(trd_id, curr)
    buy_oids = []

    # 뒷 쪽 주문으로 갈수록 더 비싸진다.
    for (idx, cust_id) in enumerate([cust_a, cust_b, cust_c]):
        balance_service.deposit(BalanceType.BALANCE, cust_id, curr,
                                CurrencyAmt(1_000))
        oid = trading_service.order_limit_buy(
            trd_id, cust_id, CurrencyAmt(5 + idx), ItemQty(5))
        buy_oids.append(oid)

    #
    trading_service.provide_item(trd_id, cust_d, ItemQty(100))

    trading_service.order_market_sell(trd_id, cust_d, ItemQty(5))

    assert not trd.orders[buy_oids[0]].fulfilled
    assert not trd.orders[buy_oids[1]].fulfilled
    assert trd.orders[buy_oids[2]].fulfilled  # 맨 뒤쪽부터 처리.

    #
    trading_service.order_market_sell(trd_id, cust_d, ItemQty(5))

    assert not trd.orders[buy_oids[0]].fulfilled
    assert trd.orders[buy_oids[1]].fulfilled  # 그 다음.

    # 마지막.
    trading_service.order_market_sell(trd_id, cust_d, ItemQty(5))

    assert trd.orders[buy_oids[0]].fulfilled


def test_order_market_sell_no_match_will_be_cancelled(
        trading_service: TradingService,
        event_writer_mock
):
    """매칭이 없으면 바로 취소."""

    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')

    # setup
    trd = trading_service.start_new_trading(trd_id, curr)

    # 매칭 불가 주문.
    trading_service.provide_item(trd_id, cust_a, ItemQty(100))

    oid = trading_service.order_market_sell(
        trd_id, cust_a, ItemQty(1))

    # 취소됨.
    event_writer_mock.on_trading_order_cancelled.assert_has_calls([
        call(trd_id=trd_id, ord_id=ANY, cust_id=cust_a,
             price=0, qty=1, remaining_qty=1,
             why=TradingOrderCancelCauseIoC())
    ])

    # 매칭은 없었었고.
    assert len(trd.matches) == 0
    event_writer_mock.on_trading_order_matched.assert_not_called()


def test_order_market_sell_matches_no_cancelled_nor_fulfilled(
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

    # oid #1을 부분 매칭 + cancel.
    trading_service.provide_item(trd_id, cust_d, ItemQty(100))

    trading_service.order_market_sell(
        trd_id, cust_d, ItemQty(1))

    trading_service.cancel_remaining_offer(trd_id, buy_oids[0])

    assert trd.orders[buy_oids[0]].cancelled
    assert not trd.orders[buy_oids[0]].fulfilled
    assert not trd.orders[buy_oids[1]].cancelled
    assert not trd.orders[buy_oids[1]].fulfilled

    # 그 다음 매칭 시도.
    trading_service.order_market_sell(
        trd_id, cust_d, ItemQty(10))

    assert not trd.orders[buy_oids[0]].fulfilled
    assert not trd.orders[buy_oids[1]].cancelled
    assert trd.orders[buy_oids[1]].fulfilled  # buy_oids[0]을 건너뛰었음.
    assert not trd.orders[buy_oids[2]].fulfilled  # buy_oids[2]은 아직.

    # 그 다음 매칭시도. (buy_oids[1], fulfilled을 건너 뛰는지?)
    trading_service.order_market_sell(
        trd_id, cust_d, ItemQty(10))

    assert trd.orders[buy_oids[2]].fulfilled


def test_order_market_sell_no_later_match(
        trading_service: TradingService
):
    """시장가 주문의 다음에 지정가 주문이 제출되어도 매칭되지 않는다."""
    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')

    # setup
    balance_service = trading_service.balance_service
    item_count_service = trading_service.item_count_service
    trd = trading_service.start_new_trading(trd_id, curr)

    # 시장가 주문을 먼저.
    trading_service.provide_item(trd_id, cust_a, ItemQty(100))

    oid = trading_service.order_market_sell(
        trd_id, cust_a, ItemQty(1))

    assert oid not in trd.orders

    # 지정가 주문.
    balance_service.deposit(BalanceType.BALANCE, cust_b, curr,
                            CurrencyAmt(1_000))
    oid_lim = trading_service.order_limit_buy(
        trd_id, cust_b, CurrencyAmt(5), ItemQty(10))

    assert not trd.orders[oid_lim].fulfilled
    assert not trd.orders[oid_lim].cancelled
    assert len(trd.matches) == 0

    # 판매 못하고 취소했으니 되돌려줘야지.
    # -- 매칭 안 된 market-sell 주문을 취소하면 아이템을 전부 되돌려준다.
    assert item_count_service.get(cust_a, trd_id) == 100
    assert item_count_service.get(cust_b, trd_id) == 0  # 구매 못함.


def test_cancel_on_market_sell_returns_item_count_02(
        trading_service: TradingService
):
    """부분 매칭 된 limit-sell 주문을 취소하면 남은 아이템을 되돌려준다."""
    trd_id = TradingId('1')
    curr = CurrencyType(1)
    cust_a = CustomerId('1')
    cust_b = CustomerId('2')

    # setup
    balance_service = trading_service.balance_service
    item_count_service = trading_service.item_count_service
    trd = trading_service.start_new_trading(trd_id, curr)

    # 지정가.
    balance_service.deposit(BalanceType.BALANCE, cust_a, curr,
                            CurrencyAmt(100))

    oid_buy = trading_service.order_limit_buy(
        trd_id, cust_a, CurrencyAmt(10), ItemQty(10))

    # 시장가 주문.
    trading_service.provide_item(trd_id, cust_b, ItemQty(100))

    oid_sell = trading_service.order_market_sell(
        trd_id, cust_b, ItemQty(100))

    # 지정가 주문 상태.
    assert trd.orders[oid_buy].fulfilled
    assert not trd.orders[oid_buy].cancelled
    assert len(trd.matches) == 1

    # 판매 못하고 취소했으니 되돌려줘야지.
    assert item_count_service.get(cust_a, trd_id) == 10
    assert item_count_service.get(cust_b, trd_id) == 90  # 판매 못함.
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0
