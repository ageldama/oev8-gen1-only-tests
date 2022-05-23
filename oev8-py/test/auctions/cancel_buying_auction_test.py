from unittest.mock import call, ANY
from pytest import raises  # type:ignore
from pytest import mark  # type:ignore
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


def test_cancel_buying_auction__ok(
        started_buying_auction
):
    '여러개의 asking이 있는 cancel buying-auction.'
    trading_service = started_buying_auction.trading_service
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service
    event_writer_mock = started_buying_auction.event_writer_mock

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id

    seller_a = str(int(params.cust_id) + 1)
    seller_b = str(int(seller_a) + 1)

    sell_sec_deposit_amt_a = 123
    sell_sec_deposit_amt_b = 456

    price = params.price
    qty = params.qty

    # 담보금 입금.
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

    # 취소.
    trading_service.cancel_trading(trd_id)

    assert trading_service.tradings[trd_id].state == TradingState.CANCELLED
    event_writer_mock.on_trading_cancelled.assert_has_calls([call(trd_id=trd_id)])

    # 아이템: 반환 없음.
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == \
        qty * 2
    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=seller_a, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=seller_b, trd_id=trd_id) == 0

    # balance: 담보금 반환 없음. 구매대금만 환불.
    sec_deposit_amts = params.security_deposit_amt + \
        sell_sec_deposit_amt_a + sell_sec_deposit_amt_b

    purchase_amt = params.price * params.qty

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        sec_deposit_amts

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == \
        purchase_amt
    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_a, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_a, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_b, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_b, curr=params.curr) == 0

    event_writer_mock.on_balance_xfer_to.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=params.cust_id, curr=params.curr,
             amt=purchase_amt, new_amt=purchase_amt, new_svc=ANY,
             why=BalanceXferToCauseTradingCancellation(trd_id=trd_id))
    ])


def test_cancel_buying_auction__empty(
        started_buying_auction
):
    'asking이 없음 cancel buying-auction.'
    trading_service = started_buying_auction.trading_service
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service
    event_writer_mock = started_buying_auction.event_writer_mock

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id

    # 취소.
    trading_service.cancel_trading(trd_id)

    assert trading_service.tradings[trd_id].state == TradingState.CANCELLED
    event_writer_mock.on_trading_cancelled.assert_has_calls([call(trd_id=trd_id)])

    # 아이템: 반환 없음.
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == 0

    # balance: 담보금 반환 없음. 구매대금만 환불.
    sec_deposit_amts = params.security_deposit_amt

    purchase_amt = params.price * params.qty

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        sec_deposit_amts

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == \
        purchase_amt
    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == 0

    event_writer_mock.on_balance_xfer_to.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=params.cust_id, curr=params.curr,
             amt=purchase_amt, new_amt=purchase_amt, new_svc=ANY,
             why=BalanceXferToCauseTradingCancellation(trd_id=trd_id))
    ])


def test_cancel_buying_auction__finalized(
        started_buying_auction
):
    'finalied된 cancel buying-auction.'
    trading_service = started_buying_auction.trading_service
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service
    event_writer_mock = started_buying_auction.event_writer_mock

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id

    seller_a = str(int(params.cust_id) + 1)
    seller_b = str(int(seller_a) + 1)

    sell_sec_deposit_amt_a = 123
    sell_sec_deposit_amt_b = 456

    price = params.price
    qty = params.qty

    # 담보금 입금.
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

    # finalize
    trading_service.finalize_trading(trd_id)

    # 취소.
    with raises(TradingIsNotCancellable):
        trading_service.cancel_trading(trd_id)

    assert trading_service.tradings[trd_id].state == TradingState.COMPLETED
    event_writer_mock.on_trading_cancelled.assert_not_called()

    # 아이템: 반환 없음.
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == qty
    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == qty
    assert item_count_service.get(cust_id=seller_a, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=seller_b, trd_id=trd_id) == 0

    # balance.
    sec_deposit_amts = params.security_deposit_amt + \
        sell_sec_deposit_amt_a + sell_sec_deposit_amt_b

    purchase_amt = params.price * params.qty

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        sec_deposit_amts

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_a, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_a, curr=params.curr) == \
        params.qty * params.price

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_b, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_b, curr=params.curr) == 0

    event_writer_mock.on_balance_xfer_to.assert_not_called()
