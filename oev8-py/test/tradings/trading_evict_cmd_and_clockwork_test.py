from collections import namedtuple
from datetime import datetime
from unittest.mock import MagicMock, Mock
from pytest import fixture, raises  # type:ignore
from oev8.svcs.clockwork.trading import TradingClockworkService
from oev8.svcs.trading.clockwork_callbacks import \
    TradingClockworkCallback
from oev8.svcs.trading import TradingService
from oev8.svcs.cmd_handler import CmdHandler
from oev8.svcs.snapshot import SnapshotService
from oev8.svcs import ShutdownService
from oev8.svcs.event_writer import EventWriter
from oev8.svcs.journal import JournalWriter
from oev8.typedefs import BalanceType
from oev8.excs import TradingIsNotFound
from oev8.bench import CSVLoggingStopwatch
from oev8_pb2 import Oev8_CommandRequest
from oev8_pb2 import \
    OEV8_CMD_TRADING_FINALIZE, \
    OEV8_CMD_TRADING_EVICT


TradingClockworkFixture = namedtuple('TradingClockworkFixture',
                                     ['event_writer_mock',
                                      'shutdown_service_mock',
                                      'snapshot_service_mock',
                                      'journal_writer_mock',
                                      'trading_clockwork_cb',
                                      'trading_clockwork_service',
                                      'trading_service',
                                      'cmd_handler'])


@fixture
def trading_clockwork_fixture(
        seq_num_service,
        balance_service,
        item_count_service
):
    # mocks
    event_writer = MagicMock(EventWriter)
    shutdown_service = MagicMock(ShutdownService)
    snapshot_service = MagicMock(SnapshotService)
    journal_writer = MagicMock(JournalWriter)
    logging_stopwatch = MagicMock(CSVLoggingStopwatch)

    #
    trading_clockwork_cb = TradingClockworkCallback(None)
    trading_clockwork_service = TradingClockworkService(
        do_complete_trading=trading_clockwork_cb.do_complete,
        do_evict_trading=trading_clockwork_cb.do_evict)

    trading_service = TradingService(
        seq_num_service=seq_num_service,
        item_count_service=item_count_service,
        balance_service=balance_service,
        event_writer=event_writer,
        trading_clockwork_service=trading_clockwork_service)

    cmd_handler = CmdHandler(
        seq_num_service=seq_num_service,
        trading_service=trading_service,
        event_writer=event_writer,
        shutdown_service=shutdown_service,
        snapshot_service=snapshot_service,
        journal_writer=journal_writer,
        trading_clockwork_service=trading_clockwork_service,
        logging_stopwatch=logging_stopwatch)

    trading_clockwork_cb.cmd_handler = cmd_handler

    return TradingClockworkFixture(
        event_writer_mock=event_writer,
        shutdown_service_mock=shutdown_service,
        snapshot_service_mock=snapshot_service,
        journal_writer_mock=journal_writer,
        trading_clockwork_cb=trading_clockwork_cb,
        trading_clockwork_service=trading_clockwork_service,
        trading_service=trading_service,
        cmd_handler=cmd_handler)


def test_evict_cmdreq(trading_clockwork_fixture):
    """evict cmdreq 잘 처리하는지."""
    trading_service = trading_clockwork_fixture.trading_service
    balance_service = trading_service.balance_service
    trading_clockwork_service = \
        trading_clockwork_fixture.trading_clockwork_service

    # 새로운 trd 시작.
    trd_id = str(123)
    cust_id = str(12)
    curr = 1

    balance_service.deposit(BalanceType.BALANCE, cust_id, curr, 1_000_000)

    trading_service.start_new_trading_as_seller(cust_id, trd_id, curr,
                                                100, 90, 7, 0)

    # finalize and evict by cmdreq-ing.
    trading_service.finalize_trading(trd_id)
    trading_service.evict_trading(trd_id)

    # trading_clockwork_service에 등록되어 있는지?
    with raises(TradingIsNotFound):
        trading_clockwork_service.find(trd_id)


def test_evict_clockwork(trading_clockwork_fixture):
    """clockwork batch (finalize/evict) test.

        - clockwork batch으로 실행된 finalize/evict이 저널을 남기는지?
    """
    trading_service = trading_clockwork_fixture.trading_service
    balance_service = trading_service.balance_service
    trading_clockwork_service = \
        trading_clockwork_fixture.trading_clockwork_service
    journal_writer_mock = trading_clockwork_fixture.journal_writer_mock

    # mocks
    event_writer_mock = trading_clockwork_fixture.event_writer_mock
    event_writer_mock.commit_buffer = MagicMock()
    event_writer_mock.clear_buffer = MagicMock()

    # 새로운 trd 시작.
    trd_id = str(123)
    cust_id = str(12)
    curr = 1

    balance_service.deposit(BalanceType.BALANCE, cust_id, curr, 1_000_000)

    trading_service.start_new_trading_as_seller(cust_id, trd_id, curr,
                                                100, 90, 7, 0)

    # finalize and evict by clockwork
    dt_now = datetime.now().timestamp()
    trading_clockwork_service.batch(dt_now)

    # trading_clockwork_service에 등록되어 있는지?
    with raises(TradingIsNotFound):
        trading_clockwork_service.find(trd_id)

    # 저널?
    assert journal_writer_mock.write.call_count == 2

    finalize_journal = Oev8_CommandRequest()
    finalize_journal.ParseFromString(journal_writer_mock.write.call_args_list[0].args[3])
    assert finalize_journal.cmd_type == OEV8_CMD_TRADING_FINALIZE
    assert finalize_journal.trading_finalize.trd_id == trd_id

    evict_journal = Oev8_CommandRequest()
    evict_journal.ParseFromString(journal_writer_mock.write.call_args_list[1].args[3])
    assert evict_journal.cmd_type == OEV8_CMD_TRADING_EVICT
    assert evict_journal.trading_evict.trd_id == trd_id
