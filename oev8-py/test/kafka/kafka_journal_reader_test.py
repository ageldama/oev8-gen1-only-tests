from abc import ABC
from collections import namedtuple
from unittest import TestCase
from unittest.mock import Mock, call, ANY
import functools
import struct
import kafka  # type:ignore
from pytest import raises  # type:ignore
from oev8.journal.bytes import BytesJournalRecords
from oev8.svcs.journal import JournalWriterFail
from oev8.svcs.journal.kafka import KafkaJournalReader


FakeConsumerMessage = namedtuple('FakeConsumerMessage',
                                 ['value'])


def make_journal_bytes(bs, seq_num) -> bytes:
    return BytesJournalRecords.pack(seq_num, bs)[1]


def my_replay(
        msgs,
        kafka_consumer,
        topic_partition,
        seq_num,
        msg_transformer,
        msg_seq_extractor,
        msg_replayer):
    cnt = 0
    for msg in msgs:
        msg2 = msg_transformer(FakeConsumerMessage(value=msg))
        seq = msg_seq_extractor(msg2)
        if seq >= seq_num:
            msg_replayer(msg2)
            cnt = cnt + 1
    return (cnt > 0, cnt,)


class KafkaJournalReaderTestBase(ABC, TestCase):
    def setUp(self):
        self.server_addr = 'SERVER'
        self.topic = 'TOPIC'
        self.partition = 42
        self.client_id = 'CLIENT-ID'
        self.group_id = 'GROUP-ID'

        self.seq_num = 123

        # mocks
        self.msgs = self.build_msgs()
        self.build_default_mocks()
        self.config_mocks()

        self.journal_reader = KafkaJournalReader(
            kafka_server_addr=self.server_addr,
            topic_partition=kafka.TopicPartition(
                self.topic, self.partition),
            group_id=self.group_id,
            client_id=self.client_id,
            cmd_handler=self.cmd_handler_mock,
            kafka_consumer_factory=self.consumer_factory,
            replay_fn=self.replay_mock)

    def get_consumer_mock(self, *args, **kws):
        return self.consumer_mock

    def build_default_mocks(self):
        self.consumer_mock = Mock()
        self.consumer_factory = Mock(
            side_effect=self.get_consumer_mock)

        self.cmd_handler_mock = Mock()

        self.replay_mock = Mock(
            side_effect=functools.partial(my_replay, self.msgs))

    def config_mocks(self):
        'configure mocks here'

    def build_msgs(self):
        return []


class EverythingsOk_KafkaJournalReaderTest(KafkaJournalReaderTestBase):
    def build_msgs(self):
        return [
            make_journal_bytes(b'123', 123),
            make_journal_bytes(b'4567', 124),
        ]

    def test_okokok(self):
        'replay N개 (OK).'

        (replayed, replay_count,) = self.journal_reader.read(self.seq_num)

        assert replayed
        assert replay_count == 2

        # VERIFY: consumer_mock
        self.consumer_mock.assign.assert_has_calls([
            call([kafka.TopicPartition(self.topic, self.partition)])
        ])

        self.consumer_mock.close.assert_called_once()

        # VERIFY: replay_mock
        self.replay_mock.assert_has_calls([
            call(
                self.consumer_mock,
                kafka.TopicPartition(self.topic, self.partition),
                self.seq_num,
                msg_transformer=ANY,
                msg_seq_extractor=ANY,
                msg_replayer=ANY
            )
        ])

        # VERIFY: cmd_handler_mock
        self.cmd_handler_mock.handle.assert_has_calls([
            call(3, ANY, b'123', replaying=True),
            call(4, ANY, b'4567', replaying=True),
        ])


class NoRecord__KafkaJournalReaderTest(KafkaJournalReaderTestBase):
    def build_msgs(self):
        return []

    def test_with_empty_msgs(self):
        (replayed, replay_count,) = self.journal_reader.read(self.seq_num)

        assert not replayed
        assert replay_count == 0

        # VERIFY: cmd_handler_mock
        self.cmd_handler_mock.handle.assert_not_called()


class WithException__KafkaJournalReaderTest(KafkaJournalReaderTestBase):
    'replay시 에러 발생: assert 실패. (checksum 등)'

    def build_msgs(self):
        return []

    def config_mocks(self):
        def fail_assert(*args, **kwargs):
            assert False, 'Example failing assertion.'

        self.replay_mock = Mock(side_effect=fail_assert)

    def test_with_an_exception(self):
        with raises(JournalWriterFail):
            self.journal_reader.read(self.seq_num)

        # VERIFY: cmd_handler_mock
        self.cmd_handler_mock.handle.assert_not_called()


class MismatchingSeq__KafkaJournalReaderTest(KafkaJournalReaderTestBase):
    def build_msgs(self):
        return [
            make_journal_bytes(b'123', 123),
            make_journal_bytes(b'4567', 124),
        ]

    def test_lt(self):
        (replayed, replay_count,) = self.journal_reader.read(13)

        assert replayed
        assert replay_count == 2

        # VERIFY: cmd_handler_mock
        self.cmd_handler_mock.handle.assert_has_calls([
            call(3, ANY, b'123', replaying=True),
            call(4, ANY, b'4567', replaying=True),
        ])

    def test_gt(self):
        (replayed, replay_count,) = self.journal_reader.read(9999)

        assert not replayed
        assert replay_count == 0

        self.cmd_handler_mock.handle.assert_not_called()


class SeqNumWrongChecksum__KafkaJournalReaderTest(KafkaJournalReaderTestBase):
    def build_msgs(self):
        msgs = [
            make_journal_bytes(b'123', 123),
            make_journal_bytes(b'4567', 124),
        ]

        for i, msg in enumerate(msgs):
            ba = bytearray(msg)
            # (seq_num_bs=32, seq_num_xxh64=8, body_len=2, body_xxh64=8)
            #  *** => (_ ^ _)
            ba[0] = ba[0] ^ 0xff
            msgs[i] = bytes(ba)

        return msgs

    def test_01(self):
        with raises(JournalWriterFail):
            self.journal_reader.read(self.seq_num)

        self.cmd_handler_mock.handle.assert_not_called()


class BodyWrongChecksum__KafkaJournalReaderTest(KafkaJournalReaderTestBase):
    def build_msgs(self):
        msgs = [
            make_journal_bytes(b'123', 123),
            make_journal_bytes(b'4567', 124),
        ]

        for i, msg in enumerate(msgs):
            ba = bytearray(msg)
            # (seq_num_bs=32, seq_num_xxh64=8, body_len=2, body_xxh64=8)
            #                                              *** => (_ ^ _)
            ba[32+8+2] = ba[32+8+2] ^ 0xff
            msgs[i] = bytes(ba)

        return msgs

    def test_01(self):
        with raises(JournalWriterFail):
            self.journal_reader.read(self.seq_num)

        self.cmd_handler_mock.handle.assert_not_called()


class BodyLenOverflow__KafkaJournalReaderTest(KafkaJournalReaderTestBase):
    def build_msgs(self):
        msgs = [
            make_journal_bytes(b'123', 123),
            make_journal_bytes(b'4567', 124),
        ]

        for i, msg in enumerate(msgs):
            ba = bytearray(msg)
            # (seq_num_bs=32, seq_num_xxh64=8, body_len=2, body_xxh64=8)
            #                                  *** => 100
            ba[32+8:32+8+2] = struct.pack('!H', 100)
            msgs[i] = bytes(ba)

        return msgs

    def test_01(self):
        with raises(JournalWriterFail):
            self.journal_reader.read(self.seq_num)

        self.cmd_handler_mock.handle.assert_not_called()


class BodyLenUnderflow__KafkaJournalReaderTest(KafkaJournalReaderTestBase):
    def build_msgs(self):
        msgs = [
            make_journal_bytes(b'123', 123),
            make_journal_bytes(b'4567', 124),
        ]

        for i, msg in enumerate(msgs):
            ba = bytearray(msg)
            # (seq_num_bs=32, seq_num_xxh64=8, body_len=2, body_xxh64=8)
            #                                  *** => 1
            ba[32+8:32+8+2] = struct.pack('!H', 1)
            msgs[i] = bytes(ba)

        return msgs

    def test_01(self):
        with raises(JournalWriterFail):
            self.journal_reader.read(self.seq_num)

        self.cmd_handler_mock.handle.assert_not_called()
