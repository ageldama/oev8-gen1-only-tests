from unittest.mock import call, ANY
from pytest import raises  # type:ignore
from pytest import mark  # type:ignore
from oev8.consts import SERVICE_CUSTOMER
from oev8.typedefs import BalanceType, OrderOption, SeqType
from oev8.typedefs import OrderType, OrderSide, TradingType
from oev8.values.event_writer import \
    TradingOrderCancelCauseUserCancel, \
    BalanceXferToCauseRefundForUnmatchedLimitBuying
from oev8.excs import NotEnoughBalance, CurrencyAmtShouldBePositive, \
    ItemQtyShouldBePositive, TradingIsNotOpened, TradingIsNotFound, \
    UnsatisfyingAuctionBidPrice


def test_cancel_ask_selling__ok(
        started_buying_auction
):
    trading_service = started_buying_auction.trading_service
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service
    event_writer_mock = started_buying_auction.event_writer_mock

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id
    trd = trading_service.tradings[trd_id]

    seller = str(int(params.cust_id) + 1)

    price = params.price
    qty = params.qty

    sell_sec_deposit_amt = 123

    # 판매자 담보금.
    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller,
        curr=params.curr,
        amt=sell_sec_deposit_amt)

    # ask!
    ord_id = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller,
        price=price,
        qty=qty,
        security_deposit_amt=sell_sec_deposit_amt,
        option=OrderOption.NONE
    )

    order = trd.orders[ord_id]

    assert not order.cancelled

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        params.security_deposit_amt + sell_sec_deposit_amt + \
        (params.price * params.qty)

    # 취소.
    trading_service.cancel_remaining_offer(
        trd_id=trd_id, ord_id=ord_id)

    assert order.cancelled

    # orders?
    assert ord_id not in trd.orders
    assert price not in trd.auction_bids

    # 취소 이벤트
    event_writer_mock.on_trading_order_cancelled.assert_has_calls([
        call(trd_id=trd_id, ord_id=ord_id, cust_id=seller,
             price=price, qty=qty, remaining_qty=qty,
             why=TradingOrderCancelCauseUserCancel())
    ])

    event_writer_mock.on_trading_order_cancelled.assert_called_once()

    # 담보금 환불 없음, 아이템 unprovide.
    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == 0

    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=seller, trd_id=trd_id) == params.qty

    event_writer_mock.on_item_count_xfer_to.assert_not_called()


def test_cancel_ask_selling__paused(
        started_buying_auction
):
    trading_service = started_buying_auction.trading_service
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service
    event_writer_mock = started_buying_auction.event_writer_mock

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id
    trd = trading_service.tradings[trd_id]

    seller = str(int(params.cust_id) + 1)

    price = params.price
    qty = params.qty

    sell_sec_deposit_amt = 123

    # 판매자 담보금.
    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller,
        curr=params.curr,
        amt=sell_sec_deposit_amt)

    # ask!
    ord_id = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller,
        price=price,
        qty=qty,
        security_deposit_amt=sell_sec_deposit_amt,
        option=OrderOption.NONE
    )

    order = trd.orders[ord_id]

    assert not order.cancelled

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        params.security_deposit_amt + sell_sec_deposit_amt + \
        (params.price * params.qty)

    # pause
    trading_service.pause_trading(trd_id)

    # 취소.
    with raises(TradingIsNotOpened):
        trading_service.cancel_remaining_offer(
            trd_id=trd_id, ord_id=ord_id)

    assert not order.cancelled

    # orders?
    assert ord_id in trd.orders
    assert price in trd.auction_bids

    # 취소 이벤트
    event_writer_mock.on_trading_order_cancelled.assert_not_called()

    # 담보금 환불 없음, 아이템 그대로 svc-cust.
    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == 0

    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == params.qty
    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=seller, trd_id=trd_id) == 0

    event_writer_mock.on_item_count_xfer_to.assert_not_called()


def test_cancel_ask_selling__finalized(
        started_buying_auction
):
    trading_service = started_buying_auction.trading_service
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service
    event_writer_mock = started_buying_auction.event_writer_mock

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id
    trd = trading_service.tradings[trd_id]

    seller = str(int(params.cust_id) + 1)

    price = params.price
    qty = params.qty

    sell_sec_deposit_amt = 123

    # 판매자 담보금.
    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller,
        curr=params.curr,
        amt=sell_sec_deposit_amt)

    # ask!
    ord_id = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller,
        price=price,
        qty=qty,
        security_deposit_amt=sell_sec_deposit_amt,
        option=OrderOption.NONE
    )

    order = trd.orders[ord_id]

    assert not order.cancelled

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        params.security_deposit_amt + sell_sec_deposit_amt + \
        (params.price * params.qty)

    # pause
    trading_service.finalize_trading(trd_id)

    # 취소.
    with raises(TradingIsNotOpened):
        trading_service.cancel_remaining_offer(
            trd_id=trd_id, ord_id=ord_id)

    assert not order.cancelled

    # orders?
    assert ord_id in trd.orders
    assert price in trd.auction_bids

    # 취소 이벤트
    event_writer_mock.on_trading_order_cancelled.assert_not_called()

    # 담보금 환불 없음, 아이템 그대로 svc-cust.
    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller, curr=params.curr) == \
        (params.qty * params.price)

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == 0

    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == params.qty
    assert item_count_service.get(cust_id=seller, trd_id=trd_id) == 0

    event_writer_mock.on_item_count_xfer_to.assert_called_once()


def test_cancel_ask_selling__passed_on_matching(
        started_buying_auction
):
    '여러개의 asking이 있고, cancel된 asking은 건너뛰고 매칭되는지?'
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

    sec_deposit_amt_a = 123
    sec_deposit_amt_b = 456

    # 판매 담보금.
    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller_a,
        curr=params.curr,
        amt=sec_deposit_amt_a)

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller_b,
        curr=params.curr,
        amt=sec_deposit_amt_b)

    # ask!
    sell_id_a = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller_a,
        price=price,
        qty=qty,
        security_deposit_amt=sec_deposit_amt_a,
        option=OrderOption.NONE
    )

    sell_id_b = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller_b,
        price=price,
        qty=qty,
        security_deposit_amt=sec_deposit_amt_b,
        option=OrderOption.NONE
    )

    # 취소.
    trading_service.cancel_remaining_offer(
        trd_id=trd_id, ord_id=sell_id_a)

    # Finalize
    trading_service.finalize_trading(trd_id)

    # balances
    sec_deposit_amts = params.security_deposit_amt + \
        sec_deposit_amt_a + sec_deposit_amt_b

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
        BalanceType.EARNING, cust_id=seller_a, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_b, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_b, curr=params.curr) == \
        params.price * params.qty
