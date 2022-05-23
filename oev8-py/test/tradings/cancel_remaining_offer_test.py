"""TradingService.cancel_remaining_offer 테스트"""
from unittest.mock import ANY, call
from pytest import fixture, raises  # type: ignore
from oev8.svcs.trading import TradingService
from oev8.svcs.seq_num import SeqType
from oev8.typedefs import CustomerId, CurrencyType, ItemQty, CurrencyAmt
from oev8.typedefs import BalanceType, TradingId
from oev8.excs import TradingIsNotFound, OrderIdNotFound
from oev8.excs import TradingIsNotOpened
from oev8.excs import OrderOfferLineIsFulfilled, OrderOfferLineIsCancelled
from oev8.values.event_writer import \
    BalanceXferToCauseRefundForUnmatchedLimitBuying
from oev8.consts import SERVICE_CUSTOMER


@fixture
def cancel_rem_basic_fixture(trading_service: TradingService):
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

    balance_service.deposit(BalanceType.BALANCE, cust_c,
                            curr, CurrencyAmt(1_000))

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
        'oid_1': oid_1,
        'oid_2': oid_2,
        'oid_3': oid_3,
        'trd': trd,
        'trading_service': trading_service,
        'item_count_service': trading_service.item_count_service,
        'balance_service': trading_service.balance_service,
    }


def test_cancel_rem_offer_valid_trading_id(
        cancel_rem_basic_fixture,
        seq_num_service,
        event_writer_mock
):
    """올바른 trading_id이어야한다."""
    # pylint: disable=redefined-outer-name
    trd_id = cancel_rem_basic_fixture['trd_id']
    trd_id_nf = cancel_rem_basic_fixture['trd_id_not_found']
    trd = cancel_rem_basic_fixture['trd']
    oid_1 = cancel_rem_basic_fixture['oid_1']
    cust_a = cancel_rem_basic_fixture['cust_a']

    trading_service = cancel_rem_basic_fixture['trading_service']

    # 없는 trading_id
    with raises(TradingIsNotFound):
        trading_service.cancel_remaining_offer(trd_id_nf, oid_1)

    assert not trd.orders[oid_1].cancelled
    event_writer_mock.on_trading_order_cancelled.assert_not_called()

    # 없는 ord_id
    oid_nf = seq_num_service.next(SeqType.ORDER)
    event_writer_mock.on_trading_order_cancelled.reset_mock()

    with raises(OrderIdNotFound):
        trading_service.cancel_remaining_offer(trd_id, oid_nf)

    assert not trd.orders[oid_1].cancelled
    event_writer_mock.on_trading_order_cancelled.assert_not_called()

    #
    order = trd.orders[oid_1]
    event_writer_mock.on_trading_order_cancelled.reset_mock()

    trading_service.cancel_remaining_offer(trd_id, oid_1)

    assert order.cancelled
    assert oid_1 not in trd.orders  # 매치가 없으니까 아예 사라졌다.

    event_writer_mock.on_trading_order_cancelled.assert_called_with(
        trd_id=trd_id, ord_id=oid_1, price=10, qty=10, remaining_qty=10,
        cust_id=cust_a, why=ANY)

    event_writer_mock.on_trading_order_cancelled.assert_called_once()


def test_cancel_rem_offer_on_only_opened_trading(
        cancel_rem_basic_fixture
):
    """trading.state == OPEN이어야 한다."""
    # pylint: disable=redefined-outer-name
    trd_id = cancel_rem_basic_fixture['trd_id']
    oid_1 = cancel_rem_basic_fixture['oid_1']

    trading_service = cancel_rem_basic_fixture['trading_service']

    # PAUSED 상태인 trading_id
    trading_service.pause_trading(trd_id)

    with raises(TradingIsNotOpened):
        trading_service.cancel_remaining_offer(trd_id, oid_1)

    trading_service.resume_trading(trd_id)

    trading_service.cancel_remaining_offer(trd_id, oid_1)


def test_cancel_rem_offer_not_for_cancelled_nor_fulfilled(
        cancel_rem_basic_fixture,
        event_writer_mock
):
    """order이 !cancelled && !fulfilled 이어야 한다."""
    # pylint: disable=redefined-outer-name
    trd_id = cancel_rem_basic_fixture['trd_id']
    trd = cancel_rem_basic_fixture['trd']
    oid_1 = cancel_rem_basic_fixture['oid_1']
    oid_2 = cancel_rem_basic_fixture['oid_2']
    oid_3 = cancel_rem_basic_fixture['oid_3']
    cust_a = cancel_rem_basic_fixture['cust_a']
    cust_b = cancel_rem_basic_fixture['cust_b']
    cust_c = cancel_rem_basic_fixture['cust_c']
    trading_service = cancel_rem_basic_fixture['trading_service']

    # oid_2을 fulfill.
    trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(5), ItemQty(5))

    # oid_2을 취소하려고 하면,
    with raises(OrderOfferLineIsFulfilled):
        trading_service.cancel_remaining_offer(trd_id, oid_2)

    event_writer_mock.on_trading_order_cancelled.assert_not_called()

    # oid_3을 취소.
    event_writer_mock.on_trading_order_cancelled.reset_mock()

    trading_service.cancel_remaining_offer(trd_id, oid_3)

    # 체결 내용이 없다면, orderbook에서 해당 가격대에서 사라져야한다.
    assert CurrencyAmt(15) not in trd.sells
    # -- 해당 가격대으로 체결될 수 없어야 한다. (buy/sell 모두)
    # -- 해당 가격이 혼자였다면, 해당 가격의 항록 자체가 오더북에서 사라져야한다.
    # -- offers에서도 아예 항목이 사라져야한다.
    assert oid_3 not in trd.orders
    #
    event_writer_mock.on_trading_order_cancelled.assert_called_with(
        trd_id=trd_id, ord_id=oid_3, price=15, qty=2, remaining_qty=2,
        cust_id=cust_b,
        why=ANY)

    # 취소된 항목을 다시 취소하려고 하면,
    event_writer_mock.on_trading_order_cancelled.reset_mock()
    with raises(OrderIdNotFound):
        trading_service.cancel_remaining_offer(trd_id, oid_3)

    event_writer_mock.on_trading_order_cancelled.assert_not_called()

    # oid_1을 부분 fill + cancel.
    event_writer_mock.on_trading_order_cancelled.reset_mock()
    t_ord_id = trading_service.order_limit_buy(
        trd_id, cust_c, CurrencyAmt(10), ItemQty(5))

    trading_service.cancel_remaining_offer(trd_id, oid_1)

    assert CurrencyAmt(10) not in trd.sells

    assert oid_1 in trd.orders
    assert trd.orders[oid_1].cancelled

    event_writer_mock.on_trading_order_cancelled.assert_called_with(
        trd_id=trd_id, ord_id=oid_1, price=10, qty=10, remaining_qty=5,
        cust_id=cust_a,
        why=ANY)

    # partially 매치된 내용은 그대로 남아있어야 한다. (buy/sell 모두)
    found_oid_1 = False
    for match in trd.matches:
        if match.making_taking_order_pair == (oid_1, t_ord_id):
            found_oid_1 = True
            break
    assert found_oid_1

    # partial 취소를 다시 취소 시도.
    event_writer_mock.on_trading_order_cancelled.reset_mock()

    with raises(OrderOfferLineIsCancelled):
        trading_service.cancel_remaining_offer(trd_id, oid_1)

    event_writer_mock.on_trading_order_cancelled.assert_not_called()


def test_cancel_rem_offer_on_not_matched_sell(
        cancel_rem_basic_fixture,
        balance_service,
        event_writer_mock
):
    """매칭되지 않은 SELL주문을 취소."""
    # pylint: disable=redefined-outer-name
    trd_id = cancel_rem_basic_fixture['trd_id']
    curr = cancel_rem_basic_fixture['curr']

    trading_service = cancel_rem_basic_fixture['trading_service']

    buyer = CustomerId('10')

    balance_service.deposit(BalanceType.BALANCE, buyer,
                            curr, CurrencyAmt(10))  # 매칭되지 않도록.

    buy_order = trading_service.order_limit_buy(
        trd_id, buyer, CurrencyAmt(1), ItemQty(10))

    trading_service.cancel_remaining_offer(trd_id, buy_order)

    # Balance 체크 (buyer, SERVICE_CUSTOMER)
    assert balance_service.get(
        BalanceType.BALANCE, buyer, curr) == 10

    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 0

    # 이벤트: xfer_to.
    event_writer_mock.on_balance_xfer_to.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=buyer,
             curr=curr,
             amt=10, new_amt=10, new_svc=0,
             why=BalanceXferToCauseRefundForUnmatchedLimitBuying(
                 trd_id=trd_id, ord_id=buy_order))
    ])


def test_cancel_rem_offer_on_partially_matched_sell(
        cancel_rem_basic_fixture,
        balance_service,
        event_writer_mock
):
    """부분 매칭된 SELL주문을 취소."""
    # pylint: disable=redefined-outer-name
    trd_id = cancel_rem_basic_fixture['trd_id']
    curr = cancel_rem_basic_fixture['curr']

    trading_service = cancel_rem_basic_fixture['trading_service']

    buyer = CustomerId('10')

    balance_service.deposit(BalanceType.BALANCE, buyer,
                            curr, CurrencyAmt(5 * 10))

    buy_order = trading_service.order_limit_buy(
        trd_id, buyer, CurrencyAmt(5), ItemQty(10))  # 5-qty만 매칭됨.

    trading_service.cancel_remaining_offer(trd_id, buy_order)

    # Balance 체크 (buyer, SERVICE_CUSTOMER)
    assert balance_service.get(
        BalanceType.BALANCE, buyer, curr) == 25

    assert balance_service.get(
        BalanceType.BALANCE, SERVICE_CUSTOMER, curr) == 25  # 판매대금.

    # 이벤트: xfer_to.
    event_writer_mock.on_balance_xfer_to.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=buyer,
             curr=curr,
             amt=25, new_amt=25, new_svc=25,
             why=BalanceXferToCauseRefundForUnmatchedLimitBuying(
                 trd_id=trd_id, ord_id=buy_order))
    ])
