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


def test_evict_buying_auction__ok(
        started_buying_auction
):
    '여러개의 asking이 있는 cancel+evict buying-auction.'
    trading_service = started_buying_auction.trading_service
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service
    event_writer_mock = started_buying_auction.event_writer_mock

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id

    seller_a = str(int(params.cust_id) + 1)
    seller_b = str(int(seller_a) + 1)

    price = params.price
    qty = params.qty

    sell_sec_deposit_amt_a = 123
    sell_sec_deposit_amt_b = 456

    # 판매자 담보금.
    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller_a,
        curr=params.curr,
        amt=sell_sec_deposit_amt_a)

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller_b,
        curr=params.curr,
        amt=sell_sec_deposit_amt_b)

    # ask!
    sell_id_a = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller_a,
        price=price,
        qty=qty,
        security_deposit_amt=sell_sec_deposit_amt_a,
        option=OrderOption.NONE
    )

    sell_id_b = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller_b,
        price=price,
        qty=qty,
        security_deposit_amt=sell_sec_deposit_amt_b,
        option=OrderOption.NONE
    )

    # 취소 + evict.
    trading_service.cancel_trading(trd_id)

    trading_service.evict_trading(trd_id)

    event_writer_mock.on_trading_evicted.assert_has_calls([call(trd_id=trd_id)])

    assert trd_id not in trading_service.tradings
    assert trd_id not in trading_service.auctions
