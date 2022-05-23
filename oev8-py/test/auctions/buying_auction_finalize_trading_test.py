from unittest.mock import call, ANY
from pytest import raises  # type:ignore
from pytest import mark  # type:ignore
from oev8.consts import SERVICE_CUSTOMER
from oev8.typedefs import TradingState, BalanceType, OrderOption
from oev8.values.event_writer import \
    BalanceCvtXferToCauseEarningPrep, ItemCountXferToCauseBuying, \
    BalanceXferToCauseRefundForUnmatchedLimitBuying, \
    BalanceXferToCauseTradingCancellation, \
    ItemCountXferFromCauseSelling, \
    BalanceXferFromCauseSecurityDeposit
from oev8.excs import TradingIsNotCompletable


def test_buying_auction_finalize_trading__empty(
        started_buying_auction
):
    '빈 Auction을 finalize.'
    trading_service = started_buying_auction.trading_service
    balance_service = started_buying_auction.balance_service
    event_writer_mock = started_buying_auction.event_writer_mock

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id
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

    # 구매대금은 환불, 담보금은 그대로.
    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        svc_cust_balance_before - (params.price * params.qty)

    # 구매대금 환불
    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=params.cust_id, curr=params.curr) == \
                               (params.price * params.qty)

    assert 0 == balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr)

    # 완료 이벤트
    event_writer_mock.on_trading_finalized.assert_has_calls([
        call(trd_id=trd_id)
    ])

    # 판매자에게 수익금 = 0.
    event_writer_mock.on_balance_cvt_xfer_to.assert_not_called()

    # 구매자가 전혀 없으니까: 구매 대금 환불 없음, 아이템 전달 없음.
    event_writer_mock.on_item_count_xfer_to.assert_not_called()

    # 구매대금 환불
    event_writer_mock.on_balance_xfer_to.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=params.cust_id, curr=params.curr,
             amt=params.price * params.qty,
             new_amt=params.price * params.qty,
             new_svc=params.security_deposit_amt,
             why=BalanceXferToCauseRefundForUnmatchedLimitBuying(
                 trd_id=params.trd_id, ord_id=ANY))
    ])


def test_buying_auction_finalize_trading__cancelled(
        started_buying_auction
):
    'Cancelled Auction을 finalize.'
    trading_service = started_buying_auction.trading_service
    event_writer_mock = started_buying_auction.event_writer_mock
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service

    params = started_buying_auction.start_new_buying_auction_params

    trd_id = started_buying_auction.trd_id
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

    # 구매대금 환불
    event_writer_mock.on_balance_xfer_to.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=params.cust_id, curr=params.curr,
             amt=params.price * params.qty,
             new_amt=params.price * params.qty,
             new_svc=params.security_deposit_amt,
             why=BalanceXferToCauseTradingCancellation(
                 trd_id=params.trd_id))
    ])

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        params.security_deposit_amt

    assert balance_service.get(BalanceType.BALANCE,
                               cust_id=params.cust_id, curr=params.curr) == \
                               (params.price * params.qty)

    assert 0 == balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr)

    # 아이템
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0
    assert item_count_service.get(params.cust_id, trd_id) == 0


def test_buying_auction_finalize_trading__single_asking_single_matching(
        started_buying_auction
):
    '매칭 1개 가능한 buying-auction을 finalize.'
    trading_service = started_buying_auction.trading_service
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service
    event_writer_mock = started_buying_auction.event_writer_mock

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id
    trd = trading_service.tradings[trd_id]

    # BEFORE: Balances
    assert 0 == balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr)

    assert 0 == balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr)

    # 판매자.
    seller = str(int(params.cust_id) + 1)

    seller_balance_amt = 1_000_000

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller,
        curr=params.curr,
        amt=seller_balance_amt)

    price = params.price
    qty = 3
    seller_security_deposit_amt = 123

    ord_id = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller,
        price=price,
        qty=qty,
        security_deposit_amt=seller_security_deposit_amt,
        option=OrderOption.NONE
    )

    order = trd.orders[ord_id]

    assert item_count_service.get(seller, trd_id) == 0
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == qty

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
    assert match.match_id > 0
    assert match.qty == qty
    assert match.price == price
    assert match.making_taking_order_pair[0] == ord_id

    # 아이템 전달되었는지?
    event_writer_mock.on_item_count_xfer_to.assert_has_calls([
        call(cust_id=params.cust_id,
             trd_id=trd_id,
             qty=qty,
             new_qty=qty,
             new_svc=0,
             why=ItemCountXferToCauseBuying(match_id=match.match_id))
    ])

    assert item_count_service.get(params.cust_id, trd_id) == qty
    assert item_count_service.get(seller, trd_id) == 0
    assert item_count_service.get(SERVICE_CUSTOMER, trd_id) == 0

    # 구매 대금 환불.
    refund_amt = params.price * (params.qty - qty)
    svc_amt = params.security_deposit_amt + seller_security_deposit_amt
    event_writer_mock.on_balance_xfer_to.assert_has_calls([
        call(balance_type=BalanceType.BALANCE, cust_id=params.cust_id,
             curr=params.curr,
             amt=refund_amt, new_amt=refund_amt,
             new_svc=svc_amt,
             why=BalanceXferToCauseRefundForUnmatchedLimitBuying(
                 trd_id=params.trd_id, ord_id=0))
    ])

    assert refund_amt == balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr)

    # 판매 수익금.
    earning_amt = price * qty

    assert svc_amt == balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr)

    assert earning_amt == balance_service.get(
        BalanceType.EARNING, cust_id=seller, curr=params.curr)

    event_writer_mock.on_balance_cvt_xfer_to.assert_has_calls([
        call(from_balance_type=BalanceType.BALANCE,
             to_balance_type=BalanceType.EARNING,
             cust_id=seller, curr=params.curr,
             amt=earning_amt, new_amt=earning_amt,
             new_svc=ANY,
             why=BalanceCvtXferToCauseEarningPrep(trd_id=trd_id))
    ])

    # 완료.
    assert trd.state == TradingState.COMPLETED

    event_writer_mock.on_trading_finalized.assert_has_calls([
        call(trd_id=trd_id)
    ])


def test_buying_auction_finalize_trading__01(
        started_buying_auction
):
    '''같은 가격의 2개 bid, 첫번째는 fulfilled, 두번째는 partially.

    부분매칭된 경우를 어떻게 처리하는지.'''
    trading_service = started_buying_auction.trading_service
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service
    event_writer_mock = started_buying_auction.event_writer_mock

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id
    trd = trading_service.tradings[trd_id]

    # 판매자, 판매자 잔고액.
    seller_a = str(int(params.cust_id) + 1)
    seller_b = str(int(seller_a) + 1)

    seller_qty_a = 23
    seller_qty_b = 3
    seller_sec_deposit_amt_a = 123
    seller_sec_deposit_amt_b = 789

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller_a,
        curr=params.curr,
        amt=seller_sec_deposit_amt_a)

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller_b,
        curr=params.curr,
        amt=seller_sec_deposit_amt_b)

    price = params.price

    # be fulfilled
    sell_id_a = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller_a,
        price=price,
        qty=seller_qty_a,
        security_deposit_amt=seller_sec_deposit_amt_a,
        option=OrderOption.NONE
    )

    # be partially filled
    sell_id_b = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller_b,
        price=price,
        qty=seller_qty_b,
        security_deposit_amt=seller_sec_deposit_amt_b,
        option=OrderOption.NONE
    )

    # BEFORE: balances
    assert 0 == balance_service.get(
        BalanceType.BALANCE, cust_id=seller_a, curr=params.curr)

    assert 0 == balance_service.get(
        BalanceType.BALANCE, cust_id=seller_b, curr=params.curr)

    assert 0 == balance_service.get(
        BalanceType.EARNING, cust_id=seller_a, curr=params.curr)

    assert 0 == balance_service.get(
        BalanceType.EARNING, cust_id=seller_b, curr=params.curr)

    assert 0 == balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr)

    assert 0 == balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr)

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        (params.price * params.qty) + params.security_deposit_amt + \
        seller_sec_deposit_amt_a + seller_sec_deposit_amt_b

    #
    sell_a = trd.orders[sell_id_a]
    sell_b = trd.orders[sell_id_b]

    #
    trading_service.finalize_trading(trd_id)

    #
    assert sell_a.fulfilled
    assert not sell_b.cancelled
    assert not sell_b.fulfilled

    # 완료 이벤트
    assert trd.state == TradingState.COMPLETED

    event_writer_mock.on_trading_finalized.assert_has_calls([
        call(trd_id=trd_id)
    ])

    # matches
    match_a = trd.matches[0]
    assert match_a.qty == seller_qty_a
    assert match_a.price == params.price
    assert match_a.making_taking_order_pair[0] == sell_id_a

    match_b = trd.matches[1]
    assert match_b.qty == (params.qty - seller_qty_a)
    assert match_b.price == params.price
    assert match_b.making_taking_order_pair[0] == sell_id_b

    # seller_a, seller_b에게 구매한 아이템. (= [23, 2])
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) \
        == (seller_qty_a + seller_qty_b) - params.qty

    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) \
        == params.qty

    assert item_count_service.get(cust_id=seller_a, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=seller_b, trd_id=trd_id) == 0

    event_writer_mock.on_item_count_xfer_from.assert_has_calls([
        call(cust_id=seller_a, trd_id=trd_id, qty=23, new_qty=0, new_svc=23,
             why=ItemCountXferFromCauseSelling(ord_id=ANY)),
        call(cust_id=seller_b, trd_id=trd_id, qty=3, new_qty=0, new_svc=26,
             why=ItemCountXferFromCauseSelling(ord_id=ANY))
    ])

    event_writer_mock.on_item_count_xfer_to.assert_has_calls([
        call(cust_id=params.cust_id, trd_id=trd_id,
             qty=23, new_qty=23, new_svc=3,
             why=ItemCountXferToCauseBuying(match_id=ANY)),
        call(cust_id=params.cust_id, trd_id=trd_id,
             qty=2, new_qty=25, new_svc=1,
             why=ItemCountXferToCauseBuying(match_id=ANY))
    ])

    # 판매자 수익금.
    earning_a = match_a.qty * match_a.price
    earning_b = match_b.qty * match_b.price
    sec_deposit_amts = \
        params.security_deposit_amt + seller_sec_deposit_amt_a + seller_sec_deposit_amt_b

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        sec_deposit_amts

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_a, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_a, curr=params.curr) == \
        earning_a

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_b, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_b, curr=params.curr) == \
        earning_b

    event_writer_mock.on_balance_cvt_xfer_to.assert_has_calls([
        call(from_balance_type=BalanceType.BALANCE,
             to_balance_type=BalanceType.EARNING,
             cust_id=seller_a, curr=params.curr,
             amt=earning_a, new_amt=earning_a,
             new_svc=earning_b + sec_deposit_amts,
             why=BalanceCvtXferToCauseEarningPrep(trd_id=trd_id)),
        call(from_balance_type=BalanceType.BALANCE,
             to_balance_type=BalanceType.EARNING,
             cust_id=seller_b, curr=params.curr,
             amt=earning_b, new_amt=earning_b,
             new_svc=sec_deposit_amts,
             why=BalanceCvtXferToCauseEarningPrep(trd_id=trd_id))
    ])

    # buyer 에게 환불금: 없음 -- fulfilled
    event_writer_mock.on_balance_xfer_to.assert_not_called()


def test_buying_auction_finalize_trading__02(
        started_buying_auction
):
    '''같은 가격의 2개 ask, 첫번째만 fulfilled, 두번째는 모두 cancel.

    전체 매칭 안된 경우를 어떻게 처리하는지.'''
    trading_service = started_buying_auction.trading_service
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service
    event_writer_mock = started_buying_auction.event_writer_mock

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id
    trd = trading_service.tradings[trd_id]

    # seller, seller 잔고액.
    seller_a = str(int(params.cust_id) + 1)
    seller_b = str(int(seller_a) + 1)

    sell_qty_a = 25
    sell_qty_b = 10
    seller_sec_deposit_amt_a = 123
    seller_sec_deposit_amt_b = 789

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller_a,
        curr=params.curr,
        amt=seller_sec_deposit_amt_a)

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller_b,
        curr=params.curr,
        amt=seller_sec_deposit_amt_b)

    price = params.price

    # be fulfilled
    sell_id_a = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller_a,
        price=price,
        qty=sell_qty_a,
        security_deposit_amt=seller_sec_deposit_amt_a,
        option=OrderOption.NONE
    )

    # never be filled
    sell_id_b = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller_b,
        price=price,
        qty=sell_qty_b,
        security_deposit_amt=seller_sec_deposit_amt_b,
        option=OrderOption.NONE
    )

    #
    sell_a = trd.orders[sell_id_a]
    sell_b = trd.orders[sell_id_b]

    #
    trading_service.finalize_trading(trd_id)

    #
    assert sell_a.fulfilled
    assert not sell_b.cancelled
    assert not sell_b.fulfilled

    # 완료 이벤트
    event_writer_mock.on_trading_finalized.assert_has_calls([call(trd_id=trd_id)])

    # 구매한 아이템. (= [25, 0])
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == \
        sell_qty_b  # 잔여

    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == \
        sell_qty_a

    assert item_count_service.get(cust_id=seller_a, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=seller_b, trd_id=trd_id) == 0

    # 판매자 수익금.
    earning_a = (sell_qty_a * price)
    sec_deposit_amts = params.security_deposit_amt + seller_sec_deposit_amt_a + seller_sec_deposit_amt_b

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        sec_deposit_amts  # 모두 구매 성공했으므로 잔여금 없음.

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_a, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_a, curr=params.curr) == earning_a

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_b, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_b, curr=params.curr) == 0

    event_writer_mock.on_balance_xfer_from.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=seller_a, curr=params.curr,
             amt=seller_sec_deposit_amt_a, new_amt=0,
             new_svc=params.security_deposit_amt + (params.price * params.qty) + seller_sec_deposit_amt_a,
             why=BalanceXferFromCauseSecurityDeposit(trd_id=trd_id)),
        call(balance_type=BalanceType.BALANCE,
             cust_id=seller_b, curr=params.curr,
             amt=seller_sec_deposit_amt_b, new_amt=0,
             new_svc=params.security_deposit_amt + (params.price * params.qty) + seller_sec_deposit_amt_a + seller_sec_deposit_amt_b,
             why=BalanceXferFromCauseSecurityDeposit(trd_id=trd_id))
    ])

    event_writer_mock.on_balance_xfer_to.assert_not_called()

    event_writer_mock.on_balance_cvt_xfer_to.assert_has_calls([
        call(from_balance_type=BalanceType.BALANCE,
             to_balance_type=BalanceType.EARNING,
             cust_id=seller_a, curr=params.curr,
             amt=earning_a, new_amt=earning_a, new_svc=sec_deposit_amts,
             why=BalanceCvtXferToCauseEarningPrep(trd_id=trd_id))
    ])


def test_buying_auction_finalize_trading__03(
        started_buying_auction
):
    '''싼 selling부터 매칭하는지.

    그 다음으로 싼 asking은 전혀 매칭 기회가 없을 때.'''
    trading_service = started_buying_auction.trading_service
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service
    event_writer_mock = started_buying_auction.event_writer_mock

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id
    trd = trading_service.tradings[trd_id]

    # sellers, sellers 잔고액.
    seller_a = str(int(params.cust_id) + 1)
    seller_b = str(int(seller_a) + 1)

    sell_qty_a = 25  # 둘 중 하나만 매칭됨.
    sell_qty_b = 25

    sell_price_a = params.price - 1
    sell_price_b = params.price - 2  # 두번째 bidding이지만 가격이 더 낮아서.

    sell_sec_deposit_amt_a = 123
    sell_sec_deposit_amt_b = 789

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

    #
    sell_id_a = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller_a,
        price=sell_price_a,
        qty=sell_qty_a,
        security_deposit_amt=sell_sec_deposit_amt_a,
        option=OrderOption.NONE
    )

    sell_id_b = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller_b,
        price=sell_price_b,
        qty=sell_qty_b,
        security_deposit_amt=sell_sec_deposit_amt_b,
        option=OrderOption.NONE
    )

    #
    sell_a = trd.orders[sell_id_a]
    sell_b = trd.orders[sell_id_b]

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == 0

    #
    trading_service.finalize_trading(trd_id)

    #
    assert not sell_a.fulfilled
    assert not sell_a.cancelled
    assert sell_b.fulfilled

    # 구매한 아이템. (= [0, 25])
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == \
        sell_qty_a  # 잔여

    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == \
        sell_qty_b  # 구매

    assert item_count_service.get(cust_id=seller_a, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=seller_b, trd_id=trd_id) == 0

    # 잔고
    buyer_refund = params.qty * (params.price - sell_b.price)
    buyer_spent = params.qty * sell_b.price
    sec_deposit_amts = params.security_deposit_amt + sell_sec_deposit_amt_a + sell_sec_deposit_amt_b

    event_writer_mock.on_balance_xfer_from.assert_has_calls([
        call(balance_type=BalanceType.BALANCE, cust_id=seller_a,
             curr=params.curr,
             amt=sell_sec_deposit_amt_a, new_amt=0, new_svc=ANY,
             why=BalanceXferFromCauseSecurityDeposit(trd_id=trd_id)),
        call(balance_type=BalanceType.BALANCE, cust_id=seller_b,
             curr=params.curr,
             amt=sell_sec_deposit_amt_b, new_amt=0, new_svc=ANY,
             why=BalanceXferFromCauseSecurityDeposit(trd_id=trd_id))
    ])

    event_writer_mock.on_balance_xfer_to.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=params.cust_id, curr=params.curr,
             amt=buyer_refund, new_amt=buyer_refund,
             new_svc=ANY,
             why=BalanceXferToCauseRefundForUnmatchedLimitBuying(
                 trd_id=trd_id, ord_id=ANY))
    ])

    event_writer_mock.on_balance_cvt_xfer_to.assert_has_calls([
        call(from_balance_type=BalanceType.BALANCE,
             to_balance_type=BalanceType.EARNING,
             cust_id=seller_b, curr=params.curr,
             amt=buyer_spent, new_amt=buyer_spent,
             new_svc=ANY,
             why=BalanceCvtXferToCauseEarningPrep(trd_id=trd_id))
    ])

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        sec_deposit_amts
    assert balance_service.get(
        BalanceType.EARNING, cust_id=SERVICE_CUSTOMER, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == buyer_refund
    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_a, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_a, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_b, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_b, curr=params.curr) == buyer_spent


def test_buying_auction_finalize_trading__04(
        started_buying_auction
):
    '''싼 selling부터 매칭하는지.

    그 다음으로 싼 asking은 부분 매칭.'''
    trading_service = started_buying_auction.trading_service
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service
    event_writer_mock = started_buying_auction.event_writer_mock

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id
    trd = trading_service.tradings[trd_id]

    # sellers, 잔고액.
    seller_a = str(int(params.cust_id) + 1)
    seller_b = str(int(seller_a) + 1)

    sell_qty_a = 20
    sell_qty_b = 20

    sell_price_a = params.price - 1
    sell_price_b = params.price - 2  # 두번째 asking이지만 가격이 낮아서 먼저.

    sell_sec_deposit_amt_a = 123
    sell_sec_deposit_amt_b = 789

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

    # 매칭=5
    sell_id_a = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller_a,
        price=sell_price_a,
        qty=sell_qty_a,
        security_deposit_amt=sell_sec_deposit_amt_a,
        option=OrderOption.NONE
    )

    # 매칭=20
    sell_id_b = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller_b,
        price=sell_price_b,
        qty=sell_qty_b,
        security_deposit_amt=sell_sec_deposit_amt_b,
        option=OrderOption.NONE
    )

    #
    sell_a = trd.orders[sell_id_a]
    sell_b = trd.orders[sell_id_b]

    #
    trading_service.finalize_trading(trd_id)

    #
    assert not sell_a.fulfilled
    assert not sell_a.cancelled
    assert sell_b.fulfilled

    # a, b에게 구매한 아이템. (= [5, 20])
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == \
        (sell_qty_a + sell_qty_b) - params.qty

    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == \
        params.qty  # fulfilled

    assert item_count_service.get(cust_id=seller_a, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=seller_b, trd_id=trd_id) == 0

    # 수익, 환불
    sec_deposit_amts = params.security_deposit_amt + \
        sell_sec_deposit_amt_a + sell_sec_deposit_amt_b

    earning_a = 5 * sell_price_a
    earning_b = sell_qty_b * sell_price_b

    buyer_spent = earning_a + earning_b
    buyer_refund = (params.price * params.qty) - buyer_spent

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        sec_deposit_amts

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == \
        buyer_refund
    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_a, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_a, curr=params.curr) == \
        earning_a

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_b, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_b, curr=params.curr) == \
        earning_b

    event_writer_mock.on_balance_xfer_from.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=seller_a, curr=params.curr,
             amt=sell_sec_deposit_amt_a, new_amt=0, new_svc=ANY,
             why=BalanceXferFromCauseSecurityDeposit(trd_id=trd_id)),
        call(balance_type=BalanceType.BALANCE,
             cust_id=seller_b, curr=params.curr,
             amt=sell_sec_deposit_amt_b, new_amt=0, new_svc=ANY,
             why=BalanceXferFromCauseSecurityDeposit(trd_id=trd_id))
    ])

    event_writer_mock.on_balance_xfer_to.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=params.cust_id, curr=params.curr,
             amt=buyer_refund, new_amt=buyer_refund, new_svc=ANY,
             why=BalanceXferToCauseRefundForUnmatchedLimitBuying(
                 trd_id=trd_id, ord_id=ANY))
    ])

    event_writer_mock.on_balance_cvt_xfer_to.assert_has_calls([
        call(from_balance_type=BalanceType.BALANCE,
             to_balance_type=BalanceType.EARNING,
             cust_id=seller_b, curr=params.curr,
             amt=earning_b, new_amt=earning_b,
             new_svc=ANY,
             why=BalanceCvtXferToCauseEarningPrep(trd_id=trd_id)),
        call(from_balance_type=BalanceType.BALANCE,
             to_balance_type=BalanceType.EARNING,
             cust_id=seller_a, curr=params.curr,
             amt=earning_a, new_amt=earning_a,
             new_svc=ANY,
             why=BalanceCvtXferToCauseEarningPrep(trd_id=trd_id))
    ])


def test_buying_auction_finalize_trading__fok_ok(
        started_buying_auction
):
    '''FoK 매칭 성공.'''
    trading_service = started_buying_auction.trading_service
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service
    event_writer_mock = started_buying_auction.event_writer_mock

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id
    trd = trading_service.tradings[trd_id]

    # sellers, 잔고액.
    seller_a = str(int(params.cust_id) + 1)
    seller_b = str(int(seller_a) + 1)

    sell_qty_a = 20
    sell_qty_b = 20

    sell_price_a = params.price - 1
    sell_price_b = params.price - 2  # 두번째 asking이지만 가격이 낮아서.

    sell_sec_deposit_amt_a = 123
    sell_sec_deposit_amt_b = 789

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

    # partially filled
    sell_id_a = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller_a,
        price=sell_price_a,
        qty=sell_qty_a,
        security_deposit_amt=sell_sec_deposit_amt_a,
        option=OrderOption.NONE
    )

    # fulfilled
    sell_id_b = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller_b,
        price=sell_price_b,
        qty=sell_qty_b,
        security_deposit_amt=sell_sec_deposit_amt_b,
        option=OrderOption.FILL_OR_KILL
    )

    #
    sell_a = trd.orders[sell_id_a]
    sell_b = trd.orders[sell_id_b]

    #
    trading_service.finalize_trading(trd_id)

    #
    assert not sell_a.fulfilled
    assert not sell_b.cancelled
    assert sell_b.fulfilled

    # a, b에게 구매한 아이템. (= [5, 20(FoK)])
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == 15

    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == 25

    assert item_count_service.get(cust_id=seller_a, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=seller_b, trd_id=trd_id) == 0

    event_writer_mock.on_item_count_xfer_to.assert_has_calls([
        call(cust_id=params.cust_id, trd_id=trd_id,
             qty=20, new_qty=20, new_svc=20,
             why=ItemCountXferToCauseBuying(match_id=ANY)),
        call(cust_id=params.cust_id, trd_id=trd_id,
             qty=5, new_qty=25, new_svc=15,
             why=ItemCountXferToCauseBuying(match_id=ANY))
    ])

    # 수익, 환불
    sec_deposit_amts = params.security_deposit_amt + \
        sell_sec_deposit_amt_a + sell_sec_deposit_amt_b

    earning_a = 5 * sell_price_a
    earning_b = sell_qty_b * sell_price_b

    buyer_spent = earning_a + earning_b
    buyer_refund = (params.price * params.qty) - buyer_spent

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        sec_deposit_amts

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == \
        buyer_refund
    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_a, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_a, curr=params.curr) == \
        earning_a

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_b, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_b, curr=params.curr) == \
        earning_b

    event_writer_mock.on_balance_xfer_from.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=seller_a, curr=params.curr,
             amt=sell_sec_deposit_amt_a, new_amt=0, new_svc=ANY,
             why=BalanceXferFromCauseSecurityDeposit(trd_id=trd_id)),
        call(balance_type=BalanceType.BALANCE,
             cust_id=seller_b, curr=params.curr,
             amt=sell_sec_deposit_amt_b, new_amt=0, new_svc=ANY,
             why=BalanceXferFromCauseSecurityDeposit(trd_id=trd_id))
    ])

    event_writer_mock.on_balance_xfer_to.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=params.cust_id, curr=params.curr,
             amt=buyer_refund, new_amt=buyer_refund, new_svc=ANY,
             why=BalanceXferToCauseRefundForUnmatchedLimitBuying(
                 trd_id=trd_id, ord_id=ANY))
    ])

    event_writer_mock.on_balance_cvt_xfer_to.assert_has_calls([
        call(from_balance_type=BalanceType.BALANCE,
             to_balance_type=BalanceType.EARNING,
             cust_id=seller_b, curr=params.curr,
             amt=earning_b, new_amt=earning_b,
             new_svc=ANY,
             why=BalanceCvtXferToCauseEarningPrep(trd_id=trd_id)),
        call(from_balance_type=BalanceType.BALANCE,
             to_balance_type=BalanceType.EARNING,
             cust_id=seller_a, curr=params.curr,
             amt=earning_a, new_amt=earning_a,
             new_svc=ANY,
             why=BalanceCvtXferToCauseEarningPrep(trd_id=trd_id))
    ])


def test_buying_auction_finalize_trading__fok_passing(
        started_buying_auction
):
    '''FoK 매칭 안될 때 건너뛰기.'''
    trading_service = started_buying_auction.trading_service
    balance_service = started_buying_auction.balance_service
    item_count_service = started_buying_auction.item_count_service
    event_writer_mock = started_buying_auction.event_writer_mock

    params = started_buying_auction.start_new_buying_auction_params
    trd_id = started_buying_auction.trd_id
    trd = trading_service.tradings[trd_id]

    # sellers, 잔고액.
    seller_a = str(int(params.cust_id) + 1)
    seller_b = str(int(seller_a) + 1)
    seller_c = str(int(seller_b) + 1)

    sell_qty_a = 20
    sell_qty_b = 20
    sell_qty_c = 20

    sell_price_a = params.price - 0
    sell_price_b = params.price - 1
    sell_price_c = params.price - 2

    sell_sec_deposit_amt_a = 123
    sell_sec_deposit_amt_b = 456
    sell_sec_deposit_amt_c = 789

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

    balance_service.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=seller_c,
        curr=params.curr,
        amt=sell_sec_deposit_amt_c)

    #
    sell_id_a = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller_a,
        price=sell_price_a,
        qty=sell_qty_a,
        security_deposit_amt=sell_sec_deposit_amt_a,
        option=OrderOption.NONE
    )

    sell_id_b = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller_b,
        price=sell_price_b,
        qty=sell_qty_b,
        security_deposit_amt=sell_sec_deposit_amt_b,
        option=OrderOption.FILL_OR_KILL
    )

    sell_id_c = trading_service.ask_selling(
        trd_id=trd_id,
        cust_id=seller_c,
        price=sell_price_c,
        qty=sell_qty_c,
        security_deposit_amt=sell_sec_deposit_amt_c,
        option=OrderOption.NONE
    )

    #
    sell_a = trd.orders[sell_id_a]
    sell_b = trd.orders[sell_id_b]
    sell_c = trd.orders[sell_id_c]

    #
    trading_service.finalize_trading(trd_id)

    #
    assert not sell_a.fulfilled
    assert not sell_b.fulfilled
    assert sell_c.fulfilled

    # a,b,c에게 구매한 아이템. (= [5, 0, 20])
    assert item_count_service.get(cust_id=SERVICE_CUSTOMER, trd_id=trd_id) == \
        60 - 25

    assert item_count_service.get(cust_id=params.cust_id, trd_id=trd_id) == \
        params.qty

    assert item_count_service.get(cust_id=seller_a, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=seller_b, trd_id=trd_id) == 0
    assert item_count_service.get(cust_id=seller_c, trd_id=trd_id) == 0

    # 환불, 수익
    #
    # sell_b은 중간 가격(+9)이어서, sell_c 가격(+8)이 20-qty 먼저 매칭되고,
    # 잔여 5-qty만으로는, 요청한 20-qty 매칭을 할 수 없으니, FoK이라 pass되고,
    # 그 다음 가격인 sell_a(+10)이 매칭되었음.
    sec_deposit_amts = params.security_deposit_amt + \
        sell_sec_deposit_amt_a + sell_sec_deposit_amt_b + sell_sec_deposit_amt_c

    earning_a = 5 * sell_price_a
    earning_b = 0
    earning_c = 20 * sell_price_c

    buyer_spent = earning_a + earning_b + earning_c
    buyer_refund = (params.price * params.qty) - buyer_spent

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=SERVICE_CUSTOMER, curr=params.curr) == \
        sec_deposit_amts

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=params.cust_id, curr=params.curr) == \
        buyer_refund
    assert balance_service.get(
        BalanceType.EARNING, cust_id=params.cust_id, curr=params.curr) == 0

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_a, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_a, curr=params.curr) == \
        earning_a

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_b, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_b, curr=params.curr) == \
        earning_b

    assert balance_service.get(
        BalanceType.BALANCE, cust_id=seller_c, curr=params.curr) == 0
    assert balance_service.get(
        BalanceType.EARNING, cust_id=seller_c, curr=params.curr) == \
        earning_c

    event_writer_mock.on_balance_xfer_to.assert_has_calls([
        call(balance_type=BalanceType.BALANCE,
             cust_id=params.cust_id, curr=params.curr,
             amt=buyer_refund, new_amt=buyer_refund, new_svc=ANY,
             why=BalanceXferToCauseRefundForUnmatchedLimitBuying(
                 trd_id=trd_id, ord_id=ANY))
    ])

    event_writer_mock.on_balance_cvt_xfer_to.assert_has_calls([
        call(from_balance_type=BalanceType.BALANCE,
             to_balance_type=BalanceType.EARNING,
             cust_id=seller_c, curr=params.curr,
             amt=earning_c, new_amt=19960, new_svc=ANY,
             why=BalanceCvtXferToCauseEarningPrep(trd_id=trd_id)),
        call(from_balance_type=BalanceType.BALANCE,
             to_balance_type=BalanceType.EARNING,
             cust_id=seller_a, curr=params.curr,
             amt=earning_a, new_amt=earning_a, new_svc=ANY,
             why=BalanceCvtXferToCauseEarningPrep(trd_id=trd_id))
    ])
