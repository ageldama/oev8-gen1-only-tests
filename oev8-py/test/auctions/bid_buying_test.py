from unittest.mock import call, ANY
from pytest import raises  # type:ignore
from oev8.consts import SERVICE_CUSTOMER
from oev8.typedefs import BalanceType, OrderOption, SeqType
from oev8.typedefs import OrderType, OrderSide, TradingType
from oev8.values.event_writer import \
    BalanceXferFromCauseBuying
from oev8.excs import NotEnoughBalance, CurrencyAmtShouldBePositive, \
    ItemQtyShouldBePositive, TradingIsNotOpened, TradingIsNotFound, \
    UnsatisfyingAuctionBidPrice
from test.testsup import assert_orderbook


def test_bid_buying__ok(
        started_selling_auction,
        seq_num_service
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

    # BEFORE: 주문 전의 ord_seq
    before_cur_ord_id = seq_num_service.cur_val(SeqType.ORDER)

    # BEFORE: 주문 전의 SERVICE_CUSTOMER의 잔고.
    svc_cust_balance_before = balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr)

    # bid!
    ord_id = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_cust_id,
        price=price,
        qty=qty,
        option=OrderOption.NONE
    )

    # order id 증가 확인.
    assert before_cur_ord_id < ord_id

    # orders and auctions_bids
    assert ord_id in trd.orders
    assert price in trd.auction_bids
    assert trd.auction_bids[price][ord_id] == qty

    order = trd.orders[ord_id]

    assert order.cust_id == buyer_cust_id
    assert order.order_type == OrderType.LIMIT
    assert order.side == OrderSide.BUY
    assert order.option == OrderOption.NONE
    assert order.price == price
    assert order.qty == qty
    assert not order.fulfilled
    assert not order.cancelled

    # balances & on_balance_xfer_from
    assert balance_service.get(
        BalanceType.BALANCE, cust_id=buyer_cust_id, curr=params.curr) == \
        0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        ((price * qty) + svc_cust_balance_before)

    event_writer_mock.on_balance_xfer_from.assert_has_calls([
        call(
            balance_type=BalanceType.BALANCE,
            cust_id=buyer_cust_id,
            curr=params.curr,
            amt=(price * qty),
            new_amt=0,
            new_svc=ANY,
            why=BalanceXferFromCauseBuying(trd_id=trd_id, ord_id=ord_id))])

    # on_trading_limit_buy_order
    event_writer_mock.on_trading_limit_buy_order.assert_has_calls([
        call(
            trd_id=trd_id,
            ord_id=ord_id,
            cust_id=buyer_cust_id,
            price=params.price,
            qty=params.qty,
            option=OrderOption.NONE)])

    # 적절한 오더북 상태인지?
    # -- 정렬이 제대로 가능한지 (integer-keyed, sorted-dicts)
    trd = trading_service.tradings[trd_id]
    assert_orderbook(trd.auction_bids)


def test_bid_buying__insufficient_balance(
        started_selling_auction
):
    '구매할 자금 없이.'
    trading_service = started_selling_auction.trading_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    buyer_cust_id = str(int(params.cust_id) + 1)

    price = params.price
    qty = params.qty

    # bid!
    with raises(NotEnoughBalance):
        trading_service.bid_buying(
            trd_id=trd_id,
            cust_id=buyer_cust_id,
            price=price,
            qty=qty,
            option=OrderOption.NONE
        )

    #
    assert len(trd.orders) == 0
    assert len(trd.auction_bids) == 0

    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_buy_order.assert_not_called()


def test_bid_buying__zero_price(
        started_selling_auction
):
    '가격=0.'
    trading_service = started_selling_auction.trading_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    buyer_cust_id = str(int(params.cust_id) + 1)

    qty = params.qty

    # bid!
    with raises(CurrencyAmtShouldBePositive):
        trading_service.bid_buying(
            trd_id=trd_id,
            cust_id=buyer_cust_id,
            price=0,
            qty=qty,
            option=OrderOption.NONE
        )

    #
    assert len(trd.orders) == 0
    assert len(trd.auction_bids) == 0

    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_buy_order.assert_not_called()


def test_bid_buying__zero_qty(
        started_selling_auction
):
    'qty=0.'
    trading_service = started_selling_auction.trading_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    buyer_cust_id = str(int(params.cust_id) + 1)

    price = params.price

    # bid!
    with raises(ItemQtyShouldBePositive):
        trading_service.bid_buying(
            trd_id=trd_id,
            cust_id=buyer_cust_id,
            price=price,
            qty=0,
            option=OrderOption.NONE
        )

    #
    assert len(trd.orders) == 0
    assert len(trd.auction_bids) == 0

    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_buy_order.assert_not_called()


def test_bid_buying__on_paused_trading(
        started_selling_auction
):
    'paused된 장터에 bid.'
    trading_service = started_selling_auction.trading_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    buyer_cust_id = str(int(params.cust_id) + 1)

    price = params.price
    qty = params.qty

    # PAUSE
    trading_service.pause_trading(trd_id=trd_id)

    # bid!
    with raises(TradingIsNotOpened):
        trading_service.bid_buying(
            trd_id=trd_id,
            cust_id=buyer_cust_id,
            price=price,
            qty=qty,
            option=OrderOption.NONE
        )

    #
    assert len(trd.orders) == 0
    assert len(trd.auction_bids) == 0

    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_buy_order.assert_not_called()


def test_bid_buying__non_existing_trd_id(
        started_selling_auction
):
    '없는 trd_id에 bidding.'
    trading_service = started_selling_auction.trading_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    buyer_cust_id = str(int(params.cust_id) + 1)

    price = params.price
    qty = params.qty

    # bid!
    with raises(TradingIsNotFound):
        trading_service.bid_buying(
            trd_id=trd_id * 2,
            cust_id=buyer_cust_id,
            price=price,
            qty=qty,
            option=OrderOption.NONE
        )

    #
    assert len(trd.orders) == 0
    assert len(trd.auction_bids) == 0

    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_buy_order.assert_not_called()


def test_bid_buying__non_auction_trd(
        started_selling_auction
):
    'TradingType.AUCTION 아닌 trd에 bidding.'
    trading_service = started_selling_auction.trading_service
    balance_service = started_selling_auction.balance_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    buyer_cust_id = str(int(params.cust_id) + 1)

    price = params.price
    qty = params.qty

    # EXCHANGE 준비.
    seller_cust_id = str(int(buyer_cust_id) + 1)
    trd2_id = str(int(trd_id) + 1)

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller_cust_id,
        curr=params.curr,
        amt=1)

    sell_ord_id = trading_service.start_new_trading_as_seller(
        cust_id=seller_cust_id,
        trd_id=trd2_id,
        curr=params.curr,
        security_deposit_amt=1,
        qty=1,
        limit_sell_unit_price=9,
        until_utc_timestamp_secs=params.until_utc_timestamp_secs
    )

    trd2 = trading_service.tradings[trd2_id]

    assert trd2.trading_type == TradingType.EXCHANGE

    event_writer_mock.on_balance_xfer_from.reset_mock()
    event_writer_mock.on_item_count_xfer_from.reset_mock()
    event_writer_mock.on_trading_provide_item.reset_mock()
    event_writer_mock.on_trading_new.reset_mock()
    # trading_clockwork_service.regist.reset_mock()

    # bid!
    with raises(TradingIsNotFound):
        trading_service.bid_buying(
            trd_id=trd2_id,
            cust_id=buyer_cust_id,
            price=price,
            qty=qty,
            option=OrderOption.NONE
        )

    # sells에는 들어갔지만, bidding은 들어가지 않았음.
    # (sell은 start_new_trading_as_seller 하면서 자동으로.)
    assert len(trd2.orders) == 1
    assert sell_ord_id in trd2.orders

    assert len(trd2.sells) == 1
    assert sell_ord_id in trd2.sells[9]

    assert len(trd2.auction_bids) == 0

    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_buy_order.assert_not_called()


def test_bid_buying__lesser_price(
        started_selling_auction
):
    '너무 싼 가격에 bidding.'
    trading_service = started_selling_auction.trading_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    buyer_cust_id = str(int(params.cust_id) + 1)

    price = 1
    qty = params.qty

    # bid!
    with raises(UnsatisfyingAuctionBidPrice):
        trading_service.bid_buying(
            trd_id=trd_id,
            cust_id=buyer_cust_id,
            price=price,
            qty=qty,
            option=OrderOption.NONE
        )

    #
    assert len(trd.orders) == 0
    assert len(trd.auction_bids) == 0

    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_buy_order.assert_not_called()
