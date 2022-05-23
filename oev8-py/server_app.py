"""OeV8 Server Application Main"""

# pylint: disable=line-too-long, invalid-name, missing-function-docstring
# pylint: disable=bare-except, too-many-locals
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=try-except-raise

import asyncio
import functools
import logging
import logging.handlers
import sys
from datetime import datetime
from signal import SIGINT, SIGTERM
from typing import List, Any

import aiokafka  # type:ignore
import kafka  # type:ignore
import uvloop  # type:ignore

from oev8.asyncio import Awaiter
from oev8.bench import CSVLoggingStopwatch
from oev8.configs import Config
from oev8.excs import FatalError
from oev8.funcs import to_timestamp_secs
from oev8.protocols.tcp import TcpServerProcessor
from oev8.svcs import ShutdownService
from oev8.svcs.balance import BalanceService
from oev8.svcs.clockwork.trading import TradingClockworkService
from oev8.svcs.cmd_handler import CmdHandler
from oev8.svcs.event_writer import EventWriter
from oev8.svcs.event_writer.aiokafka import AioKafkaEventSender
from oev8.svcs.event_writer.protobuf import ProtoBufEventWriter
from oev8.svcs.event_writer.virtual import (BufferedEventWriter,
                                            ChainEventWriter)
from oev8.svcs.item_count import ItemCountService
from oev8.svcs.journal import JournalReader
from oev8.svcs.journal.aiokafka import AioKafkaJournalWriter
from oev8.svcs.journal.kafka import KafkaJournalReader
from oev8.svcs.seq_num import SeqNumService
from oev8.svcs.snapshot import SnapshotLoadingService, SnapshotService
from oev8.svcs.snapshot.sqlite3 import \
                                SqliteThreeSnapshotLoadingService, \
                                SqliteThreeSnapshotService
from oev8.svcs.trading import TradingService
from oev8.svcs.trading.clockwork_callbacks import TradingClockworkCallback
from oev8.typedefs import SeqNum, SeqType

logger_handle_tcp = logging.getLogger('server_app.handle_tcp')
logger_recover = logging.getLogger('server_app.recover')
logger_start_server = logging.getLogger('server_app.start_server')
logger_start_trading_clockwork = logging.getLogger(
    'server_app.start_trading_clockwork')
logger_start_snapshot_clockwork = logging.getLogger(
    'server_app.start_snapshot_clockwork')


def config_logger():
    "configure default logger."
    stdout_handler = logging.StreamHandler(sys.stdout)
    tmpfile_handler = None  # logging.FileHandler('/tmp/oev8.log')
    handlers = [stdout_handler]
    if tmpfile_handler is not None:
        handlers.append(tmpfile_handler)

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03d %(levelname)s %(name)s [%(filename)s:%(lineno)d] : %(message)s',  # noqa:E501
        datefmt='%y-%m-%d_%H:%M:%S',
        handlers=handlers
    )

    for (logger_name, level) in ({
            'kafka': logging.INFO,
            'aiokafka': logging.INFO,
    }).items():
        logging.getLogger(logger_name).setLevel(level)


async def handle_tcp(
        safety_lock: asyncio.Lock,
        processor,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter):
    logger = logger_handle_tcp

    addr = writer.get_extra_info('peername')
    logger.debug('Reading from %s', addr)

    while True:
        try:
            keep_connection: bool = await processor(
                reader, writer, safety_lock, addr)
            if not keep_connection:
                logger.warning("Disconnecting %s", addr)
                break

        except FatalError:
            logger.critical('Fatal error: %s', addr,
                            exc_info=False)
            sys.exit(1)

        except ConnectionError:
            # `writer.drain()` got failed.
            logger.info('Client disconnected or Wrong request: %s', addr,
                        exc_info=False)
            writer.close()
            return

        except AssertionError:
            logger.error('Fatal error, exiting', exc_info=True)
            sys.exit(1)

        except SystemExit:
            raise

        except:  # noqa:E722
            logger.error("Caught an exception: %s, disconnecting",
                         addr, exc_info=True)
            break

    writer.close()
    await writer.wait_closed()


async def start_server(
        config: Config,
        safety_lock: asyncio.Lock,
        awaiter: Awaiter,
        cmd_handler: CmdHandler,
        snapshot_service: SnapshotService,
        trading_clockwork_service: TradingClockworkService
):
    logger = logger_start_server

    host = config.get_server_host()
    port = config.get_server_port()

    request_timeout_secs = config.get_server_request_timeout_secs()
    read_timeout_secs = config.get_server_read_timeout_secs()

    # start aiokafka producers & clear awaiter-queue.
    await awaiter.gather_queue()

    #
    processor = TcpServerProcessor(
        cmd_handler, awaiter, request_timeout_secs, read_timeout_secs)

    server = await asyncio.start_server(
        functools.partial(handle_tcp, safety_lock, processor),
        host, port)
    addr = server.sockets[0].getsockname()  # type:ignore
    logger.info('TCP serving on %s', addr)

    try:
        # async with server:  # NOTE this `async with' really needed?
        await asyncio.gather(
            server.serve_forever(),
            start_snapshot_clockwork(config, snapshot_service),
            start_trading_clockwork(config,
                                    trading_clockwork_service))
    except asyncio.CancelledError:
        logger.info('Got SIGINT|SIGTERM, Starting Save-Quit...')
        async with safety_lock:
            cmd_handler.save_quit()


async def start_trading_clockwork(
        config: Config,
        trading_clockwork_service: TradingClockworkService
):
    logger = logger_start_trading_clockwork

    delay_secs = config.get_clockwork_tradings_delay_secs()
    logger.info('Starting tradings-clockwork with delay(%s)-seconds',
                delay_secs)
    while True:
        await asyncio.sleep(delay_secs)
        utc_now = datetime.utcnow()
        utc_timestamp = to_timestamp_secs(utc_now)
        logger.info('Clockwork tick (in UTC): %s, %s',
                    utc_now, utc_timestamp)

        trading_clockwork_service.batch(utc_timestamp)


async def start_snapshot_clockwork(
        config: Config,
        snapshot_service: SnapshotService
):
    logger = logger_start_snapshot_clockwork

    delay_secs = config.get_clockwork_snapshot_delay_secs()
    logger.info('Starting snapshot-clockwork with delay(%s)-seconds',
                delay_secs)
    while True:
        await asyncio.sleep(delay_secs)
        result = snapshot_service.save()
        logger.info('Snapshotted: %s', result)


def make_journal_reader(
        config: Config,
        cmd_handler: CmdHandler
) -> JournalReader:
    # journal-reader
    server_addr = config.get_journal_writer_kafka_bootstrap_server()
    topic = config.get_journal_writer_kafka_topic()
    partition = config.get_journal_reader_kafka_partition()
    client_id = config.get_journal_reader_kafka_client_id()
    group_id = config.get_journal_reader_kafka_group_id()
    journal_reader = KafkaJournalReader(
        kafka_server_addr=server_addr,
        topic_partition=kafka.TopicPartition(topic, partition),
        group_id=group_id,
        client_id=client_id,
        cmd_handler=cmd_handler)

    return journal_reader


def recover(
        config: Config,
        seq_num_service: SeqNumService,
        snapshot_loading_svc: SnapshotLoadingService,
        journal_reader: JournalReader
):
    logger = logger_recover

    logger.info('Recovering...')

    # find latest snapshot
    latest_snapshot_fn = snapshot_loading_svc.find_latest(
        config.get_snapshot_output_dir())
    if latest_snapshot_fn is None:
        logger.info('No snapshot found')
    else:
        logger.info('Loading latest snapshot from: %s',
                    latest_snapshot_fn)

        # load snapshot
        snapshot_loading_svc.load(latest_snapshot_fn)

        #
        cur_seq = seq_num_service.cur_val(SeqType.CMD_REQ)
        logger.info('Snapshot of seq-num(%s) has loaded: %s',
                    cur_seq, latest_snapshot_fn)

    # cur_val번부터, 계속...
    seq_num = SeqNum(seq_num_service.cur_val(SeqType.CMD_REQ) + 1)
    logger.info('Journal replaying starting: from_seq=%s', seq_num)

    (replayed, replay_count,) = journal_reader.read(seq_num)

    logger.info(
        'Journal replaying done: (new_seq_num=%s, replayed=%s, replay_count=%s)',  # noqa:E501
        seq_num_service.cur_val(SeqType.CMD_REQ), replayed, replay_count)


def enter_server_async(
        # pylint: disable=unused-argument
        logger: logging.Logger,
        loop: asyncio.AbstractEventLoop,
        config: Config,
        safety_lock: asyncio.Lock,
        awaiter: Awaiter,
        cmd_handler: CmdHandler,
        snapshot_svc: SnapshotService,
        trading_clockwork_svc: TradingClockworkService
) -> Any:
    # start tcp-server
    main_task = asyncio.ensure_future(
        start_server(config, safety_lock, awaiter,
                     cmd_handler,
                     snapshot_svc,
                     trading_clockwork_svc),
        loop=loop)

    loop.add_signal_handler(SIGINT, main_task.cancel)
    loop.add_signal_handler(SIGTERM, main_task.cancel)

    try:
        return loop.run_until_complete(main_task)
    except SystemExit:
        raise
    finally:
        loop.close()


def wire_and_start(config_fn: str):
    config_logger()
    logger = logging.getLogger('server_app')

    config = Config()

    logger.info("LOADING CONFIG FROM: %s", config_fn)
    config.read_file(config_fn)

    logger.info("LOADED CONFIG: %s", config.dump())

    config.check()

    # csvLoggingStopwatch
    handler_sw = None
    if len(config.get_stopwatch_filename()) > 0:
        handler_sw = logging.handlers.RotatingFileHandler(
            config.get_stopwatch_filename(), encoding='ascii',
            maxBytes=(1024 ** 2) * config.get_stopwatch_max_mbytes(),
            backupCount=config.get_stopwatch_backup_count())

    logger_sw = CSVLoggingStopwatch.new_logger('stopwatch',
                                               handler=handler_sw)
    sw_cmdreq = CSVLoggingStopwatch(logger_sw, 'cmdreq')
    sw_journal_writer = CSVLoggingStopwatch(logger_sw, 'journal_writer')
    sw_event_writer = CSVLoggingStopwatch(logger_sw, 'event_writer')
    sw_snapshot_saver = CSVLoggingStopwatch(logger_sw, 'snapshot')

    # asyncio
    loop = asyncio.get_event_loop()

    awaiter = Awaiter(loop)

    # Kafka EventSender, ProtoBufEventWriter.
    aio_kafka_event_producer = aiokafka.AIOKafkaProducer(
        bootstrap_servers=config.get_event_writer_kafka_bootstrap_server(),
        client_id=config.get_event_writer_kafka_client_id(),
        loop=loop)

    awaiter.add_awaitable(aio_kafka_event_producer.start())

    aio_kafka_event_sender = AioKafkaEventSender(
        aio_kafka_event_producer, config.get_event_writer_kafka_topic(),
        awaiter,
        batch_size=config.get_event_writer_kafka_batch_size())

    protobuf_event_writer = ProtoBufEventWriter(aio_kafka_event_sender)

    # ChainEventWriter
    event_writers: List[EventWriter] = [protobuf_event_writer]

    chain_event_writer = ChainEventWriter(
        chain=event_writers)

    # the "event_writer".
    event_writer = BufferedEventWriter(delegate=chain_event_writer,
                                       logging_stopwatch=sw_event_writer)

    # TradingClockworkService
    trading_clockwork_cb = TradingClockworkCallback(None)
    trading_clockwork_svc = TradingClockworkService(
        do_complete_trading=trading_clockwork_cb.do_complete,
        do_evict_trading=trading_clockwork_cb.do_evict)

    # services
    seq_num_svc = SeqNumService()
    balance_svc = BalanceService()
    item_count_svc = ItemCountService()
    trading_svc = TradingService(
        seq_num_service=seq_num_svc,
        item_count_service=item_count_svc,
        balance_service=balance_svc,
        event_writer=event_writer,
        trading_clockwork_service=trading_clockwork_svc)
    shutdown_svc = ShutdownService()
    snapshot_svc = SqliteThreeSnapshotService(
        output_dir=config.get_snapshot_output_dir(),
        seq_num_service=seq_num_svc,
        balance_service=balance_svc,
        item_count_service=item_count_svc,
        trading_service=trading_svc,
        trading_clockwork_service=trading_clockwork_svc,
        logging_stopwatch=sw_snapshot_saver)

    # journal-writer
    aio_kafka_journal_producer = aiokafka.AIOKafkaProducer(
        bootstrap_servers=config.get_journal_writer_kafka_bootstrap_server(),
        client_id=config.get_journal_writer_kafka_client_id(),
        loop=loop)

    awaiter.add_awaitable(aio_kafka_journal_producer.start())

    journal_writer = AioKafkaJournalWriter(
        aio_kafka_journal_producer, config.get_journal_writer_kafka_topic(),
        awaiter, sw_journal_writer)

    #
    cmd_handler = CmdHandler(
        seq_num_service=seq_num_svc,
        trading_service=trading_svc,
        event_writer=event_writer,
        shutdown_service=shutdown_svc,
        snapshot_service=snapshot_svc,
        journal_writer=journal_writer,
        trading_clockwork_service=trading_clockwork_svc,
        logging_stopwatch=sw_cmdreq)

    trading_clockwork_cb.cmd_handler = cmd_handler

    #
    snapshot_loading_svc = SqliteThreeSnapshotLoadingService(
        seq_num_service=seq_num_svc,
        balance_service=balance_svc,
        item_count_service=item_count_svc,
        trading_service=trading_svc,
        trading_clockwork_service=trading_clockwork_svc)

    journal_reader = make_journal_reader(config, cmd_handler)

    try:
        recover(config,
                seq_num_svc,
                snapshot_loading_svc,
                journal_reader)
    except:  # noqa:E722
        logger.critical('Error during recover. FATAL.',
                        exc_info=True)
        raise

    #
    safety_lock = asyncio.Lock()

    return enter_server_async(
        logger=logger,
        loop=loop,
        config=config,
        safety_lock=safety_lock,
        awaiter=awaiter,
        cmd_handler=cmd_handler,
        snapshot_svc=snapshot_svc,
        trading_clockwork_svc=trading_clockwork_svc
    )


if __name__ == '__main__':
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    assert len(sys.argv[1]) > 1, 'Specify config file as argument.'
    wire_and_start(sys.argv[1])
