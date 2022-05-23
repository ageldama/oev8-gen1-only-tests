import logging
import asyncio
import time
import multiprocessing
import struct
import signal
import os
from unittest.mock import Mock, AsyncMock
from pytest import mark, raises, fixture  # type:ignore
from server_app import enter_server_async
from oev8.asyncio import Awaiter
from oev8.configs import Config
from oev8.svcs.journal import JournalWriterFail
from oev8.svcs.event_writer import EventWriterFail
from oev8.svcs.snapshot import SnapshotService
from oev8.svcs.cmd_handler import CmdHandler
from oev8.svcs.clockwork.trading import TradingClockworkService
from oev8.client import TCPClient, CmdClient
from oev8.excs import FatalError


@fixture
def enter_server_async_config() -> Config:
    # const
    server_host = '127.0.0.1'
    server_port = 18888
    server_request_timeout_secs = 5
    server_read_timeout_secs = 3

    clockwork_tradings_delay_secs = 10
    clockwork_snapshot_delay_secs = 10

    # config
    config = Mock(Config)

    config.get_server_host = Mock(return_value=server_host)
    config.get_server_port = Mock(return_value=server_port)
    config.get_server_request_timeout_secs = Mock(
        return_value=server_request_timeout_secs)
    config.get_server_read_timeout_secs = Mock(
        return_value=server_read_timeout_secs)
    config.get_clockwork_tradings_delay_secs = Mock(
        return_value=clockwork_tradings_delay_secs)
    config.get_clockwork_snapshot_delay_secs = Mock(
        return_value=clockwork_snapshot_delay_secs)

    return config


@mark.asyncio
async def test_enter_server_async(enter_server_async_config):
    def runner(log_queue: multiprocessing.Queue):
        # logger
        logger = Mock(logging.Logger)

        #
        event_loop = asyncio.new_event_loop()

        lock = asyncio.Lock(loop=event_loop)

        awaiter = Mock(Awaiter)
        awaiter.gather_queue = AsyncMock(return_value=[])
        awaiter.add_awaitable = Mock(return_value=None)

        #
        snapshot_service = Mock(SnapshotService)
        snapshot_service.save = Mock(return_value=None)

        cmd_handler = Mock(CmdHandler)
        cmd_handler.handle = Mock(side_effect=SystemExit)

        trading_clockwork_service = Mock(TradingClockworkService)
        trading_clockwork_service.batch = Mock(return_value=None)

        # do it
        try:
            enter_server_async(logger, event_loop,
                               enter_server_async_config,
                               lock, awaiter, cmd_handler,
                               snapshot_service, trading_clockwork_service)
        except SystemExit:
            log_queue.put_nowait('SystemExit')

    #
    log_queue = multiprocessing.Queue()

    proc = multiprocessing.Process(target=runner, args=(log_queue,),
                                   daemon=True)
    proc.start()

    # client
    tcp_client = TCPClient(enter_server_async_config.get_server_host(),
                           enter_server_async_config.get_server_port())
    cmd_client = CmdClient(tcp_client)

    time.sleep(0.1)  # wait for server starting.

    await tcp_client.connect()
    with raises(struct.error):
        await cmd_client.ping()  # initiates SystemExit

    proc.join()

    #
    assert not log_queue.empty()
    assert log_queue.get_nowait() == 'SystemExit'


@mark.parametrize('signum', [signal.SIGTERM, signal.SIGINT])
@mark.asyncio
async def test_enter_server_async__sigterm(
        signum,
        enter_server_async_config
):
    def runner(log_queue: multiprocessing.Queue):
        # logger
        logger = Mock(logging.Logger)

        #
        event_loop = asyncio.new_event_loop()

        lock = asyncio.Lock(loop=event_loop)

        awaiter = Mock(Awaiter)
        awaiter.gather_queue = AsyncMock(return_value=[])
        awaiter.add_awaitable = Mock(return_value=None)

        #
        snapshot_service = Mock(SnapshotService)
        snapshot_service.save = Mock(return_value=None)

        cmd_handler = Mock(CmdHandler)
        cmd_handler.handle = Mock(side_effect=SystemExit)

        trading_clockwork_service = Mock(TradingClockworkService)
        trading_clockwork_service.batch = Mock(return_value=None)

        # do it
        try:
            enter_server_async(logger, event_loop,
                               enter_server_async_config,
                               lock, awaiter, cmd_handler,
                               snapshot_service, trading_clockwork_service)
        except SystemExit:
            log_queue.put_nowait('SystemExit')

        cmd_handler.save_quit.assert_called_once()
        log_queue.put_nowait('SNAPSHOT')

    #
    log_queue = multiprocessing.Queue()

    proc = multiprocessing.Process(target=runner, args=(log_queue,),
                                   daemon=True)
    proc.start()

    #
    time.sleep(0.1)  # wait for server starting.

    os.kill(proc.pid, signum)

    proc.join()

    #
    assert not log_queue.empty()
    assert log_queue.get_nowait() == 'SNAPSHOT'


@mark.parametrize('failure_klass', [EventWriterFail, JournalWriterFail])
@mark.asyncio
async def test_enter_server_async__cmd_handler_failures(
        failure_klass,
        enter_server_async_config
):
    def runner(log_queue: multiprocessing.Queue):
        # logger
        logger = Mock(logging.Logger)

        #
        event_loop = asyncio.new_event_loop()

        lock = asyncio.Lock(loop=event_loop)

        awaiter = Mock(Awaiter)
        awaiter.gather_queue = AsyncMock(return_value=[])
        awaiter.add_awaitable = Mock(return_value=None)

        #
        snapshot_service = Mock(SnapshotService)
        snapshot_service.save = Mock(return_value=None)

        cmd_handler = Mock(CmdHandler)
        cmd_handler.handle = Mock(side_effect=failure_klass)

        trading_clockwork_service = Mock(TradingClockworkService)
        trading_clockwork_service.batch = Mock(return_value=None)

        # do it
        try:
            enter_server_async(logger, event_loop,
                               enter_server_async_config,
                               lock, awaiter, cmd_handler,
                               snapshot_service, trading_clockwork_service)
        except SystemExit:
            log_queue.put_nowait('SystemExit')

        cmd_handler.handle.assert_called_once()
        log_queue.put_nowait('CMD_HANDLER')

    #
    log_queue = multiprocessing.Queue()

    proc = multiprocessing.Process(target=runner, args=(log_queue,),
                                   daemon=True)
    proc.start()

    # client
    tcp_client = TCPClient(enter_server_async_config.get_server_host(),
                           enter_server_async_config.get_server_port())
    cmd_client = CmdClient(tcp_client)

    time.sleep(0.1)  # wait for server starting.

    await tcp_client.connect()
    with raises(struct.error):
        await cmd_client.ping()  # initiates an failure

    proc.join()

    #
    assert not log_queue.empty()
    assert log_queue.get_nowait() == 'SystemExit'
    assert log_queue.get_nowait() == 'CMD_HANDLER'


@mark.parametrize('failure_klass', [EventWriterFail, JournalWriterFail])
@mark.asyncio
async def test_enter_server_async__clockwork_tradings_fail(
        failure_klass,
        enter_server_async_config
):
    enter_server_async_config.get_clockwork_tradings_delay_secs = Mock(
        return_value=0.1)

    def runner(log_queue: multiprocessing.Queue):
        # logger
        logger = Mock(logging.Logger)

        #
        event_loop = asyncio.new_event_loop()

        lock = asyncio.Lock(loop=event_loop)

        awaiter = Mock(Awaiter)
        awaiter.gather_queue = AsyncMock(return_value=[])
        awaiter.add_awaitable = Mock(return_value=None)

        #
        snapshot_service = Mock(SnapshotService)
        snapshot_service.save = Mock(return_value=None)

        cmd_handler = Mock(CmdHandler)
        cmd_handler.handle = Mock(side_effect=None)

        trading_clockwork_service = Mock(TradingClockworkService)
        trading_clockwork_service.batch = Mock(side_effect=failure_klass)

        # do it
        try:
            enter_server_async(logger, event_loop,
                               enter_server_async_config,
                               lock, awaiter, cmd_handler,
                               snapshot_service, trading_clockwork_service)
        except failure_klass:
            log_queue.put_nowait('FatalError')

        trading_clockwork_service.batch.assert_called_once()
        log_queue.put_nowait('TRADING_CLOCKWORK')

    #
    log_queue = multiprocessing.Queue()

    proc = multiprocessing.Process(target=runner, args=(log_queue,),
                                   daemon=True)
    proc.start()
    proc.join()

    #
    assert not log_queue.empty()
    assert log_queue.get_nowait() == 'FatalError'
    assert log_queue.get_nowait() == 'TRADING_CLOCKWORK'


@mark.parametrize('failure_klass', [EventWriterFail, JournalWriterFail])
@mark.asyncio
async def test_enter_server_async__clockwork_snapshot_fail(
        failure_klass,
        enter_server_async_config
):
    enter_server_async_config.get_clockwork_snapshot_delay_secs = Mock(
        return_value=0.1)

    def runner(log_queue: multiprocessing.Queue):
        # logger
        logger = Mock(logging.Logger)

        #
        event_loop = asyncio.new_event_loop()

        lock = asyncio.Lock(loop=event_loop)

        awaiter = Mock(Awaiter)
        awaiter.gather_queue = AsyncMock(return_value=[])
        awaiter.add_awaitable = Mock(return_value=None)

        #
        snapshot_service = Mock(SnapshotService)
        snapshot_service.save = Mock(side_effect=failure_klass)

        cmd_handler = Mock(CmdHandler)
        cmd_handler.handle = Mock(side_effect=None)

        trading_clockwork_service = Mock(TradingClockworkService)
        trading_clockwork_service.batch = Mock(return_value=None)

        # do it
        try:
            enter_server_async(logger, event_loop,
                               enter_server_async_config,
                               lock, awaiter, cmd_handler,
                               snapshot_service, trading_clockwork_service)
        except failure_klass:
            log_queue.put_nowait('FatalError')

        snapshot_service.save.assert_called_once()
        log_queue.put_nowait('SNAPSHOT')

    #
    log_queue = multiprocessing.Queue()

    proc = multiprocessing.Process(target=runner, args=(log_queue,),
                                   daemon=True)
    proc.start()
    proc.join()

    #
    assert not log_queue.empty()
    assert log_queue.get_nowait() == 'FatalError'
    assert log_queue.get_nowait() == 'SNAPSHOT'
