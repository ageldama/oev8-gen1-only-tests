# pylint: disable=too-few-public-methods

from unittest.mock import AsyncMock, Mock, MagicMock
from typing import Tuple
import os
import random
import uuid
import datetime
import struct
import xxhash  # type:ignore
from sortedcontainers import SortedDict  # type:ignore
from oev8.funcs import to_timestamp_secs
from oev8.typedefs import BalanceType, OrderOption
from oev8.typedefs import OrderMakerTaker, TradingState
from oev8.ints import UInt256
from oev8.bench import CSVLoggingStopwatch


def NOTHING():
    'nothing.'
    return NOTHING


def id_or_call(obj):
    if callable(obj):
        return obj()
    return obj


def rand_1mil() -> int:
    return random.randint(0, 1_000_000)


def rand_balance_type() -> BalanceType:
    return random.choice([BalanceType.BALANCE, BalanceType.EARNING])


def rand_order_option() -> OrderOption:
    return random.choice([
        OrderOption.NONE,
        OrderOption.FILL_OR_KILL,
        OrderOption.IMMEDIATE_OR_CANCEL,
    ])


def rand_order_option2() -> Tuple[OrderOption, int]:
    v = rand_order_option()
    return (v, v.value,)


def rand_balance_type2() -> Tuple[BalanceType, int]:
    v = rand_balance_type()
    return (v, v.value,)


def rand_curr() -> int:
    return random.randint(0, 100)


def rand_cmd_type() -> int:
    return random.randint(0, 100)


def uuid_int() -> int:
    return uuid.uuid4().int


def rand_cmd_uuid() -> bytes:
    return uuid.uuid4().bytes


def rand_order_maker_taker() -> OrderMakerTaker:
    return random.choice([OrderMakerTaker.MAKER,
                          OrderMakerTaker.TAKER])


def rand_order_maker_taker2() -> Tuple[OrderMakerTaker, int]:
    v = rand_order_maker_taker()
    return (v, v.value,)


def rand_trading_state() -> TradingState:
    return random.choice([
        TradingState.OPEN,
        TradingState.COMPLETED,
        TradingState.PAUSED,
        TradingState.CANCELLED])


def rand_trading_state2() -> Tuple[TradingState, int]:
    v = rand_trading_state()
    return (v, v.value,)


def rand_uint256():
    return random.randint(0, UInt256.MAX)


def rand_bytes(min_len=0, max_len=65535):
    return bytes(random.randint(0, 255)
                 for i in range(random.randint(min_len, max_len)))


def inverse_bytes(bs):
    return bytes([b ^ 0xff for b in bs])


class BytesStreamReader:
    def __init__(self, byte_seq):
        self.byte_seq = byte_seq
        self.pos = 0

        self.read = AsyncMock(side_effect=self.read_ahead)

    def read_ahead(self, nlen: int) -> bytes:
        result = self.byte_seq[self.pos:(self.pos+nlen)]
        self.pos = self.pos + nlen
        return result


def make_StreamWriter_mock():
    writer = Mock()
    writer.write = Mock()
    writer.drain = AsyncMock()
    return writer


def make_request_bytes(
        payload_bytes: bytes,
        utc_now: datetime.datetime
) -> bytes:
    result = b''
    xx64 = xxhash.xxh64_intdigest(payload_bytes)
    result = struct.pack('!HQQ',
                         len(payload_bytes), xx64,
                         to_timestamp_secs(utc_now))
    result = result + payload_bytes
    return result


class EnvOverride:
    def __init__(self, env_name, val):
        self.env_name = env_name
        self.val = val
        self.backup = None

    def __enter__(self):
        self.backup = os.environ.get(self.env_name)
        os.environ[self.env_name] = self.val
        return (self.env_name, os.getenv(self.env_name),)

    def __exit__(self, exc_type, exc_val, tb):
        if self.backup is not None:
            os.environ[self.env_name] = self.backup
        else:
            os.environ.pop(self.env_name)


def make_null_logging_stopwatch():
    logging_stopwatch = Mock(CSVLoggingStopwatch)

    logging_stopwatch.__enter__ = MagicMock()
    logging_stopwatch.__exit__ = MagicMock(return_value=None)
    logging_stopwatch.__aenter__ = AsyncMock()
    logging_stopwatch.__aexit__ = AsyncMock(return_value=None)

    return logging_stopwatch


def assert_orderbook(orderbook):
    """적절한 오더북 상태인지?
     -- 정렬이 제대로 가능한지 (integer-keyed, sorted-dicts)"""

    # print('ORDERBOOK:', orderbook)

    assert isinstance(orderbook, SortedDict)
    for price in orderbook.keys():
        assert isinstance(price, int)

        offers = orderbook[price]
        assert isinstance(offers, SortedDict)

        for order_id in offers.keys():
            assert isinstance(order_id, int)

            item_qty = offers[order_id]
            assert isinstance(item_qty, int)
