from unittest.mock import Mock, MagicMock, call, ANY
from oev8_pb2 import \
    OEV8_CMD_TRADING_FINALIZE, OEV8_CMD_TRADING_EVICT
from oev8.excs import TradingIsNotFound
from oev8.svcs.cmd_handler import CmdHandler
from oev8.svcs.trading.clockwork_callbacks import \
    TradingClockworkCallback
from oev8.client import cmd_req_of, cmd_req_to_bytes


def test_do_complete_calls():
    cmd_handler = Mock(CmdHandler)
    cmd_handler.handle = MagicMock(return_value=(b'', True,))
    cb = TradingClockworkCallback(cmd_handler)

    trd_id = '123'

    assert cb.do_complete(trd_id)

    req = cmd_req_of(OEV8_CMD_TRADING_FINALIZE)
    req.trading_finalize.trd_id = trd_id
    (req_bs, _, _,) = cmd_req_to_bytes(req)

    cmd_handler.handle.assert_has_calls([
        call(ANY, ANY, req_bs, False)])


def test_do_complete_ignores_err():
    trd_id = '123'

    cmd_handler = Mock(CmdHandler)
    cmd_handler.handle = MagicMock(
        side_effect=TradingIsNotFound(trd_id=trd_id))

    cb = TradingClockworkCallback(cmd_handler)

    assert not cb.do_complete(trd_id)


def test_do_evict_calls():
    cmd_handler = Mock(CmdHandler)
    cb = TradingClockworkCallback(cmd_handler)

    trd_id = '123'

    cb.do_evict(trd_id)

    req = cmd_req_of(OEV8_CMD_TRADING_EVICT)
    req.trading_evict.trd_id = trd_id
    (req_bs, _, _,) = cmd_req_to_bytes(req)

    cmd_handler.handle.assert_has_calls([
        call(ANY, ANY, req_bs, False)])


def test_do_evict_ignores_err():
    trd_id = '123'

    cmd_handler = Mock(CmdHandler)
    cmd_handler.handle = MagicMock(
        side_effect=TradingIsNotFound(trd_id=trd_id))

    cb = TradingClockworkCallback(cmd_handler)

    assert not cb.do_evict(trd_id)
