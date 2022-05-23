from unittest.mock import call, ANY
from pytest import raises  # type:ignore
from oev8.consts import SERVICE_CUSTOMER
from oev8.typedefs import TradingState, BalanceType, OrderOption
from oev8.values.event_writer import \
    BalanceCvtXferToCauseEarningPrep, ItemCountXferToCauseBuying, \
    BalanceXferToCauseRefundForUnmatchedLimitBuying
from oev8.excs import TradingIsNotCompletable


def test_selling_auction_finalize_trading__empty(
        started_selling_auction
):
    '빈 Auction을 finalize.'
    trading_service = started_selling_auction.trading_service
    balance_service = started_selling_auction.balance_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    # BEFORE
    assert trd.state == TradingState.OPEN

    svc_cust_balance_before = balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr)

    assert 0 == balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr)

    assert 0 == balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr)

    # 빈 Auction을 finalize.
    trading_service.finalize_trading(trd_id)

    # AFTER
    assert trd.state == TradingState.COMPLETED

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        svc_cust_balance_before

    assert 0 == balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr)

    assert 0 == balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr)

    # 완료 이벤트
    event_writer_mock.on_trading_finalized.assert_has_calls([
        call(trd_id=trd_id)
    ])

    # 판매자에게 수익금 = 0.
    event_writer_mock.on_balance_cvt_xfer_to.assert_has_calls([
        call(from_balance_type=BalanceType.BALANCE,
             to_balance_type=BalanceType.EARNING,
             cust_id=params.cust_id, curr=params.curr,
             amt=0, new_amt=0,  # 0-amt 이체.
             new_svc=ANY,
             why=BalanceCvtXferToCauseEarningPrep(trd_id=trd_id))
    ])

    # 구매자가 전혀 없으니까: 구매 대금 환불 없음, 아이템 전달 없음.
    event_writer_mock.on_item_count_xfer_to.assert_not_called()

    event_writer_mock.on_balance_xfer_to.assert_not_called()


def test_selling_auction_finalize_trading__cancelled(
        started_selling_auction
):
    'Cancelled Auction을 finalize.'
    trading_service = started_selling_auction.trading_service
    event_writer_mock = started_selling_auction.event_writer_mock

    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    # BEFORE
    trading_service.cancel_trading(trd_id)

    assert trd.state == TradingState.CANCELLED

    # 빈 Auction을 finalize.
    with raises(TradingIsNotCompletable):
        trading_service.finalize_trading(trd_id)

    # 완료 이벤트
    event_writer_mock.on_trading_finalized.assert_not_called()
    event_writer_mock.on_balance_cvt_xfer_to.assert_not_called()
    event_writer_mock.on_item_count_xfer_to.assert_not_called()
    event_writer_mock.on_balance_xfer_to.assert_not_called()


def test_selling_auction_finalize_trading__single_bidding_single_matching(
        started_selling_auction
):
    '매칭 1개 가능한 selling-auction을 finalize.'
    trading_service = started_selling_auction.trading_service
    balance_service = started_selling_auction.balance_service
    item_count_service = started_selling_auction.item_count_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    # BEFORE: Balances
    assert 0 == balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr)

    assert 0 == balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr)

    # 구매자.
    buyer_cust_id = str(int(params.cust_id) + 1)

    buyer_balance_amt = 1_000_000

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_cust_id,
        curr=params.curr,
        amt=buyer_balance_amt)

    price = params.price
    qty = 3

    ord_id = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_cust_id,
        price=price,
        qty=qty,
        option=OrderOption.NONE
    )

    order = trd.orders[ord_id]

    assert item_count_service.get(buyer_cust_id, trd_id) == 0

    # BEFORE: matches
    assert len(trd.matches) == 0

    #
    trading_service.finalize_trading(trd_id)

    # AFTER: order
    assert order.fulfilled
    assert not order.cancelled

    # AFTER: match
    assert len(trd.matches) == 1
    match = trd.matches[0]
    assert int(match.match_id) > 0
    assert match.qty == qty
    assert match.price == price
    assert match.making_taking_order_pair[0] == ord_id

    # 아이템 전달되었는지?
    event_writer_mock.on_item_count_xfer_to.assert_has_calls([
        call(cust_id=buyer_cust_id,
             trd_id=trd_id,
             qty=qty,
             new_qty=qty,
             new_svc=params.qty - qty,
             why=ItemCountXferToCauseBuying(match_id=match.match_id))
    ])

    assert item_count_service.get(buyer_cust_id, trd_id) == qty
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == \
        (params.qty - qty)

    # 구매 대금 환불: 없음.
    event_writer_mock.on_balance_xfer_to.assert_not_called()

    # 판매 수익금.
    earning_amt = price * qty

    assert 0 == balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr)

    assert earning_amt == balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr)

    event_writer_mock.on_balance_cvt_xfer_to.assert_has_calls([
        call(from_balance_type=BalanceType.BALANCE,
             to_balance_type=BalanceType.EARNING,
             cust_id=params.cust_id, curr=params.curr,
             amt=earning_amt, new_amt=earning_amt,
             new_svc=ANY,
             why=BalanceCvtXferToCauseEarningPrep(trd_id=trd_id))
    ])

    # 완료.
    assert trd.state == TradingState.COMPLETED

    event_writer_mock.on_trading_finalized.assert_has_calls([
        call(trd_id=trd_id)
    ])


def test_selling_auction_finalize_trading__01(
        started_selling_auction
):
    '''같은 가격의 2개 bid, 첫번째는 fulfilled, 두번째는 partially.

    부분매칭된 경우를 어떻게 처리하는지.'''
    trading_service = started_selling_auction.trading_service
    balance_service = started_selling_auction.balance_service
    item_count_service = started_selling_auction.item_count_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    # 구매자들, 구매자 잔고액.
    buyer_a = str(int(params.cust_id) + 1)
    buyer_b = str(int(buyer_a) + 1)

    buying_qty_a = 23
    buying_qty_b = 3
    buyer_balance_a = buying_qty_a * params.price
    buyer_balance_b = buying_qty_b * params.price

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_a,
        curr=params.curr,
        amt=buyer_balance_a)

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_b,
        curr=params.curr,
        amt=buyer_balance_b)

    price = params.price

    # be fulfilled
    buy_id_a = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_a,
        price=price,
        qty=buying_qty_a,
        option=OrderOption.NONE
    )

    # be partially filled
    buy_id_b = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_b,
        price=price,
        qty=buying_qty_b,
        option=OrderOption.NONE
    )

    # BEFORE: balances
    assert 0 == balance_service.get(
        BalanceType.BALANCE, cust_id=buyer_a, curr=params.curr)

    assert 0 == balance_service.get(
        BalanceType.BALANCE, cust_id=buyer_b, curr=params.curr)

    assert 0 == balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr)

    assert 0 == balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr)

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        params.security_deposit_amt + (buyer_balance_a + buyer_balance_b)

    #
    buy_a = trd.orders[buy_id_a]
    buy_b = trd.orders[buy_id_b]

    #
    trading_service.finalize_trading(trd_id)

    #
    assert buy_a.fulfilled
    assert not buy_b.cancelled
    assert not buy_b.fulfilled

    # 완료 이벤트
    assert trd.state == TradingState.COMPLETED

    event_writer_mock.on_trading_finalized.assert_has_calls([
        call(trd_id=trd_id)
    ])

    # matches
    match_a = trd.matches[0]
    assert match_a.qty == buying_qty_a
    assert match_a.price == params.price
    assert match_a.making_taking_order_pair[0] == buy_id_a

    match_b = trd.matches[1]
    assert match_b.qty == (params.qty - buying_qty_a)
    assert match_b.price == params.price
    assert match_b.making_taking_order_pair[0] == buy_id_b

    # buyer_a, buyer_b에게 구매한 아이템. (= [23, 2])
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == 0

    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == 0

    assert item_count_service.get(cust_id=buyer_a, trd_id=trd_id) == \
        buying_qty_a

    assert item_count_service.get(cust_id=buyer_b, trd_id=trd_id) == \
        params.qty - buying_qty_a

    event_writer_mock.on_item_count_xfer_to.assert_has_calls([
        call(cust_id=buyer_a,
             trd_id=trd_id,
             qty=buying_qty_a, new_qty=buying_qty_a,
             new_svc=(params.qty - buying_qty_a),
             why=ItemCountXferToCauseBuying(match_id=ANY)),
        call(cust_id=buyer_b,
             trd_id=trd_id,
             qty=(params.qty - buying_qty_a),
             new_qty=(params.qty - buying_qty_a),
             new_svc=0,
             why=ItemCountXferToCauseBuying(match_id=ANY))
    ])

    # 판매자 수익금.
    earnings = (match_a.qty * match_a.price) + \
        (match_b.qty * match_b.price)

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == \
        earnings

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        params.security_deposit_amt

    event_writer_mock.on_balance_cvt_xfer_to.assert_has_calls([
        call(from_balance_type=BalanceType.BALANCE,
             to_balance_type=BalanceType.EARNING,
             cust_id=params.cust_id, curr=params.curr,
             amt=earnings, new_amt=earnings,
             new_svc=ANY,
             why=BalanceCvtXferToCauseEarningPrep(trd_id=trd_id))
    ])

    # buyer_b (partially filled)에게 환불금.
    returning_amt_b = \
        (buying_qty_b - (params.qty - buying_qty_a)) * params.price

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=buyer_b, curr=params.curr) == \
        returning_amt_b

    event_writer_mock.on_balance_xfer_to.assert_has_calls([
        call(
            balance_type=BalanceType.BALANCE,
            cust_id=buyer_b, curr=params.curr,
            amt=returning_amt_b, new_amt=returning_amt_b,
            new_svc=params.security_deposit_amt + earnings,
            why=BalanceXferToCauseRefundForUnmatchedLimitBuying(
                trd_id=trd_id, ord_id=buy_id_b))
    ])


def test_selling_auction_finalize_trading__02(
        started_selling_auction
):
    '''같은 가격의 2개 bid, 첫번째만 fulfilled, 두번째는 모두 cancel.

    전체 매칭 안된 경우를 어떻게 처리하는지.'''
    trading_service = started_selling_auction.trading_service
    balance_service = started_selling_auction.balance_service
    item_count_service = started_selling_auction.item_count_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    # 구매자들, 구매자 잔고액.
    buyer_a = str(int(params.cust_id) + 1)
    buyer_b = str(int(buyer_a) + 1)

    buying_qty_a = 25
    buying_qty_b = 10
    buyer_balance_a = buying_qty_a * params.price
    buyer_balance_b = buying_qty_b * params.price

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_a,
        curr=params.curr,
        amt=buyer_balance_a)

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_b,
        curr=params.curr,
        amt=buyer_balance_b)

    price = params.price

    # be fulfilled
    buy_id_a = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_a,
        price=price,
        qty=buying_qty_a,
        option=OrderOption.NONE
    )

    # never be filled
    buy_id_b = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_b,
        price=price,
        qty=buying_qty_b,
        option=OrderOption.NONE
    )

    #
    buy_a = trd.orders[buy_id_a]
    buy_b = trd.orders[buy_id_b]

    #
    trading_service.finalize_trading(trd_id)

    #
    assert buy_a.fulfilled
    assert not buy_b.cancelled
    assert not buy_b.fulfilled

    # 완료 이벤트
    event_writer_mock.on_trading_finalized.assert_has_calls([call(trd_id=trd_id)])

    # buyer_a, buyer_b에게 구매한 아이템. (= [25, 0])
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == 0

    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == 0

    assert item_count_service.get(cust_id=buyer_a, trd_id=trd_id) == \
        buying_qty_a

    assert item_count_service.get(cust_id=buyer_b, trd_id=trd_id) == 0

    # 판매자 수익금.
    earnings = (buying_qty_a * price)

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == \
        earnings

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        params.security_deposit_amt

    # buyer_b에게 환불금.
    returning_amt_b = buying_qty_b * params.price

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=buyer_b, curr=params.curr) == \
        returning_amt_b


def test_selling_auction_finalize_trading__03(
        started_selling_auction
):
    '''비싼 buying부터 매칭하는지.

    그 다음으로 비싼 bidding은 전혀 매칭 기회가 없을 때.'''
    trading_service = started_selling_auction.trading_service
    balance_service = started_selling_auction.balance_service
    item_count_service = started_selling_auction.item_count_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    # 구매자들, 구매자 잔고액.
    buyer_a = str(int(params.cust_id) + 1)
    buyer_b = str(int(buyer_a) + 1)

    buying_qty_a = 25  # 둘 중 하나만 매칭됨.
    buying_qty_b = 25

    buying_price_a = params.price + 10
    buying_price_b = params.price + 11  # 두번째 bidding이지만 가격이 높아서.

    buyer_balance_a = buying_qty_a * buying_price_a
    buyer_balance_b = buying_qty_b * buying_price_b

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_a,
        curr=params.curr,
        amt=buyer_balance_a)

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_b,
        curr=params.curr,
        amt=buyer_balance_b)

    price = params.price

    #
    buy_id_a = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_a,
        price=buying_price_a,
        qty=buying_qty_a,
        option=OrderOption.NONE
    )

    buy_id_b = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_b,
        price=buying_price_b,
        qty=buying_qty_b,
        option=OrderOption.NONE
    )

    #
    buy_a = trd.orders[buy_id_a]
    buy_b = trd.orders[buy_id_b]

    #
    trading_service.finalize_trading(trd_id)

    #
    assert not buy_a.fulfilled
    assert buy_b.fulfilled

    # buyer_a, buyer_b에게 구매한 아이템. (= [0, 25])
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == 0

    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == 0

    assert item_count_service.get(cust_id=buyer_a, trd_id=trd_id) == 0

    assert item_count_service.get(cust_id=buyer_b, trd_id=trd_id) == \
        buying_qty_b


def test_selling_auction_finalize_trading__04(
        started_selling_auction
):
    '''비싼 buying부터 매칭하는지.

    그 다음으로 비싼 bidding은 부분 매칭.'''
    trading_service = started_selling_auction.trading_service
    balance_service = started_selling_auction.balance_service
    item_count_service = started_selling_auction.item_count_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    # 구매자들, 구매자 잔고액.
    buyer_a = str(int(params.cust_id) + 1)
    buyer_b = str(int(buyer_a) + 1)

    buying_qty_a = 20
    buying_qty_b = 20

    buying_price_a = params.price + 10
    buying_price_b = params.price + 11  # 두번째 bidding이지만 가격이 높아서.

    buyer_balance_a = buying_qty_a * buying_price_a
    buyer_balance_b = buying_qty_b * buying_price_b

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_a,
        curr=params.curr,
        amt=buyer_balance_a)

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_b,
        curr=params.curr,
        amt=buyer_balance_b)

    price = params.price

    # 매칭=5
    buy_id_a = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_a,
        price=buying_price_a,
        qty=buying_qty_a,
        option=OrderOption.NONE
    )

    # 매칭=20
    buy_id_b = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_b,
        price=buying_price_b,
        qty=buying_qty_b,
        option=OrderOption.NONE
    )

    #
    buy_a = trd.orders[buy_id_a]
    buy_b = trd.orders[buy_id_b]

    #
    trading_service.finalize_trading(trd_id)

    #
    assert not buy_a.fulfilled
    assert buy_b.fulfilled

    # buyer_a, buyer_b에게 구매한 아이템. (= [5, 20])
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == 0

    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == 0

    assert item_count_service.get(cust_id=buyer_a, trd_id=trd_id) == \
        params.qty - buying_qty_b

    assert item_count_service.get(cust_id=buyer_b, trd_id=trd_id) == \
        buying_qty_b


def test_selling_auction_finalize_trading__fok_ok(
        started_selling_auction
):
    '''FoK 매칭 성공.'''
    trading_service = started_selling_auction.trading_service
    balance_service = started_selling_auction.balance_service
    item_count_service = started_selling_auction.item_count_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    # 구매자들, 구매자 잔고액.
    buyer_a = str(int(params.cust_id) + 1)
    buyer_b = str(int(buyer_a) + 1)

    buying_qty_a = 20
    buying_qty_b = 20

    buying_price_a = params.price + 10
    buying_price_b = params.price + 11  # 두번째 bidding이지만 가격이 높아서.

    buyer_balance_a = buying_qty_a * buying_price_a
    buyer_balance_b = buying_qty_b * buying_price_b

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_a,
        curr=params.curr,
        amt=buyer_balance_a)

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_b,
        curr=params.curr,
        amt=buyer_balance_b)

    price = params.price

    # be fulfilled
    buy_id_a = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_a,
        price=buying_price_a,
        qty=buying_qty_a,
        option=OrderOption.NONE
    )

    # never be filled
    buy_id_b = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_b,
        price=buying_price_b,
        qty=buying_qty_b,
        option=OrderOption.FILL_OR_KILL
    )

    #
    buy_a = trd.orders[buy_id_a]
    buy_b = trd.orders[buy_id_b]

    #
    trading_service.finalize_trading(trd_id)

    #
    assert not buy_a.fulfilled
    assert buy_b.fulfilled

    # buyer_a, buyer_b에게 구매한 아이템. (= [5, 20])
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == 0

    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == 0

    assert item_count_service.get(cust_id=buyer_a, trd_id=trd_id) == \
        params.qty - buying_qty_b

    assert item_count_service.get(cust_id=buyer_b, trd_id=trd_id) == \
        buying_qty_b



def test_selling_auction_finalize_trading__fok_passing(
        started_selling_auction
):
    '''FoK 매칭 안될 때 건너뛰기.'''
    trading_service = started_selling_auction.trading_service
    balance_service = started_selling_auction.balance_service
    item_count_service = started_selling_auction.item_count_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    # 구매자들, 구매자 잔고액.
    buyer_a = str(int(params.cust_id) + 1)
    buyer_b = str(int(buyer_a) + 1)
    buyer_c = str(int(buyer_b) + 1)

    buying_qty_a = 20
    buying_qty_b = 20
    buying_qty_c = 20

    buying_price_a = params.price + 10
    buying_price_b = params.price + 11
    buying_price_c = params.price + 12

    buyer_balance_a = buying_qty_a * buying_price_a
    buyer_balance_b = buying_qty_b * buying_price_b
    buyer_balance_c = buying_qty_c * buying_price_c

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_a,
        curr=params.curr,
        amt=buyer_balance_a)

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_b,
        curr=params.curr,
        amt=buyer_balance_b)

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_c,
        curr=params.curr,
        amt=buyer_balance_c)

    price = params.price

    #
    buy_id_a = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_a,
        price=buying_price_a,
        qty=buying_qty_a,
        option=OrderOption.NONE
    )

    buy_id_b = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_b,
        price=buying_price_b,
        qty=buying_qty_b,
        option=OrderOption.FILL_OR_KILL
    )

    buy_id_c = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_c,
        price=buying_price_c,
        qty=buying_qty_c,
        option=OrderOption.NONE
    )


    #
    buy_a = trd.orders[buy_id_a]
    buy_b = trd.orders[buy_id_b]
    buy_c = trd.orders[buy_id_c]

    #
    trading_service.finalize_trading(trd_id)

    #
    assert not buy_a.fulfilled
    assert not buy_b.fulfilled
    assert buy_c.fulfilled

    # buyer_a, buyer_b에게 구매한 아이템. (= [5, 0, 20])
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == 0

    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == 0

    assert item_count_service.get(cust_id=buyer_a, trd_id=trd_id) == 5
    assert item_count_service.get(cust_id=buyer_b, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=buyer_c, trd_id=trd_id) == 20

    # buy_b은 중간 가격(+11)이어서, buy_c 가격(+12)이 20-qty 먼저 매칭되고,
    # 잔여 5-qty만으로는, 요청한 20-qty 매칭을 할 수 없으니, FoK이라 pass되고,
    # 그 다음 가격인 buy_a(+10)이 매칭되었음.


def test_selling_auction_finalize_trading__fok_passing_02(
        started_selling_auction
):
    '''FoK 매칭 안될 때 건너뛰기.

    이번엔  가장 높은 우선 순위로 평가가 되지만 FoK-passing될 때.'''
    trading_service = started_selling_auction.trading_service
    balance_service = started_selling_auction.balance_service
    item_count_service = started_selling_auction.item_count_service
    event_writer_mock = started_selling_auction.event_writer_mock

    params = started_selling_auction.start_new_selling_auction_params
    trd_id = started_selling_auction.trd_id
    trd = trading_service.tradings[trd_id]

    # 구매자들, 구매자 잔고액.
    buyer_a = str(int(params.cust_id) + 1)
    buyer_b = str(int(buyer_a) + 1)
    buyer_c = str(int(buyer_b) + 1)

    buying_qty_a = 20
    buying_qty_b = 100  # FoK: fulfill되기엔 너무 많은 수량 요청.
    buying_qty_c = 20

    buying_price_a = params.price + 10
    buying_price_b = params.price + 100  # 가장 높은 가격.
    buying_price_c = params.price + 12

    buyer_balance_a = buying_qty_a * buying_price_a
    buyer_balance_b = buying_qty_b * buying_price_b
    buyer_balance_c = buying_qty_c * buying_price_c

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_a,
        curr=params.curr,
        amt=buyer_balance_a)

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_b,
        curr=params.curr,
        amt=buyer_balance_b)

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=buyer_c,
        curr=params.curr,
        amt=buyer_balance_c)

    price = params.price

    #
    buy_id_a = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_a,
        price=buying_price_a,
        qty=buying_qty_a,
        option=OrderOption.NONE
    )

    buy_id_b = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_b,
        price=buying_price_b,
        qty=buying_qty_b,
        option=OrderOption.FILL_OR_KILL
    )

    buy_id_c = trading_service.bid_buying(
        trd_id=trd_id,
        cust_id=buyer_c,
        price=buying_price_c,
        qty=buying_qty_c,
        option=OrderOption.NONE
    )


    #
    buy_a = trd.orders[buy_id_a]
    buy_b = trd.orders[buy_id_b]
    buy_c = trd.orders[buy_id_c]

    #
    trading_service.finalize_trading(trd_id)

    #
    assert not buy_a.fulfilled
    assert not buy_b.fulfilled
    assert buy_c.fulfilled

    # buyer_a, buyer_b에게 구매한 아이템. (= [5, 0, 20])
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == 0

    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == 0

    assert item_count_service.get(cust_id=buyer_a, trd_id=trd_id) == 5
    assert item_count_service.get(cust_id=buyer_b, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=buyer_c, trd_id=trd_id) == 20
