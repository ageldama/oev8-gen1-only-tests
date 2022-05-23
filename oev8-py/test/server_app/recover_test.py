from unittest.mock import Mock, call

from pytest import raises  # type:ignore

from oev8.typedefs import SeqType
from oev8.svcs.journal import JournalWriterFail
from oev8.svcs.snapshot import SnapshotFail
from server_app import recover


def test_recover__ok(recover_fixture):
    # do it
    recover(
        recover_fixture.config,
        recover_fixture.seq_num_service_mock,
        recover_fixture.snapshot_loading_service_mock,
        recover_fixture.journal_reader_mock
    )

    # verify mocks
    recover_fixture.seq_num_service_mock.cur_val.assert_has_calls([
        call(SeqType.CMD_REQ)])

    recover_fixture.snapshot_loading_service_mock.find_latest.assert_called_once()

    recover_fixture.snapshot_loading_service_mock.load.assert_has_calls([
        call(recover_fixture.found_snapshot_filename)])

    recover_fixture.journal_reader_mock.read.assert_has_calls([
        call(recover_fixture.last_seq_num+1)])


def test_recover__snapshot_find_latest_fail(recover_fixture):
    # record mocks
    recover_fixture.snapshot_loading_service_mock.find_latest = Mock(
        side_effect=SnapshotFail)

    # do it
    with raises(SnapshotFail):
        recover(
            recover_fixture.config,
            recover_fixture.seq_num_service_mock,
            recover_fixture.snapshot_loading_service_mock,
            recover_fixture.journal_reader_mock
        )


def test_recover__snapshot_load_fail(recover_fixture):
    # record mocks
    recover_fixture.snapshot_loading_service_mock.load = Mock(
        side_effect=SnapshotFail)

    # do it
    with raises(SnapshotFail):
        recover(
            recover_fixture.config,
            recover_fixture.seq_num_service_mock,
            recover_fixture.snapshot_loading_service_mock,
            recover_fixture.journal_reader_mock
        )


def test_recover__journal_read_fail(recover_fixture):
    # record mocks
    recover_fixture.journal_reader_mock.read = Mock(
        side_effect=JournalWriterFail)

    # do it
    with raises(JournalWriterFail):
        recover(
            recover_fixture.config,
            recover_fixture.seq_num_service_mock,
            recover_fixture.snapshot_loading_service_mock,
            recover_fixture.journal_reader_mock
        )
