"""TradingService.finalize_trading 테스트."""
from unittest.mock import call
from pytest import fixture, raises  # type: ignore
from oev8.typedefs import CurrencyAmt, TradingId, CustomerId, CurrencyType
from oev8.typedefs import BalanceType, ItemQty
from oev8.typedefs import TradingState
from oev8.consts import SERVICE_CUSTOMER
from oev8.svcs.trading import TradingService
from oev8.excs import TradingIsNotFound
from oev8.excs import TradingIsNotCompletable
from oev8.values.event_writer import BalanceCvtXferToCauseEarningPrep
from oev8.values.event_writer import \
    BalanceXferToCauseRefundForUnmatchedLimitBuying


@fixture
def finalize_trading_fixture(
        trading_service: TradingService
):
    """취소를 위한 픽스쳐.
    왠만한 거래들이 일어난 상태."""
    # pylint: disable=too-many-locals
    trd_id = TradingId('1')

    curr = CurrencyType(1)

    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')
    cust_d = CustomerId('4')
    cust_e = CustomerId('5')

    trd = trading_service.start_new_trading(trd_id, curr)
    balance_service = trading_service.balance_service

    # cust_{a~c}에게 1_000씩 입금.
    balance_service.deposit(BalanceType.BALANCE, cust_a, curr,
                            CurrencyAmt(1_000))

    balance_service.deposit(BalanceType.BALANCE, cust_b, curr,
                            CurrencyAmt(1_000))

    balance_service.deposit(BalanceType.BALANCE, cust_c, curr,
                            CurrencyAmt(1_000))

    # cust_{a~c}이 구매 주문.
    oid_1 = trading_service.order_limit_buy(
        trd_id, cust_a, CurrencyAmt(10), ItemQty(23))  # -230

    oid_2 = trading_service.order_limit_buy(
        trd_id, cust_b, CurrencyAmt(9), ItemQty(22))  # -198

    oid_3 = trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(8), ItemQty(21))  # -168

    # 판매: cust_{d, e}
    trading_service.provide_item(trd_id, cust_d, ItemQty(100))

    trading_service.provide_item(trd_id, cust_e, ItemQty(200))

    # oid_1: 10*23 = 230으로 23-qty 구매 :: fulfilled. cust_a 환불 없음.
    # oid_2: 7*9 = 63으로 7-qty 구매. :: oid_2에서 15-qty 남음.
    #   - cust_b에게 9 * 15 = 135-amt 환불 남음.
    # oid_4: 전량 판매. 230 + 63 = 293 수익 -> cust_d.
    oid_4 = trading_service.order_limit_sell(
        trd_id, cust_d, CurrencyAmt(7), ItemQty(30))

    # oid_2: 9*15 = 135으로 15-qty 전량 구매. :: fulfilled. cust_b 환불 없음.
    # oid_3: 8*15 = 120으로 15-qty 부분 구매. :: cust_c, 6-qty*8-amt = 48-amt 환불 남음.
    # oid_5: 9*15 = 135, 8*15 = 120 전량 판매 :: cust_d 255-amt 수익.
    # oid_4, oid_5 수익 합 :: 293+255 = 548.
    oid_5 = trading_service.order_limit_sell(
        trd_id, cust_d, CurrencyAmt(8), ItemQty(30))

    # 매칭 없음: cust_e 수익 없음.
    oid_6 = trading_service.order_limit_sell(
        trd_id, cust_e, CurrencyAmt(10), ItemQty(13))

    return {
        'cust_a': cust_a,
        'cust_b': cust_b,
        'cust_c': cust_c,
        'cust_d': cust_d,
        'cust_e': cust_e,
        'trading_service': trading_service,
        'balance_service': balance_service,
        'item_count_service': trading_service.item_count_service,
        'trd': trd,
        'trd_id': trd_id,
        'curr': curr,
        'oid_1': oid_1,
        'oid_2': oid_2,
        'oid_3': oid_3,
        'oid_4': oid_4,
        'oid_5': oid_5,
        'oid_6': oid_6,
    }


def assert_event_writer_not_called(event_writer):
    "event_writer interaction 없음을 assert."
    event_writer.on_balance_cvt_xfer_to.assert_not_called()
    event_writer.on_balance_xfer_to.assert_not_called()
    event_writer.on_trading_finalized.assert_not_called()


def reset_event_writer_mocks(event_writer):
    "event_writer interaction 없음을 assert."
    event_writer.on_balance_cvt_xfer_to.reset_mock()
    event_writer.on_balance_xfer_to.reset_mock()
    event_writer.on_trading_finalized.reset_mock()


def test_finalize_non_existing_trading(
        trading_service: TradingService,
        event_writer_mock
):
    """trading_id이 존재하는 것이어야한다."""
    with raises(TradingIsNotFound):
        trading_service.finalize_trading(TradingId('123'))

    assert_event_writer_not_called(event_writer_mock)


def test_finalize_on_invalid_state_trading(
        trading_service: TradingService,
        event_writer_mock
):
    """trading이 {OPEN, PAUSED} 상태여야한다. (not CANCELLED, COMPLETED.)"""

    # CANCELLED은 다시 취소 불가.
    trd = trading_service.start_new_trading(TradingId('1'), CurrencyType(1))
    trading_service.cancel_trading(TradingId('1'))  # 일단 취소처리.
    assert trd.state == TradingState.CANCELLED
    with raises(TradingIsNotCompletable):
        trading_service.finalize_trading(TradingId('1'))  # 다시 완료처리.
    assert trd.state == TradingState.CANCELLED
    assert_event_writer_not_called(event_writer_mock)
    reset_event_writer_mocks(event_writer_mock)

    # COMPLETED도 취소 불가.
    trd = trading_service.start_new_trading(TradingId('2'), CurrencyType(1))
    trading_service.finalize_trading(TradingId('2'))  # 일단 완료처리.

    event_writer_mock.on_balance_cvt_xfer_to.assert_not_called()
    event_writer_mock.on_balance_xfer_to.assert_not_called()
    event_writer_mock.on_trading_finalized.assert_called_with(trd_id='2')

    reset_event_writer_mocks(event_writer_mock)

    # trading.state <- COMPLETED으로 변경한다.
    assert trd.state == TradingState.COMPLETED
    with raises(TradingIsNotCompletable):
        trading_service.finalize_trading(TradingId('2'))  # 다시 완료처리.
    assert trd.state == TradingState.COMPLETED
    assert_event_writer_not_called(event_writer_mock)


def test_finalize_trading_refund_to_buyers(
        finalize_trading_fixture
):
    """구매자에게 매칭 안된 LIMIT주문 비용 환불."""
    # pylint: disable=redefined-outer-name, invalid-name
    ft = finalize_trading_fixture
    trd_id = ft['trd_id']
    trading_service = ft['trading_service']
    balance_service = ft['balance_service']
    item_count_service = ft['item_count_service']
    curr = ft['curr']
    cust_a = ft['cust_a']
    cust_b = ft['cust_b']
    cust_c = ft['cust_c']

    #
    trading_service.finalize_trading(trd_id)

    # buyer에게는 처음 {구매시 제시액 - (매칭 수량 x 매칭 단가)}을 Balance으로 환불.
    # -- svc-cust -> buyer balance.

    # svc-cust
    assert balance_service.get(BalanceType.BALANCE,
                               SERVICE_CUSTOMER, curr) == 0
    assert balance_service.get(BalanceType.EARNING,
                               SERVICE_CUSTOMER, curr) == 0
    assert item_count_service.get(SERVICE_CUSTOMER,
                                  trd_id) == 13  # oid_6 미판매분.

    # cust_a
    assert balance_service.get(BalanceType.BALANCE,
                               cust_a, curr) == 1_000 - 230
    assert balance_service.get(BalanceType.EARNING,
                               cust_a, curr) == 0
    assert item_count_service.get(cust_a, trd_id) == 23

    # cust_b
    assert balance_service.get(BalanceType.BALANCE,
                               cust_b, curr) == 1_000 - 198
    assert balance_service.get(BalanceType.EARNING,
                               cust_b, curr) == 0
    assert item_count_service.get(cust_b, trd_id) == 22

    # cust_c
    assert balance_service.get(BalanceType.BALANCE,
                               cust_c, curr) == 1_000 - 168 + 48
    assert balance_service.get(BalanceType.EARNING,
                               cust_c, curr) == 0
    assert item_count_service.get(cust_c, trd_id) == 15


def test_finalize_trading_refund_to_buyers_event_writer(
        finalize_trading_fixture,
        event_writer_mock
):
    """구매자에게 매칭 안된 LIMIT주문 비용 환불 + event_writer."""
    # pylint: disable=redefined-outer-name, invalid-name
    ft = finalize_trading_fixture
    trd_id = ft['trd_id']
    trading_service = ft['trading_service']
    curr = ft['curr']
    oid_3 = ft['oid_3']
    cust_c = ft['cust_c']
    cust_d = ft['cust_d']

    trading_service.finalize_trading(trd_id)

    # event_writer
    event_writer_mock.on_trading_finalized.assert_called_with(trd_id=trd_id)

    event_writer_mock.on_balance_cvt_xfer_to.assert_has_calls(
        [
            call(
                from_balance_type=BalanceType.BALANCE,
                to_balance_type=BalanceType.EARNING,
                cust_id=cust_d,
                curr=curr,
                amt=230,
                new_amt=230,
                new_svc=318,
                why=BalanceCvtXferToCauseEarningPrep(
                    trd_id=trd_id)),
            call(
                from_balance_type=BalanceType.BALANCE,
                to_balance_type=BalanceType.EARNING,
                cust_id=cust_d,
                curr=curr,
                amt=63,
                new_amt=293,
                new_svc=255,
                why=BalanceCvtXferToCauseEarningPrep(
                    trd_id=trd_id)),
            call(
                from_balance_type=BalanceType.BALANCE,
                to_balance_type=BalanceType.EARNING,
                cust_id=cust_d,
                curr=curr,
                amt=135,
                new_amt=428,
                new_svc=120,
                why=BalanceCvtXferToCauseEarningPrep(
                    trd_id=trd_id)),
            call(
                from_balance_type=BalanceType.BALANCE,
                to_balance_type=BalanceType.EARNING,
                cust_id=cust_d,
                curr=curr,
                amt=120,
                new_amt=548,
                new_svc=0,
                why=BalanceCvtXferToCauseEarningPrep(
                    trd_id=trd_id))])

    event_writer_mock.on_balance_xfer_to.assert_has_calls(
        [
            call(
                balance_type=BalanceType.BALANCE,
                cust_id=cust_c,
                curr=curr,
                amt=48,
                new_amt=880,
                new_svc=548,
                why=BalanceXferToCauseRefundForUnmatchedLimitBuying(
                    trd_id=trd_id,
                    ord_id=oid_3))])


def test_finalize_trading_earnings_for_sellers(
        finalize_trading_fixture
):
    """구매자에게 매칭 안된 LIMIT주문 비용 환불."""
    # pylint: disable=redefined-outer-name, invalid-name
    ft = finalize_trading_fixture
    trd_id = ft['trd_id']
    trading_service = ft['trading_service']
    balance_service = ft['balance_service']
    item_count_service = ft['item_count_service']
    curr = ft['curr']
    cust_d = ft['cust_d']
    cust_e = ft['cust_e']

    #
    trading_service.finalize_trading(trd_id)

    # svc-cust
    assert balance_service.get(BalanceType.BALANCE,
                               SERVICE_CUSTOMER, curr) == 0
    assert balance_service.get(BalanceType.EARNING,
                               SERVICE_CUSTOMER, curr) == 0
    assert item_count_service.get(SERVICE_CUSTOMER,
                                  trd_id) == 13  # oid_6 미판매분.

    # item-provider, reseller 모두 earnings으로 매칭된 금액을 svc-cust 에서 이체해준다.
    # cust_d
    assert balance_service.get(BalanceType.BALANCE,
                               cust_d, curr) == 0
    assert balance_service.get(BalanceType.EARNING,
                               cust_d, curr) == 548
    assert item_count_service.get(cust_d, trd_id) == 100 - 30 - 30

    # cust_e
    assert balance_service.get(BalanceType.BALANCE,
                               cust_e, curr) == 0
    assert balance_service.get(BalanceType.EARNING,
                               cust_e, curr) == 0
    assert item_count_service.get(cust_e, trd_id) == 200 - 13


def test_finalize_trading_after_juggling(
        trading_service: TradingService
):
    """reselling이 중간에 있을 경우, 중복된 구매 대금과 판매 수익."""
    # pylint: disable=too-many-locals
    trd_id = TradingId('1')

    curr = CurrencyType(1)

    cust_a = CustomerId('1')
    cust_b = CustomerId('2')
    cust_c = CustomerId('3')

    #
    trading_service.start_new_trading(trd_id, curr)
    balance_service = trading_service.balance_service
    item_count_service = trading_service.item_count_service

    # buy-1 by cust_a
    balance_service.deposit(BalanceType.BALANCE, cust_a,
                            curr, CurrencyAmt(100))

    trading_service.order_limit_buy(
        trd_id, cust_a, CurrencyAmt(10), ItemQty(10))

    assert balance_service.get(BalanceType.BALANCE,
                               SERVICE_CUSTOMER, curr) == 10 * 10
    assert balance_service.get(BalanceType.BALANCE,
                               cust_a, curr) == 100 - 100

    # sell-1 by cust_b
    trading_service.provide_item(trd_id, cust_b, ItemQty(20))
    trading_service.order_limit_sell(
        trd_id, cust_b, CurrencyAmt(7), ItemQty(5))

    assert item_count_service.get(cust_b, trd_id) == 20 - 5
    assert item_count_service.get(cust_a, trd_id) == 5

    # resell-1 by cust_a
    trading_service.order_limit_sell(
        trd_id, cust_a, CurrencyAmt(20), ItemQty(5))
    assert item_count_service.get(cust_a, trd_id) == 0
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 5

    # buy-2 by cust_c
    balance_service.deposit(BalanceType.BALANCE, cust_c,
                            curr, CurrencyAmt(100))
    before_balance = balance_service.get(BalanceType.BALANCE,
                                         SERVICE_CUSTOMER, curr)
    trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(23), ItemQty(3))
    assert item_count_service.get(cust_c, trd_id) == 3
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 2
    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == \
        before_balance + (23 * 3)
    assert balance_service.get(BalanceType.BALANCE,
                               cust_c, curr) == 100 - (23 * 3)

    #
    trading_service.finalize_trading(trd_id)

    # cust_a
    # -- BUY:{10-amt, 10-qty}제시 -> {10-amt, 5-qty}매칭 --> BUY:-100, REFUND:+50
    # -- SELL:{23-amt, 3-qty}매칭 --> EARN:+69
    assert balance_service.get(
        BalanceType.BALANCE, cust_a, curr) == 100 - 100 + 50
    assert balance_service.get(
        BalanceType.EARNING, cust_a, curr) == 69

    # cust_b
    # -- SELL:{10-amt, 5-qty}매칭 --> EARN:+50
    assert balance_service.get(
        BalanceType.BALANCE, cust_b, curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_b, curr) == 50

    # cust_c
    # -- BUY:{23-amt, 3-qty}매칭 --> BUY:-69
    assert balance_service.get(
        BalanceType.BALANCE, cust_c, curr) == 100 - 69
    assert balance_service.get(
        BalanceType.EARNING, cust_c, curr) == 0


def test_finalize_trading_never_cancels(
        finalize_trading_fixture
):
    """매칭 안된 경우에도 cancel_remaining_offer 하지 않고 잔여 구매 주문을 환불."""
    # pylint: disable=redefined-outer-name, invalid-name
    ft = finalize_trading_fixture
    trd_id = ft['trd_id']
    trading_service = ft['trading_service']

    trading_service.finalize_trading(trd_id)

    #
    count_total = 0
    count_fulfilled = 0

    for oid_name in ['oid_1', 'oid_2', 'oid_3',
                     'oid_4', 'oid_5', 'oid_6']:
        oid = ft[oid_name]
        assert oid in trading_service.tradings[trd_id].orders
        order =  trading_service.tradings[trd_id].orders[oid]

        assert not order.cancelled

        count_total = count_total + 1

        if order.fulfilled:
            count_fulfilled = count_fulfilled + 1

    assert count_total > count_fulfilled > 0
