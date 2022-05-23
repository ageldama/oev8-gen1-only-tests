import logging
from pathlib import Path
import shutil
import os
import uuid
import json
from collections import namedtuple
from unittest.mock import MagicMock
import kafka  # type:ignore
import kafka.admin  # type:ignore
from pytest import fixture  # type:ignore
from oev8.client import TCPClient, CmdClient
from oev8.client.event_reader import KafkaEventReader
from oev8.client.event_callback import EventCallback
from oev8.svcs.journal.kafka import KafkaJournalReader
from oev8.svcs.cmd_handler import CmdHandler


logger = logging.getLogger('test.system_tests.conftest')


def kafka_create_topic(
        server_addr, topic_name,
        num_partitions=1, replication_factor=1):
    admin = kafka.KafkaAdminClient(bootstrap_servers=server_addr)

    admin.create_topics([
        kafka.admin.NewTopic(
            name=topic_name,
            num_partitions=num_partitions,
            replication_factor=replication_factor),
    ])

    admin.close()


def kafka_delete_topic(server_addr, topic_name):
    admin = kafka.KafkaAdminClient(bootstrap_servers=server_addr)
    admin.delete_topics([topic_name])
    admin.close()


def kafka_prepare_new_topic(
        server_addr, topic_name,
        num_partitions=1, replication_factor=1):
    try:
        kafka_delete_topic(server_addr, topic_name)
    except:
        logger.warning("kafka_delete_topic fail: (server=%s, topic=%s), IGNORE",
                       server_addr, topic_name,
                       exc_info=True)

    kafka_create_topic(server_addr, topic_name,
                       num_partitions, replication_factor)


@fixture
def journal_kafka_topic_resetter(test_config):
    cfg = test_config

    def f():
        kafka_prepare_new_topic(
            cfg.get_journal_writer_kafka_bootstrap_server(),
            cfg.get_journal_writer_kafka_topic())

    return f


@fixture
def prepare_test_config_events_kafka_topic(test_config):
    cfg = test_config
    kafka_prepare_new_topic(cfg.get_event_writer_kafka_bootstrap_server(),
                            cfg.get_event_writer_kafka_topic())


@fixture
def prepare_test_config_journal_kafka_topic(test_config):
    cfg = test_config
    kafka_prepare_new_topic(cfg.get_journal_writer_kafka_bootstrap_server(),
                            cfg.get_journal_writer_kafka_topic())


@fixture
def tcp_client(test_config):
    return TCPClient(test_config.get_server_host(),
                     test_config.get_server_port())


@fixture
def tcp_cmd_client(tcp_client):
    return CmdClient(tcp_client)


@fixture
def tcp_cmd_client_provider(test_config):
    def provider():
        tcp_client = TCPClient(test_config.get_server_host(),
                               test_config.get_server_port())

        return CmdClient(tcp_client)

    return provider


@fixture
def kafka_event_reader_and_callback_mock(test_config):
    cfg = test_config
    group_id = str(uuid.uuid4())
    reader = KafkaEventReader(
        cfg.get_event_writer_kafka_bootstrap_server(),
        cfg.get_event_writer_kafka_topic(),
        cfg.get_event_writer_kafka_client_id(),
        group_id)

    callback_mock = MagicMock(EventCallback)

    yield (reader, callback_mock,)

    try:
        reader.disconnect()
    except:
        logger.warning("KafkaEventReader.disconnect fail: %s, IGNORE",
                       reader,
                       exc_info=True)


@fixture
def kafka_journal_reader(test_config):
    server_addr = test_config.get_journal_writer_kafka_bootstrap_server()
    topic_name = test_config.get_journal_writer_kafka_topic()
    group_id = str(uuid.uuid4())
    client_id = str(uuid.uuid4())

    logger.debug('kafka_journal_reader: server_addr=%s, topic_name=%s, group_id=%s, client_id=%s',
                 server_addr, topic_name, group_id, client_id)

    cmd_handler_mock = MagicMock(CmdHandler)

    topic_partition = kafka.TopicPartition(
        topic_name, 0),

    reader = KafkaJournalReader(
        server_addr,
        topic_partition,
        group_id,
        client_id,
        cmd_handler_mock)

    return (reader, cmd_handler_mock,)


@fixture
def journal_kafka_depth_getter(test_config):
    server_addr = test_config.get_journal_writer_kafka_bootstrap_server()
    topic = test_config.get_journal_writer_kafka_topic()
    partition = test_config.get_journal_reader_kafka_partition()
    group_id = str(uuid.uuid4())
    client_id = str(uuid.uuid4())

    def f():
        consumer = kafka.KafkaConsumer(
            bootstrap_servers=server_addr,
            group_id=group_id,
            client_id=client_id)

        topic_partition = kafka.TopicPartition(topic, partition)

        consumer.assign([topic_partition])

        return consumer.end_offsets([topic_partition])[topic_partition]

    return f


@fixture
def snapshot_output_dir(test_config):
    p = Path(test_config.get_snapshot_output_dir())
    dirn = str(p.resolve())

    try:
        shutil.rmtree(dirn)
    except:
        logger.warning("shutil.rmtree FAIL (%s), IGNORE",
                       dirn,
                       exc_info=True)

    os.mkdir(dirn)
    return p


Oev8_SysTestFixture = namedtuple('Oev8_SysTestFixture',
                                 [
                                     'kafka_journal_reader',
                                     'cmd_handler_mock',
                                     'kafka_event_reader',
                                     'event_callback_mock',
                                     'snapshot_output_dir',
                                 ])


# NOTE: pgsql-db은 생성되어 있어야함.
# NOTE: 나머지 kafka-topic, snapshot-dir은 어차피 자동 생성.

@fixture
def oev8_sys_test_fixture(
        # PREP kafka : journal, events
        prepare_test_config_events_kafka_topic,
        prepare_test_config_journal_kafka_topic,
        kafka_journal_reader,
        kafka_event_reader_and_callback_mock,
        # PREP fs : snapshot-output-dir
        snapshot_output_dir,
):
    return Oev8_SysTestFixture(
        kafka_journal_reader=kafka_journal_reader[0],
        cmd_handler_mock=kafka_journal_reader[1],
        kafka_event_reader=kafka_event_reader_and_callback_mock[0],
        event_callback_mock=kafka_event_reader_and_callback_mock[1],
        snapshot_output_dir=snapshot_output_dir
    )


@fixture
def server_app_py_path(src_root):
    return src_root / "server_app.py"


@fixture
def oev8_sh_cmd(
        server_app_py_path
):
    env_key = 'OEV8_CMD_JSON_ARRAY'
    if env_key in os.environ:
        return json.loads(os.environ.get(env_key))
    else:
        server_app_fn = str(server_app_py_path.resolve())
        return ['python', server_app_fn]
