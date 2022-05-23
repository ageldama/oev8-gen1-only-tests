from unittest.mock import call, ANY
from pytest import raises  # type:ignore
from pytest import mark  # type:ignore
from oev8.consts import SERVICE_CUSTOMER
from oev8.typedefs import BalanceType, OrderOption, SeqType
from oev8.typedefs import OrderType, OrderSide, TradingType
from oev8.values.event_writer import \
    BalanceXferFromCauseSecurityDeposit, ItemCountXferFromCauseSelling
from oev8.excs import NotEnoughBalance, CurrencyAmtShouldBePositive, \
    ItemQtyShouldBePositive, TradingIsNotOpened, TradingIsNotFound, \
    UnsatisfyingAuctionAskPrice
from test.testsup import assert_orderbook


def test_ask_selling__ok(
        started_buying_auction,
        seq_num_service
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

    security_deposit_amt = 100

    # 구매할 자금.
    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller,
        curr=params.curr,
        amt=security_deposit_amt)

    # BEFORE: 주문 전의 ord_seq
    before_cur_ord_id = seq_num_service.cur_val(SeqType.ORDER)

    # BEFORE: 주문 전의 SERVICE_CUSTOMER의 잔고.
    svc_cust_balance_before = balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr)

    # BEFORE: 주문 전의 item-counts
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0
    assert item_count_service.get(seller, trd_id) == 0

    # bid!
    ord_id = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller,
        price=price,
        qty=qty,
        security_deposit_amt=security_deposit_amt,
        option=OrderOption.NONE
    )

    # order id 증가 확인.
    assert before_cur_ord_id < ord_id

    # orders and auctions_bids
    assert ord_id in trd.orders
    assert price in trd.auction_bids
    assert trd.auction_bids[price][ord_id] == qty

    order = trd.orders[ord_id]

    assert order.cust_id == seller
    assert order.order_type == OrderType.LIMIT
    assert order.side == OrderSide.SELL
    assert order.option == OrderOption.NONE
    assert order.price == price
    assert order.qty == qty
    assert not order.fulfilled
    assert not order.cancelled

    # balances & on_balance_xfer_from
    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller, curr=params.curr) == \
        0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        (security_deposit_amt + svc_cust_balance_before)

    event_writer_mock.on_balance_xfer_from.assert_has_calls([
        call(
            balance_type=BalanceType.BALANCE,
            cust_id=seller,
            curr=params.curr,
            amt=security_deposit_amt,
            new_amt=0,
            new_svc=security_deposit_amt + svc_cust_balance_before,
            why=BalanceXferFromCauseSecurityDeposit(trd_id=trd_id))])

    # on_trading_limit_buy_order
    event_writer_mock.on_trading_limit_sell_order.assert_has_calls([
        call(
            trd_id=trd_id,
            ord_id=ord_id,
            cust_id=seller,
            price=params.price,
            qty=params.qty,
            option=OrderOption.NONE)])

    # item-providing
    event_writer_mock.on_trading_provide_item.assert_has_calls([
        call(trd_id=trd_id,
             cust_id=seller,
             qty=qty,
             new_qty=qty)
    ])

    event_writer_mock.on_item_count_xfer_from.assert_has_calls([
        call(cust_id=seller, trd_id=trd_id,
             qty=params.qty, new_qty=0, new_svc=params.qty,
             why=ItemCountXferFromCauseSelling(ord_id=ord_id))
    ])

    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == params.qty
    assert item_count_service.get(seller, trd_id) == 0

    # 적절한 오더북 상태인지?
    # -- 정렬이 제대로 가능한지 (integer-keyed, sorted-dicts)
    trd = trading_service.tradings[trd_id]
    assert_orderbook(trd.auction_bids)


def test_ask_selling__insufficient_balance(
        started_buying_auction
):
    '담보금 부족.'
    trading_service = started_buying_auction.trading_service
    event_writer_mock = started_buying_auction.event_writer_mock
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id
    trd = trading_service.tradings[trd_id]

    seller = str(int(params.cust_id) + 1)

    price = params.price
    qty = params.qty
    security_deposit_amt = 1234

    #
    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller, curr=params.curr) == 0

    assert item_count_service.get(seller, trd_id) == 0
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0

    # ask!
    with raises(NotEnoughBalance):
        trading_service.ask_selling(
            trd_id=trd_id,
            cust_id=seller,
            price=price,
            qty=qty,
            security_deposit_amt=security_deposit_amt,
            option=OrderOption.NONE
        )

    #
    assert len(trd.orders) == 0
    assert len(trd.auction_bids) == 0

    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_sell_order.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()

    event_writer_mock.on_item_count_xfer_from.assert_not_called()

    assert item_count_service.get(seller, trd_id) == 0
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0


def test_ask_selling__zero_price(
        started_buying_auction
):
    '가격=0.'
    trading_service = started_buying_auction.trading_service
    event_writer_mock = started_buying_auction.event_writer_mock
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id
    trd = trading_service.tradings[trd_id]

    seller = str(int(params.cust_id) + 1)

    qty = params.qty
    security_deposit_amt = 123

    #
    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=params.cust_id,
        curr=params.curr,
        amt=security_deposit_amt)

    # bid!
    with raises(CurrencyAmtShouldBePositive):
        trading_service.ask_selling(
            trd_id=trd_id,
            cust_id=seller,
            price=0,
            qty=qty,
            security_deposit_amt=security_deposit_amt,
            option=OrderOption.NONE
        )

    #
    assert len(trd.orders) == 0
    assert len(trd.auction_bids) == 0

    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_sell_order.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()

    event_writer_mock.on_item_count_xfer_from.assert_not_called()

    assert item_count_service.get(seller, trd_id) == 0
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0


def test_ask_selling__zero_qty(
        started_buying_auction
):
    'qty=0.'
    trading_service = started_buying_auction.trading_service
    event_writer_mock = started_buying_auction.event_writer_mock
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id
    trd = trading_service.tradings[trd_id]

    seller = str(int(params.cust_id) + 1)

    qty = 0
    security_deposit_amt = 123

    #
    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=params.cust_id,
        curr=params.curr,
        amt=security_deposit_amt)

    # bid!
    with raises(ItemQtyShouldBePositive):
        trading_service.ask_selling(
            trd_id=trd_id,
            cust_id=seller,
            price=params.qty,
            qty=qty,
            security_deposit_amt=security_deposit_amt,
            option=OrderOption.NONE
        )

    #
    assert len(trd.orders) == 0
    assert len(trd.auction_bids) == 0

    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_sell_order.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()

    event_writer_mock.on_item_count_xfer_from.assert_not_called()

    assert item_count_service.get(seller, trd_id) == 0
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0


def test_ask_selling__on_paused_trading(
        started_buying_auction
):
    'paused된 장터에 bid.'
    trading_service = started_buying_auction.trading_service
    event_writer_mock = started_buying_auction.event_writer_mock
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id
    trd = trading_service.tradings[trd_id]

    seller = str(int(params.cust_id) + 1)

    price = params.price
    qty = params.qty

    security_deposit_amt = 123

    #
    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller,
        curr=params.curr,
        amt=security_deposit_amt)

    # PAUSE
    trading_service.pause_trading(trd_id=trd_id)

    # ask!
    with raises(TradingIsNotOpened):
        trading_service.ask_selling(
            trd_id=trd_id,
            cust_id=seller,
            price=price,
            qty=qty,
            security_deposit_amt=security_deposit_amt,
            option=OrderOption.NONE
        )

    #
    assert len(trd.orders) == 0
    assert len(trd.auction_bids) == 0

    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_buy_order.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()
    event_writer_mock.on_item_count_xfer_from.assert_not_called()

    assert item_count_service.get(seller, trd_id) == 0
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0


def test_ask_selling__non_existing_trd_id(
        started_buying_auction
):
    '없는 trd_id에 bidding.'
    trading_service = started_buying_auction.trading_service
    event_writer_mock = started_buying_auction.event_writer_mock
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id
    trd = trading_service.tradings[trd_id]

    seller = str(int(params.cust_id) + 1)

    price = params.price
    qty = params.qty
    security_deposit_amt = 123

    #
    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller,
        curr=params.curr,
        amt=security_deposit_amt)

    # ask!
    with raises(TradingIsNotFound):
        trading_service.ask_selling(
            trd_id=trd_id * 2,
            cust_id=seller,
            price=price,
            qty=qty,
            security_deposit_amt=security_deposit_amt,
            option=OrderOption.NONE
        )

    #
    assert len(trd.orders) == 0
    assert len(trd.auction_bids) == 0

    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_buy_order.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()
    event_writer_mock.on_item_count_xfer_from.assert_not_called()

    assert item_count_service.get(seller, trd_id) == 0
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0


def test_ask_selling__non_auction_trd(
        started_buying_auction
):
    'TradingType.AUCTION 아닌 trd에 asking.'
    trading_service = started_buying_auction.trading_service
    balance_service = started_buying_auction.balance_service
    event_writer_mock = started_buying_auction.event_writer_mock
    item_count_service = started_buying_auction.item_count_service

    params = started_buying_auction.start_new_buying_auction_params
    # print('PARAMS:', params)
    trd_id = started_buying_auction.trd_id
    trd = trading_service.tradings[trd_id]

    seller = str(int(params.cust_id) + 111)

    price = params.price
    qty = params.qty
    security_deposit_amt = 123

    #
    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller,
        curr=params.curr,
        amt=security_deposit_amt)

    # EXCHANGE 준비.
    exch_cust_id = str(int(seller) + 1)
    trd2_id = str(int(trd_id) + 1)

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=exch_cust_id,
        curr=params.curr,
        amt=100)

    sell_ord_id = trading_service.start_new_trading_as_seller(
        cust_id=exch_cust_id,
        trd_id=trd2_id,
        curr=params.curr,
        security_deposit_amt=2,
        qty=3,
        limit_sell_unit_price=6,
        until_utc_timestamp_secs=params.until_utc_timestamp_secs
    )

    # print('SELL_ORD_ID:', repr(sell_ord_id))

    trd2 = trading_service.tradings[trd2_id]

    assert trd2.trading_type == TradingType.EXCHANGE

    event_writer_mock.on_balance_xfer_from.reset_mock()
    event_writer_mock.on_item_count_xfer_from.reset_mock()
    event_writer_mock.on_trading_provide_item.reset_mock()
    event_writer_mock.on_trading_new.reset_mock()
    # trading_clockwork_service.regist.reset_mock()

    # ask!
    with raises(TradingIsNotFound):
        trading_service.ask_selling(
            trd_id=trd2_id,
            cust_id=seller,
            price=price,
            qty=qty,
            security_deposit_amt=security_deposit_amt,
            option=OrderOption.NONE
        )

    # sells에는 들어갔지만, bidding은 들어가지 않았음.
    # (sell은 start_new_trading_as_seller 하면서 자동으로.)
    assert len(trd2.orders) == 1
    assert sell_ord_id in trd2.orders

    assert len(trd2.sells) == 1
    assert sell_ord_id in trd2.sells[6]

    assert len(trd2.auction_bids) == 0

    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_buy_order.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()
    event_writer_mock.on_item_count_xfer_from.assert_not_called()

    assert item_count_service.get(seller, trd_id) == 0
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0


def test_ask_selling__greater_price(
        started_buying_auction
):
    '너무 비싼 가격에 asking.'
    trading_service = started_buying_auction.trading_service
    event_writer_mock = started_buying_auction.event_writer_mock
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id
    trd = trading_service.tradings[trd_id]

    seller = str(int(params.cust_id) + 1)

    price = params.price + 1
    qty = params.qty
    security_deposit_amt = 123

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller,
        curr=params.curr,
        amt=security_deposit_amt)

    # bid!
    with raises(UnsatisfyingAuctionAskPrice):
        trading_service.ask_selling(
            trd_id=trd_id,
            cust_id=seller,
            price=price,
            qty=qty,
            security_deposit_amt=security_deposit_amt,
            option=OrderOption.NONE
        )

    #
    assert len(trd.orders) == 0
    assert len(trd.auction_bids) == 0

    event_writer_mock.on_balance_xfer_from.assert_not_called()
    event_writer_mock.on_trading_limit_buy_order.assert_not_called()
    event_writer_mock.on_trading_provide_item.assert_not_called()
    event_writer_mock.on_item_count_xfer_from.assert_not_called()

    assert item_count_service.get(seller, trd_id) == 0
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0
