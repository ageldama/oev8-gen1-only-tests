from pytest import fixture  # type:ignore
from oev8.configs import Config
from test.testsup import EnvOverride  # pylint: disable=wrong-import-order


@fixture
def all_ok_config(test_root):
    config_path = test_root / "configs/all_ok.ini"

    cfg = Config()
    cfg.read_file(config_path.resolve())

    return cfg


def test_all_ok_config(all_ok_config):
    cfg = all_ok_config

    assert cfg.get_server_host() == '127.0.0.1'

    assert cfg.get_server_port() == 8888

    assert cfg.get_server_request_timeout_secs() == 5

    assert cfg.get_server_read_timeout_secs() == 3

    assert cfg.get_event_writer_kafka_topic() == 'oev8_events'

    assert cfg.get_event_writer_kafka_bootstrap_server() == \
        ['127.0.0.1:9092']

    assert cfg.get_event_writer_kafka_client_id() == 'oev8_event_writer'

    assert cfg.get_event_writer_kafka_batch_size() == 123

    assert cfg.get_journal_writer_kafka_topic() == 'oev8_journal'

    assert cfg.get_journal_writer_kafka_bootstrap_server() == \
        ['127.0.0.1:9092']

    assert cfg.get_journal_writer_kafka_client_id() == \
        'oev8_journal_writer'

    assert cfg.get_journal_reader_kafka_client_id() == \
        'oev8_journal_reader'

    assert cfg.get_journal_reader_kafka_group_id() == \
        'oev8_journal_reader'

    assert cfg.get_journal_reader_kafka_partition() == 0

    assert cfg.get_clockwork_tradings_delay_secs() == 60

    assert cfg.get_clockwork_snapshot_delay_secs() == 600

    assert cfg.get_snapshot_output_dir() == '/tmp'

    assert cfg.get_stopwatch_filename() == '/tmp/oev8-stopwatch-test.log'

    assert cfg.get_stopwatch_max_mbytes() == 50

    assert cfg.get_stopwatch_backup_count() == 123


def test_env_server_host(all_ok_config):
    with EnvOverride('OEV8_SERVER_HOST', '1.2.3.4'):
        assert all_ok_config.get_server_host() == '1.2.3.4'


def test_env_server_port(all_ok_config):
    with EnvOverride('OEV8_SERVER_PORT', '1818'):
        assert all_ok_config.get_server_port() == 1818


def test_env_server_request_timeout_secs(all_ok_config):
    with EnvOverride('OEV8_SERVER_REQUEST_TIMEOUT_SECS', '1800'):
        assert all_ok_config.get_server_request_timeout_secs() == 1800


def test_env_server_read_timeout_secs(all_ok_config):
    with EnvOverride('OEV8_SERVER_READ_TIMEOUT_SECS', '1919'):
        assert all_ok_config.get_server_read_timeout_secs() == 1919


def test_env_event_writer_kafka_topic(all_ok_config):
    with EnvOverride('OEV8_EVENT_WRITER_KAFKA_TOPIC', 'some-events'):
        assert all_ok_config.get_event_writer_kafka_topic() == 'some-events'


def test_env_EVENT_WRITER_KAFKA_BOOTSTRAP_SERVER(all_ok_config):
    with EnvOverride('OEV8_EVENT_WRITER_KAFKA_BOOTSTRAP_SERVER',
                     'remotehost'):
        assert all_ok_config.get_event_writer_kafka_bootstrap_server() == \
            ['remotehost']


def test_env_event_writer_kafka_client_id(all_ok_config):
    with EnvOverride('OEV8_EVENT_WRITER_KAFKA_CLIENT_ID', 'CLI-ID'):
        assert all_ok_config.get_event_writer_kafka_client_id() == 'CLI-ID'


def test_env_event_writer_kafka_batch_size(all_ok_config):
    with EnvOverride('OEV8_EVENT_WRITER_KAFKA_BATCH_SIZE', '789'):
        assert all_ok_config.get_event_writer_kafka_batch_size() == 789


def test_env_journal_writer_kafka_topic(all_ok_config):
    with EnvOverride('OEV8_JOURNAL_WRITER_KAFKA_TOPIC', 'a-j-topic'):
        assert all_ok_config.get_journal_writer_kafka_topic() == 'a-j-topic'


def test_env_journal_writer_kafka_bootstrap_server(all_ok_config):
    # NOTE a few spaces
    with EnvOverride('OEV8_JOURNAL_WRITER_KAFKA_BOOTSTRAP_SERVER',
                     ' kafka-remote,a,  b , c'):
        assert all_ok_config.get_journal_writer_kafka_bootstrap_server() == \
            ['kafka-remote', 'a', 'b', 'c']


def test_env_journal_writer_kafka_client_id(all_ok_config):
    with EnvOverride('OEV8_JOURNAL_WRITER_KAFKA_CLIENT_ID', 'JCLI-ID'):
        assert all_ok_config.get_journal_writer_kafka_client_id() == 'JCLI-ID'


def test_env_journal_reader_kafka_client_id(all_ok_config):
    with EnvOverride('OEV8_JOURNAL_READER_KAFKA_CLIENT_ID', 'JRCLI-ID'):
        assert all_ok_config.get_journal_reader_kafka_client_id() == 'JRCLI-ID'


def test_env_journal_reader_kafka_group_id(all_ok_config):
    with EnvOverride('OEV8_JOURNAL_READER_KAFKA_GROUP_ID', 'JRGRP-ID'):
        assert all_ok_config.get_journal_reader_kafka_group_id() == 'JRGRP-ID'


def test_env_journal_reader_kafka_partition(all_ok_config):
    with EnvOverride('OEV8_JOURNAL_READER_KAFKA_PARTITION', '18'):
        assert all_ok_config.get_journal_reader_kafka_partition() == 18


def test_env_clockwork_tradings_delay_secs(all_ok_config):
    with EnvOverride('OEV8_CLOCKWORK_TRADINGS_DELAY_SECS', '12345'):
        assert all_ok_config.get_clockwork_tradings_delay_secs() == 12345


def test_env_clockwork_snapshot_delay_secs(all_ok_config):
    with EnvOverride('OEV8_CLOCKWORK_SNAPSHOT_DELAY_SECS', '54321'):
        assert all_ok_config.get_clockwork_snapshot_delay_secs() == 54321


def test_env_snapshot_output_dir(all_ok_config):
    with EnvOverride('OEV8_SNAPSHOT_OUTPUT_DIR', '/var/db/oev8'):
        assert all_ok_config.get_snapshot_output_dir() == '/var/db/oev8'


def test_env_stopwatch_filename(all_ok_config):
    with EnvOverride('OEV8_STOPWATCH_FILENAME', 'foo'):
        assert all_ok_config.get_stopwatch_filename() == 'foo'


def test_env_stopwatch_max_mbytes(all_ok_config):
    with EnvOverride('OEV8_STOPWATCH_MAX_MBYTES', '789'):
        assert all_ok_config.get_stopwatch_max_mbytes() == 789


def test_env_stopwatch_backup_count(all_ok_config):
    with EnvOverride('OEV8_STOPWATCH_BACKUP_COUNT', '111'):
        assert all_ok_config.get_stopwatch_backup_count() == 111
