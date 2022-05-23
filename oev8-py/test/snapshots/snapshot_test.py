'snapshotting/recovering tests.'
from datetime import datetime
import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock
from pytest import fixture
from pytest import mark
from sortedcontainers import SortedDict  # type:ignore
from oev8.typedefs import SeqType, BalanceType, OrderOption
from oev8.typedefs import CustomerId, CurrencyType, CurrencyAmt
from oev8.typedefs import TradingId, ItemQty
from oev8.funcs import to_timestamp_secs
from oev8.svcs.event_writer import EventWriter
from oev8.svcs.seq_num import SeqNumService
from oev8.svcs.balance import BalanceService
from oev8.svcs.item_count import ItemCountService
from oev8.svcs.trading import TradingService
from oev8.svcs.clockwork.trading import TradingClockworkService
from oev8.svcs.snapshot.sqlite3 import SqliteThreeSnapshotService, \
    SqliteThreeSnapshotLoadingService
from test.testsup import assert_orderbook


def do_nothing(*_):
    'eargerly does nothing'
    return None


def do_some_mess(
        seq_num_svc: SeqNumService,
        balance_svc: BalanceService,
        item_count_svc: ItemCountService,
        trading_svc: TradingService):
    curr = CurrencyType(18)

    cust_a = CustomerId('11')
    cust_b = CustomerId('22')
    cust_c = CustomerId('33')

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
    }


@fixture
def seq_num_svc():
    return SeqNumService()


@fixture
def balance_svc():
    return BalanceService()


@fixture
def item_count_svc():
    return ItemCountService()


@fixture
def trading_clockwork_svc():
    return TradingClockworkService(
        do_complete_trading=do_nothing,
        do_evict_trading=do_nothing)


@fixture
def event_writer():
    return Mock(EventWriter)


@fixture
def trading_svc(seq_num_svc, item_count_svc, balance_svc,
                event_writer, trading_clockwork_svc):
    return TradingService(
        seq_num_service=seq_num_svc,
        item_count_service=item_count_svc,
        balance_service=balance_svc,
        event_writer=event_writer,
        trading_clockwork_service=trading_clockwork_svc)


SAVER_LOADER_CLASSES = (
    (SqliteThreeSnapshotService, SqliteThreeSnapshotLoadingService,),
)


@mark.parametrize("saver_cls,loader_cls", SAVER_LOADER_CLASSES)
def test_saving_and_loading_empty(
        saver_cls, loader_cls,
        tmpdir, seq_num_svc, item_count_svc, balance_svc,
        trading_svc, trading_clockwork_svc,
        null_logging_stopwatch
):
    saving_svc = saver_cls(
        tmpdir,
        seq_num_service=seq_num_svc,
        balance_service=balance_svc,
        item_count_service=item_count_svc,
        trading_service=trading_svc,
        trading_clockwork_service=trading_clockwork_svc,
        logging_stopwatch=null_logging_stopwatch
    )

    loading_svc = loader_cls(
        seq_num_service=seq_num_svc,
        balance_service=balance_svc,
        item_count_service=item_count_svc,
        trading_service=trading_svc,
        trading_clockwork_service=trading_clockwork_svc
    )

    # save it as empty
    (snapshot_fn, checksum_fn,) = saving_svc.save()
    print(snapshot_fn, checksum_fn)

    # do some mess
    result_dict = do_some_mess(seq_num_svc,
                               balance_svc,
                               item_count_svc,
                               trading_svc)

    trd_b = result_dict['trd_b']

    # verify: how it have messed
    assert len(balance_svc.balances) > 0
    assert len(trading_svc.tradings) > 0
    assert len(trading_svc.auctions) > 0

    assert len(trading_svc.tradings[trd_b].orders) > 0

    # load it again
    loading_svc.load(snapshot_fn)

    # verify: all the messes are gone
    assert seq_num_svc.cur_val(SeqType.CMD_REQ) == 0
    assert seq_num_svc.cur_val(SeqType.ORDER) == 0
    assert seq_num_svc.cur_val(SeqType.MATCH) == 0

    assert len(balance_svc.balances) == 0
    assert len(balance_svc.earnings) == 0

    assert len(item_count_svc.counts) == 0

    assert len(trading_svc.tradings) == 0
    assert len(trading_svc.auctions) == 0

    assert len(trading_clockwork_svc.sched_to_trd_ids) == 0

    # cleanups
    os.remove(snapshot_fn)
    if checksum_fn is not None and len(checksum_fn) > 0:
        os.remove(checksum_fn)


@mark.parametrize("saver_cls,loader_cls", SAVER_LOADER_CLASSES)
def test_saving_and_loading(
        saver_cls, loader_cls,
        tmpdir, seq_num_svc, item_count_svc, balance_svc,
        trading_svc, trading_clockwork_svc,
        null_logging_stopwatch
):
    saving_svc = saver_cls(
        tmpdir,
        seq_num_service=seq_num_svc,
        balance_service=balance_svc,
        item_count_service=item_count_svc,
        trading_service=trading_svc,
        trading_clockwork_service=trading_clockwork_svc,
        logging_stopwatch=null_logging_stopwatch
    )

    loading_svc = loader_cls(
        seq_num_service=seq_num_svc,
        balance_service=balance_svc,
        item_count_service=item_count_svc,
        trading_service=trading_svc,
        trading_clockwork_service=trading_clockwork_svc
    )

    # do some mess
    result_dict = do_some_mess(seq_num_svc,
                               balance_svc,
                               item_count_svc,
                               trading_svc)

    trd_b = result_dict['trd_b']
    trd_d = result_dict['trd_d']

    # verify: how it have messed
    assert len(balance_svc.balances) > 0
    assert len(trading_svc.tradings) > 0

    assert len(trading_svc.tradings[trd_b].orders) > 0
    assert len(trading_svc.auctions) > 0

    # save it
    (snapshot_fn, checksum_fn,) = saving_svc.save()
    print(snapshot_fn, checksum_fn)

    # store the states
    seq_num_vals = seq_num_svc.vals
    balances = balance_svc.balances
    earnings = balance_svc.earnings
    item_counts = item_count_svc.counts
    tradings = trading_svc.tradings
    auctions = trading_svc.auctions
    trading_clockwork_scheds = trading_clockwork_svc.sched_to_trd_ids

    # reset all
    seq_num_svc.vals = {}
    balance_svc.balances = {}
    balance_svc.earnings = {}
    item_count_svc.counts = {}
    trading_svc.tradings = {}
    trading_svc.auctions = {}
    trading_clockwork_svc.sched_to_trd_ids = SortedDict()

    # verify: all the messes are gone
    assert seq_num_svc.cur_val(SeqType.CMD_REQ) == 0
    assert seq_num_svc.cur_val(SeqType.ORDER) == 0
    assert seq_num_svc.cur_val(SeqType.MATCH) == 0

    assert len(balance_svc.balances) == 0
    assert len(balance_svc.earnings) == 0

    assert len(item_count_svc.counts) == 0

    assert len(trading_svc.tradings) == 0
    assert len(trading_svc.auctions) == 0

    assert len(trading_clockwork_svc.sched_to_trd_ids) == 0

    # load it again
    loading_svc.load(snapshot_fn)

    # compare
    assert seq_num_svc.vals == seq_num_vals
    assert balances == balance_svc.balances
    assert earnings == balance_svc.earnings
    assert item_counts == item_count_svc.counts
    assert tradings == trading_svc.tradings
    assert auctions == trading_svc.auctions and\
        auctions is not trading_svc.auctions
    assert trading_clockwork_svc.sched_to_trd_ids == trading_clockwork_scheds

    # checks
    assert trd_d in trading_svc.tradings

    buy_orderbook = trading_svc.tradings[trd_d].buys[18]

    assert len(buy_orderbook) == 3

    seq_ord_a = result_dict['seq_ord_a']
    seq_ord_b = result_dict['seq_ord_b']
    seq_ord_c = result_dict['seq_ord_c']

    assert [(seq_ord_a, 1,),
            (seq_ord_b, 2,),
            (seq_ord_c, 3,)] == \
            [ord_id__qty for ord_id__qty in buy_orderbook.items()]

    # 적절한 오더북 상태인지?
    # -- 정렬이 제대로 가능한지 (integer-keyed, sorted-dicts)
    for trd_id in trading_svc.tradings.keys():
        trd = trading_svc.tradings[trd_id]
        assert_orderbook(trd.buys)
        assert_orderbook(trd.sells)
        assert_orderbook(trd.auction_bids)

    # logging-stopwatch
    null_logging_stopwatch.__enter__.assert_called()
    null_logging_stopwatch.__exit__.assert_called()

    # cleanups
    os.remove(snapshot_fn)
    if checksum_fn is not None and len(checksum_fn) > 0:
        os.remove(checksum_fn)


def test_find_latest_sqlite3(
        seq_num_svc, item_count_svc, balance_svc,
        trading_svc, trading_clockwork_svc,
        null_logging_stopwatch,
        samples_snapshot_sqlite3
):
    loading_svc = SqliteThreeSnapshotLoadingService(
        seq_num_service=seq_num_svc,
        balance_service=balance_svc,
        item_count_service=item_count_svc,
        trading_service=trading_svc,
        trading_clockwork_service=trading_clockwork_svc
    )

    assert samples_snapshot_sqlite3.is_dir()

    result = loading_svc.find_latest(base_dir=str(samples_snapshot_sqlite3))
    assert result is not None

    result_path = Path(result)
    assert result_path.is_file() and result_path.exists()
    assert result_path.name == '0099.oev8.sqlite3'


def test_find_latest_sqlite3__empty_dir(
        seq_num_svc, item_count_svc, balance_svc,
        trading_svc, trading_clockwork_svc,
        null_logging_stopwatch,
        samples_snapshot_sqlite3_empty
):
    loading_svc = SqliteThreeSnapshotLoadingService(
        seq_num_service=seq_num_svc,
        balance_service=balance_svc,
        item_count_service=item_count_svc,
        trading_service=trading_svc,
        trading_clockwork_service=trading_clockwork_svc
    )

    assert samples_snapshot_sqlite3_empty.is_dir()

    result = loading_svc.find_latest(base_dir=str(samples_snapshot_sqlite3_empty))

    assert result is None


def test_find_latest_sqlite3__falsy_dir(
        seq_num_svc, item_count_svc, balance_svc,
        trading_svc, trading_clockwork_svc,
        null_logging_stopwatch,
        samples_snapshot_sqlite3_falsy
):
    loading_svc = SqliteThreeSnapshotLoadingService(
        seq_num_service=seq_num_svc,
        balance_service=balance_svc,
        item_count_service=item_count_svc,
        trading_service=trading_svc,
        trading_clockwork_service=trading_clockwork_svc
    )

    assert samples_snapshot_sqlite3_falsy.is_dir()

    result = loading_svc.find_latest(base_dir=str(samples_snapshot_sqlite3_falsy))

    assert result is None
