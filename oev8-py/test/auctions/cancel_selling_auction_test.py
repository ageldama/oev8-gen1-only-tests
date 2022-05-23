from unittest.mock import call, ANY
from pytest import raises  # type:ignore
from oev8.consts import SERVICE_CUSTOMER
from oev8.typedefs import BalanceType, OrderOption, SeqType
from oev8.typedefs import OrderType, OrderSide, TradingType, TradingState
from oev8.values.event_writer import \
    TradingOrderCancelCauseUserCancel, \
    BalanceXferToCauseRefundForUnmatchedLimitBuying, \
    BalanceXferToCauseTradingCancellation
from oev8.excs import NotEnoughBalance, CurrencyAmtShouldBePositive, \
    ItemQtyShouldBePositive, TradingIsNotOpened, TradingIsNotFound, \
    UnsatisfyingAuctionBidPrice, \
    TradingIsNotCancellable


def test_cancel_selling_auction__ok(
        started_selling_auction
):
    '여러개의 bidding이 있는 cancel selling-auction.'
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
    trading_service.cancel_trading(trd_id)

    assert trading_service.tradings[trd_id].state == TradingState.CANCELLED
    event_writer_mock.on_trading_cancelled.assert_has_calls([call(trd_id=trd_id)])

    # 아이템, 잔고.
    assert item_count_service.get(cust_id=buyer_a, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=buyer_b, trd_id=trd_id) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=buyer_a, curr=params.curr) == \
        balance_amt

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=buyer_b, curr=params.curr) == \
        balance_amt

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        params.security_deposit_amt

    event_writer_mock.on_balance_xfer_to.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=buyer_a, curr=params.curr,
             amt=balance_amt, new_amt=balance_amt,
             new_svc=ANY,
             why=BalanceXferToCauseTradingCancellation(trd_id=trd_id)),
        call(balance_type=BalanceType.BALANCE,
             cust_id=buyer_b, curr=params.curr,
             amt=balance_amt, new_amt=balance_amt,
             new_svc=ANY,
             why=BalanceXferToCauseTradingCancellation(trd_id='123'))
    ])


def test_cancel_selling_auction__empty(
        started_selling_auction
):
    trading_service = started_selling_auction.trading_service
    balance_service = started_selling_auction.balance_service
    item_count_service = started_selling_auction.item_count_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id

      # 취소.
    trading_service.cancel_trading(trd_id)

    assert trading_service.tradings[trd_id].state == TradingState.CANCELLED
    event_writer_mock.on_trading_cancelled.assert_has_calls([call(trd_id=trd_id)])

    # 아이템, 잔고.
    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        params.security_deposit_amt


def test_cancel_selling_auction__finalized(
        started_selling_auction
):
    trading_service = started_selling_auction.trading_service
    balance_service = started_selling_auction.balance_service
    item_count_service = started_selling_auction.item_count_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id

    buyer_a = str(int(params.cust_id) + 1)
    buyer_b = str(int(buyer_a) + 1)

    price = params.price
    qty = 2

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
    trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_a,
        price=price,
        qty=qty,
        option=OrderOption.NONE
    )

    trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_b,
        price=price,
        qty=qty,
        option=OrderOption.NONE
    )

    # fianlize.
    trading_service.finalize_trading(trd_id)

    # 취소.
    with raises(TradingIsNotCancellable):
        trading_service.cancel_trading(trd_id)

    assert trading_service.tradings[trd_id].state != TradingState.CANCELLED
    event_writer_mock.on_trading_cancelled.assert_not_called()

    # 아이템, 잔고.
    assert item_count_service.get(cust_id=buyer_a, trd_id=trd_id) == qty
    assert item_count_service.get(cust_id=buyer_b, trd_id=trd_id) == qty

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=buyer_a, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=buyer_b, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        params.security_deposit_amt

    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == \
        balance_amt * 2


def test_cancel_selling_auction__and_cancel_rem_offer(
        started_selling_auction
):
    'cancel_trading한 후 bid_buying을 cancel_rem_offer 시도.'
    trading_service = started_selling_auction.trading_service
    balance_service = started_selling_auction.balance_service
    item_count_service = started_selling_auction.item_count_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id

    buyer = str(int(params.cust_id) + 1)

    price = params.price
    qty = params.qty

    balance_amt = price * qty

    # 구매할 자금.
    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer,
        curr=params.curr,
        amt=balance_amt)

    # bid!
    buy_id = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer,
        price=price,
        qty=qty,
        option=OrderOption.NONE
    )

    # 취소.
    trading_service.cancel_trading(trd_id)

    event_writer_mock.on_balance_xfer_to.reset_mock()
    event_writer_mock.on_item_count_xfer_from.reset_mock()
    event_writer_mock.on_trading_cancelled.reset_mock()

    assert trading_service.tradings[trd_id].state == TradingState.CANCELLED

    # 아이템, 잔고.
    assert item_count_service.get(cust_id=buyer, trd_id=trd_id) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=buyer, curr=params.curr) == \
        balance_amt

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        params.security_deposit_amt

    # 주문 취소시도.
    with raises(TradingIsNotOpened):
        trading_service.cancel_remaining_offer(
            trd_id=trd_id, ord_id=buy_id)

    event_writer_mock.on_trading_order_cancelled.assert_not_called()
    event_writer_mock.on_balance_xfer_to.assert_not_called()
    event_writer_mock.on_item_count_xfer_from.assert_not_called()
