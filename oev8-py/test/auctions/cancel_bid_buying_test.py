from unittest.mock import call, ANY
from pytest import raises  # type:ignore
from oev8.consts import SERVICE_CUSTOMER
from oev8.typedefs import BalanceType, OrderOption, SeqType
from oev8.typedefs import OrderType, OrderSide, TradingType
from oev8.values.event_writer import \
    TradingOrderCancelCauseUserCancel, \
    BalanceXferToCauseRefundForUnmatchedLimitBuying
from oev8.excs import NotEnoughBalance, CurrencyAmtShouldBePositive, \
    ItemQtyShouldBePositive, TradingIsNotOpened, TradingIsNotFound, \
    UnsatisfyingAuctionBidPrice


def test_cancel_bid_buying__ok(
        started_selling_auction
):
    trading_service = started_selling_auction.trading_service
    balance_service = started_selling_auction.balance_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    buyer_cust_id = str(int(params.cust_id) + 1)

    price = params.price
    qty = params.qty

    balance_amt = price * qty

    # 구매할 자금.
    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_cust_id,
        curr=params.curr,
        amt=balance_amt)

    # bid!
    ord_id = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_cust_id,
        price=price,
        qty=qty,
        option=OrderOption.NONE
    )

    order = trd.orders[ord_id]

    assert not order.cancelled

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=buyer_cust_id, curr=params.curr) == \
        0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        params.security_deposit_amt + balance_amt

    # 취소.
    trading_service.cancel_remaining_offer(
        trd_id=trd_id, ord_id=ord_id)

    assert order.cancelled

    # orders?
    assert ord_id not in trd.orders
    assert price not in trd.auction_bids

    # 취소 이벤트
    event_writer_mock.on_trading_order_cancelled.assert_has_calls([
        call(trd_id=trd_id, ord_id=ord_id, cust_id=buyer_cust_id,
             price=price, qty=qty, remaining_qty=qty,
             why=TradingOrderCancelCauseUserCancel())
    ])

    event_writer_mock.on_trading_order_cancelled.assert_called_once()

    # 환불처리 + 이벤트.
    assert balance_service.get(
        BalanceType.BALANCE, cust_id=buyer_cust_id, curr=params.curr) == \
        balance_amt

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        params.security_deposit_amt

    event_writer_mock.on_balance_xfer_to.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=buyer_cust_id, curr=params.curr,
             amt=balance_amt, new_amt=balance_amt,
             new_svc=params.security_deposit_amt,
             why=BalanceXferToCauseRefundForUnmatchedLimitBuying(
                 trd_id=trd_id, ord_id=ord_id))
    ])


def test_cancel_bid_buying__paused(
        started_selling_auction
):
    trading_service = started_selling_auction.trading_service
    balance_service = started_selling_auction.balance_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    buyer_cust_id = str(int(params.cust_id) + 1)

    price = params.price
    qty = params.qty

    balance_amt = price * qty

    # 구매할 자금.
    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_cust_id,
        curr=params.curr,
        amt=balance_amt)

    # bid!
    ord_id = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_cust_id,
        price=price,
        qty=qty,
        option=OrderOption.NONE
    )

    order = trd.orders[ord_id]

    assert not order.cancelled

    # Pause
    trading_service.pause_trading(trd_id)

    # 취소.
    with raises(TradingIsNotOpened):
        trading_service.cancel_remaining_offer(
            trd_id=trd_id, ord_id=ord_id)

    # orders?
    assert ord_id in trd.orders
    assert price in trd.auction_bids
    assert not order.cancelled

    # 취소 이벤트
    event_writer_mock.on_trading_order_cancelled.assert_not_called()

    # 환불처리 + 이벤트.
    assert balance_service.get(
        BalanceType.BALANCE, cust_id=buyer_cust_id, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        params.security_deposit_amt + balance_amt

    event_writer_mock.on_balance_xfer_to.assert_not_called()


def test_cancel_bid_buying__finalized(
        started_selling_auction
):
    trading_service = started_selling_auction.trading_service
    balance_service = started_selling_auction.balance_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    buyer_cust_id = str(int(params.cust_id) + 1)

    price = params.price
    qty = params.qty

    balance_amt = price * qty

    # 구매할 자금.
    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_cust_id,
        curr=params.curr,
        amt=balance_amt)

    # bid!
    ord_id = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_cust_id,
        price=price,
        qty=qty,
        option=OrderOption.NONE
    )

    order = trd.orders[ord_id]

    assert not order.cancelled

    # Finalize
    trading_service.finalize_trading(trd_id)

    # 취소.
    with raises(TradingIsNotOpened):
        trading_service.cancel_remaining_offer(
            trd_id=trd_id, ord_id=ord_id)

    # orders?
    assert ord_id in trd.orders
    assert price in trd.auction_bids
    assert not order.cancelled

    # 취소 이벤트
    event_writer_mock.on_trading_order_cancelled.assert_not_called()

    # 환불처리 + 이벤트.
    assert balance_service.get(
        BalanceType.BALANCE, cust_id=buyer_cust_id, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == \
        balance_amt

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        params.security_deposit_amt

    event_writer_mock.on_balance_xfer_to.assert_not_called()


def test_cancel_bid_buying__passed_on_matching(
        started_selling_auction
):
    '여러개의 bidding이 있고, cancel된 bidding은 건너뛰고 매칭되는지?'
    trading_service = started_selling_auction.trading_service
    balance_service = started_selling_auction.balance_service
    item_count_service = started_selling_auction.item_count_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id

    buyer_a = str(int(params.cust_id) + 1)
    buyer_b = str(int(buyer_a) + 1)

    price = params.price
    qty = params.qty

    balance_amt = price * qty

    # 구매할 자금.
    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_a,
        curr=params.curr,
        amt=balance_amt)

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_b,
        curr=params.curr,
        amt=balance_amt)

    # bid!
    buy_id_a = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_a,
        price=price,
        qty=qty,
        option=OrderOption.NONE
    )

    buy_id_b = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_b,
        price=price,
        qty=qty,
        option=OrderOption.NONE
    )

    # 취소.
    trading_service.cancel_remaining_offer(
        trd_id=trd_id, ord_id=buy_id_a)

    # Finalize
    trading_service.finalize_trading(trd_id)

    #
    assert item_count_service.get(cust_id=buyer_a, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=buyer_b, trd_id=trd_id) == params.qty
