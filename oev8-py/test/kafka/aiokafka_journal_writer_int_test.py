import asyncio
from pytest import mark  # type:ignore
from xxhash import xxh64_intdigest  # type:ignore
from oev8.asyncio import Awaiter
from oev8.svcs.journal.aiokafka import AioKafkaJournalWriter
from test.testsup.kafka import \
    KafkaIntegrationTestBase, JournalKafkaMessageSerDeser, ListCollector
from test.conftest import get_test_config
from test.testsup import make_null_logging_stopwatch


@mark.int
class AioKafkaJournalWriter_IntTestCase(KafkaIntegrationTestBase):
    def topic_name_pattern(self) -> str:
        return 'journal-writer'

    def kafka_bootstrap_server(self) -> str:
        return get_test_config().\
            get_event_writer_kafka_bootstrap_server()

    def test_enabled_ok(self):
        async def my_asyncfn():
            logging_stopwatch = make_null_logging_stopwatch()

            event_loop = asyncio.get_event_loop()
            assert event_loop is not None

            producer = self.make_aio_producer(event_loop)
            await producer.start()

            awaiter = Awaiter(event_loop)

            journal_writer = AioKafkaJournalWriter(
                producer, self.topic_name,
                awaiter, logging_stopwatch)

            assert journal_writer.enabled

            # produce some msgs.
            for i in range(1, 10+1):
                bs = ('{}'.format(i)).encode('utf8')
                journal_writer.write(i, len(bs), xxh64_intdigest(bs), bs)

            await awaiter.gather_queue()

            # CHECK: replay
            collector = ListCollector()
            consumer = self.make_consumer()

            (replayed, _,) = self.replay(
                consumer, 2, collector, JournalKafkaMessageSerDeser)

            assert replayed

            # CHECK: collector
            assert [i['Seq'] for i in collector.coll] == list(range(2, 10+1))

            # CHECK: logging_stopwatch
            logging_stopwatch.__enter__.assert_called()
            logging_stopwatch.__exit__.assert_called()

        #
        asyncio.run(my_asyncfn())

    def test_disabled_ok(self):
        async def my_asyncfn():
            logging_stopwatch = make_null_logging_stopwatch()

            event_loop = asyncio.get_event_loop()
            assert event_loop is not None

            producer = self.make_aio_producer(event_loop)
            await producer.start()

            awaiter = Awaiter(event_loop)

            journal_writer = AioKafkaJournalWriter(
                producer, self.topic_name,
                awaiter, logging_stopwatch)

            journal_writer.disable()
            assert not journal_writer.enabled

            # produce some msgs.
            for i in range(1, 10+1):
                bs = ('{}'.format(i)).encode('utf8')
                journal_writer.write(i, len(bs), xxh64_intdigest(bs), bs)

            await awaiter.gather_queue()

            # CHECK: replay
            collector = ListCollector()
            consumer = self.make_consumer()

            (replayed, _,) = self.replay(
                consumer, 2, collector, JournalKafkaMessageSerDeser)

            assert not replayed

            # CHECK: collector
            assert [i['Seq'] for i in collector.coll] == []

            # CHECK: logging_stopwatch
            logging_stopwatch.__enter__.assert_called()
            logging_stopwatch.__exit__.assert_called()

        #
        asyncio.run(my_asyncfn())
