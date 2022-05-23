import json
import struct
import uuid
from abc import ABC, abstractmethod
from unittest import TestCase

import aiokafka  # type:ignore
import kafka  # type:ignore
import kafka.admin  # type:ignore

from oev8.kafka.replay import replay
from oev8.journal.bytes import BytesJournalRecords
from oev8_pb2 import OEV8_EVT_CAUSE_NONE, OEV8_EVT_SNAPSHOT, Oev8_Event \
    # type:ignore


class ListCollector:
    def __init__(self):
        self.coll = []

    def __call__(self, arg):
        self.coll.append(arg)


class KafkaMessageSerDeser:
    @staticmethod
    def produce_msg(seq_num) -> bytes:
        pass

    @staticmethod
    def parse_msg(raw_msg):
        pass

    @staticmethod
    def seq_num_of(msg):
        pass


class JsonKafkaMessageSerDeser(KafkaMessageSerDeser):
    @staticmethod
    def produce_msg(seq_num) -> bytes:
        body = json.dumps({
            'Seq': seq_num,
        })
        return body.encode('utf8')

    @staticmethod
    def parse_msg(raw_msg):
        return json.loads(raw_msg.value)

    @staticmethod
    def seq_num_of(msg):
        return msg['Seq']


class ProtobufEventKafkaMessageSerDeser(KafkaMessageSerDeser):
    @staticmethod
    def produce_msg(seq_num) -> bytes:
        evt = Oev8_Event()
        evt.evt_type = OEV8_EVT_SNAPSHOT
        evt.evt_cause_type = OEV8_EVT_CAUSE_NONE
        evt.seq_num = seq_num
        return evt.SerializeToString()

    @staticmethod
    def parse_msg(raw_msg):
        evt = Oev8_Event()
        evt.ParseFromString(raw_msg.value)
        return evt

    @staticmethod
    def seq_num_of(msg):
        return int(msg.seq_num)


class JournalKafkaMessageSerDeser(KafkaMessageSerDeser):
    @staticmethod
    def produce_msg(seq_num) -> bytes:
        pass

    @staticmethod
    def parse_msg(raw_msg):
        unpacked = BytesJournalRecords.unpack_or_error(raw_msg.value)

        return {
            'Seq': unpacked.seq_num,
            'BodyLen': unpacked.body_bs_len,
            'Checksum': unpacked.body_bs_xxh64,
            'Body': unpacked.body_bs,
        }

    @staticmethod
    def seq_num_of(msg):
        return msg['Seq']


class KafkaIntegrationTestBase(ABC, TestCase):
    @abstractmethod
    def topic_name_pattern(self) -> str:
        pass

    @abstractmethod
    def kafka_bootstrap_server(self) -> str:
        pass

    def topic_partition(self):
        return kafka.TopicPartition(self.topic_name, 0)

    def num_partitions(self):
        return 1

    def replication_factor(self):
        return 1

    def create_topic(self):
        # CREATE TOPIC
        admin = kafka.KafkaAdminClient(
            bootstrap_servers=self.kafka_bootstrap_server())

        admin.create_topics([
            kafka.admin.NewTopic(
                name=self.topic_name,
                num_partitions=self.num_partitions(),
                replication_factor=self.replication_factor()),
        ])

        admin.close()

    def delete_topic(self):
        # DELETE TOPIC
        admin = kafka.KafkaAdminClient(
            bootstrap_servers=self.kafka_bootstrap_server())

        admin.delete_topics([self.topic_name])

        admin.close()

    def setUp(self):
        self.topic_name = 't-{}-{}'.format(
            self.topic_name_pattern(), uuid.uuid1())
        self.client_id = 'client-' + self.topic_name
        self.group_id = 'group-' + self.topic_name

        self.create_topic()

    def tearDown(self):
        self.delete_topic()

    def make_consumer(self):
        consumer = kafka.KafkaConsumer(
            bootstrap_servers=self.kafka_bootstrap_server(),
            group_id=self.group_id,
            client_id=self.client_id
        )

        consumer.assign([self.topic_partition()])

        return consumer

    def make_producer(self):
        return kafka.KafkaProducer(
            bootstrap_servers=self.kafka_bootstrap_server())

    def make_aio_producer(self, event_loop):
        return aiokafka.AIOKafkaProducer(
            bootstrap_servers=self.kafka_bootstrap_server(),
            loop=event_loop)

    def produce_seqs(
            self, producer, seq,
            msg_serdeser_klass
    ):
        for i in seq:
            producer.send(self.topic_name,
                          msg_serdeser_klass.produce_msg(i))
        producer.flush()

    def replay(
            self, consumer, from_seq,
            replayer_fn, msg_serdeser_klass
    ):
        (replayed, poll_count,) = replay(
            consumer, self.topic_partition(), from_seq,
            msg_transformer=msg_serdeser_klass.parse_msg,
            msg_seq_extractor=msg_serdeser_klass.seq_num_of,
            msg_replayer=replayer_fn
        )

        return (replayed, poll_count,)
