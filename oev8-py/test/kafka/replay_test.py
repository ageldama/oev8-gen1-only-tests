from collections import namedtuple
import os
import uuid
import json
import logging
import pytest  # type:ignore
from pytest import mark  # type:ignore
import kafka  # type:ignore
import kafka.admin  # type:ignore
import kafka.errors  # type:ignore
from kafka.errors import KafkaError  # type:ignore
from oev8.kafka.replay import replay
from test.testsup.kafka import \
    KafkaIntegrationTestBase, JsonKafkaMessageSerDeser, \
    ListCollector
from test.conftest import get_test_config


@mark.slow
@mark.int
class EverythingsOk_KafkaReplayTest(KafkaIntegrationTestBase):
    def kafka_bootstrap_server(self) -> str:
        return get_test_config().\
            get_event_writer_kafka_bootstrap_server()

    def topic_name_pattern(self) -> str:
        return 'replay'

    def test_01(self):
        # produce some msgs.
        producer = self.make_producer()

        self.produce_seqs(
            producer, range(1, 100+1), JsonKafkaMessageSerDeser)

        producer.flush()

        # CHECK: replay
        collector = ListCollector()
        consumer = self.make_consumer()

        (replayed, poll_count,) = self.replay(
            consumer, 13, collector, JsonKafkaMessageSerDeser)

        assert replayed
        assert poll_count > 1

        # CHECK: collector
        assert [i['Seq'] for i in collector.coll] == list(range(13, 100+1))


@mark.int
class AskLt_KafkaReplayTest(KafkaIntegrationTestBase):
    def kafka_bootstrap_server(self) -> str:
        return get_test_config().\
            get_event_writer_kafka_bootstrap_server()

    def topic_name_pattern(self) -> str:
        return 'replay'

    def test_01(self):
        # produce some msgs.
        producer = self.make_producer()

        self.produce_seqs(
            producer, range(10, 20), JsonKafkaMessageSerDeser)

        producer.flush()

        # CHECK: replay
        collector = ListCollector()
        consumer = self.make_consumer()

        (replayed, _,) = self.replay(
            consumer, 7, collector, JsonKafkaMessageSerDeser)

        assert not replayed

        # CHECK: collector
        assert collector.coll == []


@mark.int
class AskGt_WithoutRecord_KafkaReplayTest(KafkaIntegrationTestBase):
    def kafka_bootstrap_server(self) -> str:
        return get_test_config().\
            get_event_writer_kafka_bootstrap_server()

    def topic_name_pattern(self) -> str:
        return 'replay'

    def test_01(self):
        # produce some msgs.
        producer = self.make_producer()

        self.produce_seqs(
            producer,
            [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
            JsonKafkaMessageSerDeser)

        producer.flush()

        # CHECK: replay
        collector = ListCollector()
        consumer = self.make_consumer()

        (replayed, _,) = self.replay(
            consumer, 21, collector, JsonKafkaMessageSerDeser)

        assert replayed

        # CHECK: collector
        assert collector.coll == []


@mark.int
class AskGt_WithRecord_KafkaReplayTest(KafkaIntegrationTestBase):
    def kafka_bootstrap_server(self) -> str:
        return get_test_config().\
            get_event_writer_kafka_bootstrap_server()

    def topic_name_pattern(self) -> str:
        return 'replay'

    def test_01(self):
        # produce some msgs.
        producer = self.make_producer()

        self.produce_seqs(
            producer,
            [10, 12, 13],
            JsonKafkaMessageSerDeser)

        producer.flush()

        # CHECK: replay
        collector = ListCollector()
        consumer = self.make_consumer()

        # 11은 없지만, 그보다 큰 12, 13 있음.
        (replayed, _,) = self.replay(
            consumer, 11, collector, JsonKafkaMessageSerDeser)

        assert replayed

        # CHECK: collector
        assert collector.coll == [{'Seq': 12}, {'Seq': 13}]


@mark.int
class NotExistingTopic_KafkaReplayTest(KafkaIntegrationTestBase):
    def kafka_bootstrap_server(self) -> str:
        return get_test_config().\
            get_event_writer_kafka_bootstrap_server()

    def topic_name_pattern(self) -> str:
        return 'replay'

    def create_topic(self):
        pass  # Override to do nothing.

    def test_01(self):
        # produce some msgs.
        producer = self.make_producer()

        self.produce_seqs(
            producer, range(10, 20), JsonKafkaMessageSerDeser)

        producer.flush()

        # CHECK: replay
        collector = ListCollector()
        consumer = self.make_consumer()

        (replayed, _,) = self.replay(
            consumer, 13, collector, JsonKafkaMessageSerDeser)

        assert replayed

        # CHECK: collector
        assert [i['Seq'] for i in collector.coll] == list(range(13, 20))


@mark.int
class OnlyOneRecord_KafkaReplayTest(KafkaIntegrationTestBase):
    def kafka_bootstrap_server(self) -> str:
        return get_test_config().\
            get_event_writer_kafka_bootstrap_server()

    def topic_name_pattern(self) -> str:
        return 'replay'

    def test_01(self):
        # produce some msgs.
        producer = self.make_producer()

        self.produce_seqs(
            producer, range(10), JsonKafkaMessageSerDeser)

        producer.flush()

        # CHECK: replay
        collector = ListCollector()
        consumer = self.make_consumer()

        (replayed, _,) = self.replay(
            consumer, 0, collector, JsonKafkaMessageSerDeser)

        assert replayed

        # CHECK: collector
        assert [i['Seq'] for i in collector.coll] == list(range(10))


@mark.int
class EmptyTopic_KafkaReplayTest(KafkaIntegrationTestBase):
    def kafka_bootstrap_server(self) -> str:
        return get_test_config().\
            get_event_writer_kafka_bootstrap_server()

    def topic_name_pattern(self) -> str:
        return 'replay'

    def test_01(self):
        # NOT to produce some msgs.

        # CHECK: replay
        collector = ListCollector()
        consumer = self.make_consumer()

        (replayed, _,) = self.replay(
            consumer, 123, collector, JsonKafkaMessageSerDeser)

        assert not replayed

        # CHECK: collector
        assert collector.coll == []


@mark.int
class FirstRecord_KafkaReplayTest(KafkaIntegrationTestBase):
    def kafka_bootstrap_server(self) -> str:
        return get_test_config().\
            get_event_writer_kafka_bootstrap_server()

    def topic_name_pattern(self) -> str:
        return 'replay'

    def test_01(self):
        # produce some msgs.
        producer = self.make_producer()

        self.produce_seqs(
            producer, range(1, 10), JsonKafkaMessageSerDeser)

        producer.flush()

        # CHECK: replay
        collector = ListCollector()
        consumer = self.make_consumer()

        (replayed, poll_count,) = self.replay(
            consumer, 1, collector, JsonKafkaMessageSerDeser)

        assert replayed
        assert poll_count > 1

        # CHECK: collector
        assert [i['Seq'] for i in collector.coll] == list(range(1, 10))
