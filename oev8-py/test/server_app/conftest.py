from collections import namedtuple
from unittest.mock import Mock
from pytest import fixture  # type:ignore

from oev8.configs import Config
from oev8.svcs.journal import JournalReader
from oev8.svcs.seq_num import SeqNumService
from oev8.svcs.snapshot import SnapshotLoadingService


RecoverFixture = namedtuple(
    'RecoverFixture',
    ['config',
     #
     'last_seq_num',
     'found_snapshot_filename',
     'replayed',
     'replay_count',
     #
     'seq_num_service_mock',
     'snapshot_loading_service_mock',
     'journal_reader_mock'])


@fixture
def recover_fixture():
    # consts
    last_seq_num = 42
    found_snapshot_filename = 'found-snapshot'
    replayed = True
    replay_count = 18

    # record mocks
    config = Mock(Config)
    config.get_snapshot_output_dir = Mock(return_value='some-dir')

    seq_num_service = Mock(SeqNumService)
    seq_num_service.cur_val = Mock(return_value=last_seq_num)

    snapshot_loading_service = Mock(SnapshotLoadingService)
    snapshot_loading_service.find_latest = Mock(
        return_value=found_snapshot_filename)
    snapshot_loading_service.load = Mock(return_value=True)

    journal_reader = Mock(JournalReader)
    journal_reader.read = Mock(return_value=(replayed, replay_count,))

    #
    return RecoverFixture(
        config=config,
        #
        last_seq_num=last_seq_num,
        found_snapshot_filename=found_snapshot_filename,
        replayed=replayed,
        replay_count=replay_count,
        #
        seq_num_service_mock=seq_num_service,
        snapshot_loading_service_mock=snapshot_loading_service,
        journal_reader_mock=journal_reader
    )
