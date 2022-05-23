import logging
import asyncio
from glob import glob
from pytest import mark, fixture  # type:ignore
import kafka  # type:ignore
from oev8.kafka.replay import replay
from . import is_system_test_disabled
from test.testsup.retries import RetryFail, async_retry
from test.testsup.kafka import ListCollector, ProtobufEventKafkaMessageSerDeser
from oev8.typedefs import BalanceType
from oev8_pb2 import OEV8_EVT_BALANCE_DEPOSIT, \
    OEV8_EVT_CAUSE_BALANCE_DEPOSIT_DEPOSIT, \
    OEV8_EVT_SNAPSHOT, \
    OEV8_EVT_CAUSE_ADMIN


logger = logging.getLogger('test.system_tests.recover_from_partial_snapshot_and_journal_test')


async def tbody_1st_session(
        oev8_sh_cmd,
        test_config_path,
        tcp_cmd_client
):
    # start process.
    cfg_fn = str(test_config_path.resolve())
    proc = await asyncio.create_subprocess_exec(
        *(oev8_sh_cmd + [cfg_fn]))

    logger.debug('PID(%s) Running?(%s)',
                 proc.pid, proc.returncode is None)

    logger.debug('tcp_cmd_client: %s',
                 tcp_cmd_client)

    # try to connect...
    async def connect():
        logger.info('TCP Client CONNECTING...')
        await tcp_cmd_client.client.connect()
        logger.info('TCP Client CONNECTED..')

    await async_retry(connect, max_retries=10, delay_secs=1)

    # 1) Balance-Deposit(Cust=1, Curr=1, Amt=X)
    balance_deposit_resp = await tcp_cmd_client.balance_deposit(
        cust_id='1', balance_type=BalanceType.BALANCE,
        curr=1, amt=123)

    logger.info('BALANCE-DEPOSIT(Cust=1, Curr=1, Amt=X): %s',
                balance_deposit_resp)

    assert balance_deposit_resp.new_amt == '123'

    # 2) Snapshot
    await tcp_cmd_client.snapshot()

    # 3) Balance-Deposit(Cust=1, Curr=1, Amt=Y)
    balance_deposit_resp = await tcp_cmd_client.balance_deposit(
        cust_id='1', balance_type=BalanceType.BALANCE,
        curr=1, amt=456)

    logger.info('BALANCE-DEPOSIT(Cust=1, Curr=1, Amt=Y): %s',
                balance_deposit_resp)

    assert balance_deposit_resp.new_amt == str(123 + 456)

    # wait...
    proc.kill()  # no more snapshotting.
    retcode = await proc.wait()
    logger.info('Terminated with: %s', retcode)


async def tbody_2nd_session(
        oev8_sh_cmd,
        test_config_path,
        tcp_cmd_client
):
    # start process.
    cfg_fn = str(test_config_path.resolve())
    proc = await asyncio.create_subprocess_exec(
        *(oev8_sh_cmd + [cfg_fn]))

    logger.debug('PID(%s) Running?(%s)',
                 proc.pid, proc.returncode is None)

    logger.debug('tcp_cmd_client: %s',
                 tcp_cmd_client)

    # try to connect...
    async def connect():
        logger.info('TCP Client CONNECTING...')
        await tcp_cmd_client.client.connect()
        logger.info('TCP Client CONNECTED..')

    await async_retry(connect, max_retries=10, delay_secs=1)

    # 2) assert Balance-Get(Cust=1, Curr=1) == X + Y
    balance_get_a = await tcp_cmd_client.balance_get(
        cust_id='1', balance_type=BalanceType.BALANCE,
        curr=1)

    logger.info('BALANCE-GET (Cust=1, Curr=1): %s', balance_get_a)

    assert balance_get_a.amt == str(123 + 456)

    # wait...
    proc.kill()
    retcode = await proc.wait()
    logger.info('Terminated with: %s', retcode)


def event_writer_replay(config):
    topic_name = config.get_event_writer_kafka_topic()
    server = config.get_event_writer_kafka_bootstrap_server()
    group_id = 'systest-recover_from_partial_snapshot_and_journal_test-replayer'
    client_id = 'systest-recover_from_partial_snapshot_and_journal_test-replayer'

    collector = ListCollector()

    topic_partition = kafka.TopicPartition(topic_name, 0)

    consumer = kafka.KafkaConsumer(
        bootstrap_servers=server,
        group_id=group_id,
        client_id=client_id
    )

    consumer.assign([topic_partition])

    (replayed, poll_count,) = replay(
        consumer, topic_partition, 1,
        msg_transformer=ProtobufEventKafkaMessageSerDeser.parse_msg,
        msg_seq_extractor=ProtobufEventKafkaMessageSerDeser.seq_num_of,
        msg_replayer=collector
    )

    assert replayed

    assert len(collector.coll) == 3

    # 1st evt: BALANCE_DEPOSIT
    evt = collector.coll[0]

    assert evt.cmd_uuid is not None
    assert evt.seq_num == '1'
    assert evt.evt_type == OEV8_EVT_BALANCE_DEPOSIT
    assert evt.evt_cause_type == OEV8_EVT_CAUSE_BALANCE_DEPOSIT_DEPOSIT
    assert evt.balance_deposit.balance_type == BalanceType.BALANCE.value
    assert evt.balance_deposit.curr == 1
    assert evt.balance_deposit.cust_id == '1'
    assert evt.balance_deposit.amt == '123'

    # 2nd evt: SNAPSHOT
    evt = collector.coll[1]

    assert evt.cmd_uuid is not None
    assert evt.seq_num == '2'
    assert evt.evt_type == OEV8_EVT_SNAPSHOT
    assert evt.evt_cause_type == OEV8_EVT_CAUSE_ADMIN

    # 3rd evt: BALANCE_DEPOSIT
    evt = collector.coll[2]

    assert evt.cmd_uuid is not None
    assert evt.seq_num == '3'
    assert evt.evt_type == OEV8_EVT_BALANCE_DEPOSIT
    assert evt.evt_cause_type == OEV8_EVT_CAUSE_BALANCE_DEPOSIT_DEPOSIT
    assert evt.balance_deposit.balance_type == BalanceType.BALANCE.value
    assert evt.balance_deposit.curr == 1
    assert evt.balance_deposit.cust_id == '1'
    assert evt.balance_deposit.amt == '456'


@mark.skipif(is_system_test_disabled(), reason='system test')
def test_recover_from_partial_snapshot_and_jorunal(
        oev8_sh_cmd,
        oev8_sys_test_fixture,
        # cmd_client
        tcp_cmd_client_provider,
        # asyncio
        asyncio_loop_and_runner,
        # fs paths
        test_config_path,
        # cfg
        test_config
):
    '''스냅샷/저널의 합으로 복구하는지 확인하기.

           1) Balance-Deposit(Cust=1, Curr=1, Amt=X)
           2) Snapshot
           3) Balance-Deposit(Cust=1, Curr=1, Amt=Y)

           T) assert Balance-Get(Cust=1, Curr=1) == X + Y
    '''
    # testing steps:
    # snapshot 디렉토리 목록 - 비어 있는지?
    snapshot_glob_path = \
        oev8_sys_test_fixture.snapshot_output_dir / "*.oev8.sqlite3"

    before_snapshot_glob = glob(str(snapshot_glob_path))
    assert len(before_snapshot_glob) == 0

    # 실행 #1.
    with asyncio_loop_and_runner as lnr:
        lnr[1](tbody_1st_session(oev8_sh_cmd,
                                 test_config_path,
                                 tcp_cmd_client_provider()))

    # snapshot 디렉토리 목록 - 스냅샷 1개
    after_snapshot_glob = glob(str(snapshot_glob_path))
    assert len(after_snapshot_glob) == 1

    # 실행 #2.
    with asyncio_loop_and_runner as lnr:
        lnr[1](tbody_2nd_session(oev8_sh_cmd,
                                 test_config_path,
                                 tcp_cmd_client_provider()))

    # event-writer 검증.
    event_writer_replay(test_config)
