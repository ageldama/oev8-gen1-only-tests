import os
from unittest.mock import Mock, MagicMock, AsyncMock
from os.path import abspath
from pathlib import Path
from glob import glob
import asyncio
import sys
import logging
import logging.config
from collections import namedtuple
from datetime import datetime
from pytest import fixture  # type: ignore
from aiokafka import AIOKafkaProducer  # type:ignore
from oev8.svcs.balance import BalanceService
from oev8.svcs.item_count import ItemCountService
from oev8.svcs.seq_num import SeqNumService
from oev8.svcs.trading import TradingService
from oev8.svcs.clockwork.trading import TradingClockworkService
from oev8.funcs import to_timestamp_secs
from oev8.configs import Config
from test.testsup import make_null_logging_stopwatch


stdout_handler = logging.StreamHandler(sys.stdout)
handlers = [stdout_handler]


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d %(name)s [%(filename)s:%(lineno)d] : %(message)s',
    datefmt='%y/%m/%d_%H:%M:%S',
    handlers=handlers
)

# DEBUG for `kakfka*` is too annoying...
logging.getLogger('kafka').setLevel(logging.WARNING)


@fixture
def src_root():
    return Path(abspath(__file__)).parents[1]


@fixture
def test_root(src_root):
    return src_root / "test"


@fixture
def balance_service():
    return BalanceService()


@fixture
def item_count_service():
    return ItemCountService()


@fixture
def seq_num_service():
    return SeqNumService()


@fixture
def event_writer_mock():
    return Mock()


@fixture
def trading_clockwork_service():
    return Mock(TradingClockworkService)


@fixture
def trading_service(
        seq_num_service,
        item_count_service,
        balance_service,
        event_writer_mock,
        trading_clockwork_service
):
    return TradingService(
        seq_num_service,
        item_count_service,
        balance_service,
        event_writer_mock,
        trading_clockwork_service
    )


@fixture
def test_config_path(test_root):
    return test_root / "test-environ.ini"


@fixture
def test_config(test_config_path):
    cfg = Config()
    cfg.read_file(test_config_path.resolve())
    return cfg


def get_test_config():
    src_root_ = Path(abspath(__file__)).parents[1]
    test_root_ = src_root_ / "test"

    config_path = test_root_ / "test-environ.ini"

    cfg = Config()
    cfg.read_file(config_path.resolve())

    return cfg


StartNewSellingAuctionParams = namedtuple(
    'StartNewSellingAuctionParams',
    ['trd_id', 'curr', 'cust_id', 'price', 'qty',
     'security_deposit_amt', 'until_utc_timestamp_secs'])


@fixture
def start_new_selling_auction_params():
    trd_id = str(123)
    curr = 12
    cust_id = str(12345)
    price = 1_000
    qty = 25
    security_deposit_amt = 20_000
    until_utc_timestamp_secs = \
        to_timestamp_secs(datetime(3000, 12, 25))

    return StartNewSellingAuctionParams(
        trd_id=trd_id,
        curr=curr,
        cust_id=cust_id,
        price=price,
        qty=qty,
        security_deposit_amt=security_deposit_amt,
        until_utc_timestamp_secs=until_utc_timestamp_secs
    )


StartNewBuyingAuctionParams = namedtuple(
    'StartNewBuyingAuctionParams',
    ['trd_id', 'curr', 'cust_id', 'price', 'qty',
     'security_deposit_amt', 'until_utc_timestamp_secs'])


@fixture
def start_new_buying_auction_params():
    trd_id = str(123)
    curr = 12
    cust_id = str(12345)
    price = 1_000
    qty = 25
    security_deposit_amt = 20_000
    until_utc_timestamp_secs = \
        to_timestamp_secs(datetime(3000, 12, 25))

    return StartNewBuyingAuctionParams(
        trd_id=trd_id,
        curr=curr,
        cust_id=cust_id,
        price=price,
        qty=qty,
        security_deposit_amt=security_deposit_amt,
        until_utc_timestamp_secs=until_utc_timestamp_secs
    )


class AsyncIOLoopContext:
    def __enter__(self):
        loop = asyncio.get_event_loop()

        def runner(fut):
            return loop.run_until_complete(
                asyncio.ensure_future(fut))

        return (loop, runner,)

    def __exit__(self, exc_type, exc_value, traceback):
        return None


@fixture
def asyncio_loop_and_runner():
    return AsyncIOLoopContext()


@fixture
def null_logging_stopwatch():
    return make_null_logging_stopwatch()


@fixture
def aio_kafka_producer_mock():
    return AsyncMock(AIOKafkaProducer)


@fixture
def samples_snapshot_sqlite3(test_root):
    return test_root / "samples/sqlite3-snapshot"


@fixture
def samples_snapshot_sqlite3_empty(test_root):
    return test_root / "samples/sqlite3-snapshot-empty"


@fixture
def samples_snapshot_sqlite3_falsy(test_root):
    return test_root / "samples/sqlite3-snapshot-falsy"
