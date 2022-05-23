from datetime import datetime
from pytest import raises  # type:ignore
from oev8.typedefs import SeqType, BalanceType, OrderOption, OrderSide
from oev8.typedefs import CustomerId, CurrencyType, CurrencyAmt
from oev8.typedefs import TradingId, ItemQty, TradingType, AuctionSide
from oev8.funcs import to_timestamp_secs
from oev8.svcs.event_writer import EventWriter
from oev8.svcs.seq_num import SeqNumService
from oev8.svcs.balance import BalanceService
from oev8.svcs.item_count import ItemCountService
from oev8.svcs.trading import TradingService
from oev8.excs import TradingIsNotFound


def do_some_mess(
        seq_num_svc: SeqNumService,
        balance_svc: BalanceService,
        item_count_svc: ItemCountService,
        trading_svc: TradingService):
    curr = CurrencyType(18)

    cust_a = CustomerId(11)
    cust_b = CustomerId(22)
    cust_c = CustomerId(33)

    trd_a = TradingId('101')
    trd_b = TradingId('202')
    trd_c = TradingId('303')
    trd_d = TradingId('404')

    balance_svc.deposit(
        BalanceType.BALANCE,
        cust_a, curr, CurrencyAmt(1234567))

    balance_svc.deposit(
        BalanceType.BALANCE,
        cust_b, curr, CurrencyAmt(1234567 * 373))

    balance_svc.deposit(
        BalanceType.BALANCE,
        cust_c, curr, CurrencyAmt(1234567 * 36713))

    trading_svc.start_new_trading_as_seller(
        cust_a, trd_a, curr, CurrencyAmt(100), ItemQty(10),
        CurrencyAmt(12),
        to_timestamp_secs(datetime(3000, 12, 25)))

    trading_svc.start_new_trading_as_seller(
        cust_a, trd_b, curr, CurrencyAmt(100), ItemQty(10),
        CurrencyAmt(12),
        to_timestamp_secs(datetime(3000, 12, 25)))

    trading_svc.start_new_trading_as_seller(
        cust_c, trd_c, curr, CurrencyAmt(100), ItemQty(10),
        CurrencyAmt(12),
        to_timestamp_secs(datetime(3000, 12, 25)))

    trading_svc.join_as_item_provider(
        cust_b, trd_b,
        security_deposit_amt=CurrencyAmt(100),
        qty=ItemQty(100))

    trading_svc.order_limit_buy(
        trd_a, cust_b, CurrencyAmt(12), ItemQty(10))

    trading_svc.order_market_sell(
        trd_b, cust_b, ItemQty(12))

    trading_svc.order_market_buy(
        trd_a, cust_c, ItemQty(13))

    trading_svc.cancel_trading(trd_a)
    trading_svc.evict_trading(trd_a)

    trading_svc.start_new_trading_as_seller(
        cust_c, trd_d, curr, CurrencyAmt(1),
        ItemQty(1), CurrencyAmt(100),
        to_timestamp_secs(datetime(4000, 12, 25)))

    seq_ord_a = trading_svc.order_limit_buy(
        trd_d, cust_c, CurrencyAmt(18), ItemQty(1))

    seq_ord_b = trading_svc.order_limit_buy(
        trd_d, cust_c, CurrencyAmt(18), ItemQty(2))

    seq_ord_c = trading_svc.order_limit_buy(
        trd_d, cust_c, CurrencyAmt(18), ItemQty(3))

    # 경매거래 a
    auction_trd_id_a = str(1_000)
    auction_curr_a = 1_000_1
    auction_seller_a = str(1_000_1)
    auction_buyer_a = str(1_000_2)
    auction_buyer_b = str(1_000_3)
    auction_buyer_c = str(1_000_4)

    balance_svc.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=auction_seller_a,
        curr=auction_curr_a,
        amt=1_000)

    trading_svc.start_new_selling_auction(
        trd_id=auction_trd_id_a,
        curr=auction_curr_a,
        cust_id=auction_seller_a,
        price=1,
        qty=10,
        security_deposit_amt=1_000,
        until_utc_timestamp_secs=to_timestamp_secs(datetime(3000, 12, 25))
    )

    balance_svc.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=auction_buyer_a,
        curr=auction_curr_a,
        amt=1_000_2)

    balance_svc.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=auction_buyer_b,
        curr=auction_curr_a,
        amt=1_000_3)

    balance_svc.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=auction_buyer_c,
        curr=auction_curr_a,
        amt=1_000_4)

    buying_bid_id_a = trading_svc.bid_buying(
        trd_id=auction_trd_id_a,
        cust_id=auction_buyer_a,
        price=1,
        qty=10,
        option=OrderOption.NONE
    )

    buying_bid_id_b = trading_svc.bid_buying(
        trd_id=auction_trd_id_a,
        cust_id=auction_buyer_b,
        price=10,
        qty=100,
        option=OrderOption.NONE
    )

    buying_bid_id_c = trading_svc.bid_buying(
        trd_id=auction_trd_id_a,
        cust_id=auction_buyer_c,
        price=10,
        qty=200,
        option=OrderOption.NONE
    )

    # 경매거래 b
    auction_trd_id_b = str(2_000)
    auction_curr_b = 2_000_1
    auction_seller_b = str(2_000_1)
    auction_buyer_d = str(2_000_2)
    auction_buyer_e = str(2_000_3)

    balance_svc.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=auction_seller_b,
        curr=auction_curr_b,
        amt=2_000)

    trading_svc.start_new_selling_auction(
        trd_id=auction_trd_id_b,
        curr=auction_curr_b,
        cust_id=auction_seller_b,
        price=123,
        qty=999,
        security_deposit_amt=987,
        until_utc_timestamp_secs=to_timestamp_secs(datetime(3000, 10, 13))
    )

    balance_svc.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=auction_buyer_d,
        curr=auction_curr_b,
        amt=2_000_000_000_2)

    balance_svc.deposit(
        balance_type=BalanceType.BALANCE,
        cust_id=auction_buyer_e,
        curr=auction_curr_b,
        amt=2_000_000_000_3)

    buying_bid_id_d = trading_svc.bid_buying(
        trd_id=auction_trd_id_b,
        cust_id=auction_buyer_d,
        price=123,
        qty=9,
        option=OrderOption.NONE
    )

    buying_bid_id_e = trading_svc.bid_buying(
        trd_id=auction_trd_id_b,
        cust_id=auction_buyer_e,
        price=125,
        qty=8,
        option=OrderOption.FILL_OR_KILL
    )

    trading_svc.finalize_trading(auction_trd_id_b)

    #
    return {
        'curr': curr,
        'trd_a': trd_a,
        'trd_b': trd_b,
        'trd_c': trd_c,
        'trd_d': trd_d,
        'cust_a': cust_a,
        'cust_b': cust_b,
        'cust_c': cust_c,
        'seq_ord_a': seq_ord_a,
        'seq_ord_b': seq_ord_b,
        'seq_ord_c': seq_ord_c,
        'auction_trd_id_a': auction_trd_id_a,
        'auction_trd_id_b': auction_trd_id_b,
    }


def test_get_trading_info__auctions(trading_service):
    params = do_some_mess(trading_service.seq_num_service,
                          trading_service.balance_service,
                          trading_service.item_count_service,
                          trading_service)

    trd_id = params['trd_b']
    trd = trading_service.get_trading(trd_id)
    assert trd.trading_type == TradingType.EXCHANGE

    trd_id = params['auction_trd_id_a']
    trd = trading_service.get_trading(trd_id)
    assert trd.trading_type == TradingType.AUCTION


def test_get_auction_info(trading_service):
    params = do_some_mess(trading_service.seq_num_service,
                          trading_service.balance_service,
                          trading_service.item_count_service,
                          trading_service)

    trd_id = params['trd_b']
    with raises(TradingIsNotFound):
        trading_service.get_auction_info(trd_id)

    trd_id = params['auction_trd_id_a']
    auction = trading_service.get_auction_info(trd_id)
    assert auction.auction_side == AuctionSide.SELLING


def test_list_price_and_count_price_auction(trading_service):
    params = do_some_mess(trading_service.seq_num_service,
                          trading_service.balance_service,
                          trading_service.item_count_service,
                          trading_service)

    trd_id = params['auction_trd_id_a']
    prices = trading_service.list_price(trd_id,
                                        OrderSide.BUY,
                                        0, 10)
    assert [1, 10] == list(prices)

    price_count = trading_service.count_price(trd_id, OrderSide.BUY)
    assert 2 == price_count

    trd_id = params['auction_trd_id_b']
    prices = trading_service.list_price(trd_id,
                                        OrderSide.BUY,
                                        0, 10)
    assert [123, 125] == list(prices)

    price_count = trading_service.count_price(trd_id, OrderSide.BUY)
    assert 2 == price_count


def test_list_and_count_order_auction(trading_service):
    params = do_some_mess(trading_service.seq_num_service,
                          trading_service.balance_service,
                          trading_service.item_count_service,
                          trading_service)

    trd_id = params['auction_trd_id_a']
    orders = trading_service.list_order_id_by_price(
        trd_id, OrderSide.BUY, 10,  # price
        0, 10)
    assert [(12, 100,), (13, 200,)] == list(orders)

    cnt = trading_service.count_order_id_by_price(
        trd_id, OrderSide.BUY, 10)
    assert 2 == cnt
