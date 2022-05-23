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


def test_evict_selling_auction__ok(
        started_selling_auction
):
    '여러개의 bidding이 있는 cancel+evict selling-auction.'
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

    # 취소 + evict.
    trading_service.cancel_trading(trd_id)

    trading_service.evict_trading(trd_id)

    event_writer_mock.on_trading_evicted.assert_has_calls([call(trd_id=trd_id)])

    assert trd_id not in trading_service.tradings
    assert trd_id not in trading_service.auctions
