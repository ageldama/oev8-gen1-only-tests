import asyncio
from pytest import mark  # type:ignore
from oev8.asyncio import Awaiter
from oev8.svcs.event_writer.aiokafka import AioKafkaEventSender
from test.testsup.kafka import \
    KafkaIntegrationTestBase, JsonKafkaMessageSerDeser, ListCollector
from test.conftest import get_test_config
from test.testsup import make_null_logging_stopwatch


@mark.int
class AioKafkaEventSender_IntTestCase(KafkaIntegrationTestBase):
    def topic_name_pattern(self) -> str:
        return 'event-sender'

    def kafka_bootstrap_server(self) -> str:
        return get_test_config().\
            get_event_writer_kafka_bootstrap_server()

    def __build(self, batch_size=10):
        event_loop = asyncio.get_event_loop()
        assert event_loop is not None

        producer = self.make_aio_producer(event_loop)

        awaiter = Awaiter(event_loop)

        event_sender = AioKafkaEventSender(
            producer, self.topic_name, awaiter,
            batch_size=batch_size)

        return (event_loop, producer, awaiter, event_sender,)

    def test_enabled_ok(self):
        async def my_asyncfn():
            (_, producer, awaiter, event_sender,) = \
                self.__build()

            await producer.start()

            assert event_sender.enabled

            # produce some msgs.
            for i in range(1, 10+1):
                bs = JsonKafkaMessageSerDeser.produce_msg(i)
                event_sender.send(bs)

            event_sender.flush()

            await awaiter.gather_queue()

            # CHECK: replay
            collector = ListCollector()
            consumer = self.make_consumer()

            (replayed, _,) = self.replay(
                consumer, 1, collector, JsonKafkaMessageSerDeser)

            assert replayed

            # CHECK: collector
            assert [i['Seq'] for i in collector.coll] == list(range(1, 10+1))

        #
        asyncio.run(my_asyncfn())

    def test_disabled(self):
        async def my_asyncfn():
            (_, producer, awaiter, event_sender,) = \
                self.__build()

            event_sender.disable()
            assert not event_sender.enabled

            await producer.start()

            # produce some msgs.
            for i in range(1, 10+1):
                bs = JsonKafkaMessageSerDeser.produce_msg(i)
                event_sender.send(bs)

            event_sender.flush()

            await awaiter.gather_queue()

            # CHECK: replay
            collector = ListCollector()
            consumer = self.make_consumer()

            (replayed, _,) = self.replay(
                consumer, 1, collector, JsonKafkaMessageSerDeser)

            assert not replayed

            # CHECK: collector
            assert [i['Seq'] for i in collector.coll] == []

        #
        asyncio.run(my_asyncfn())

    def test_ok_empty(self):
        async def my_asyncfn():
            (_, producer, awaiter, event_sender,) = \
                self.__build()

            assert event_sender.enabled

            await producer.start()

            # produce some msgs.
            event_sender.flush()

            await awaiter.gather_queue()

            # CHECK: replay
            collector = ListCollector()
            consumer = self.make_consumer()

            (replayed, _,) = self.replay(
                consumer, 1, collector, JsonKafkaMessageSerDeser)

            assert not replayed

            # CHECK: collector
            assert [i['Seq'] for i in collector.coll] == []

        #
        asyncio.run(my_asyncfn())

    def test_multiple_batch(self):
        async def my_asyncfn():
            (_, producer, awaiter, event_sender,) = \
                self.__build(batch_size=3)

            await producer.start()

            assert event_sender.enabled

            # produce some msgs.
            for i in range(1, 10+1):
                bs = JsonKafkaMessageSerDeser.produce_msg(i)
                event_sender.send(bs)

            event_sender.flush()

            await awaiter.gather_queue()

            # CHECK: replay
            collector = ListCollector()
            consumer = self.make_consumer()

            (replayed, _,) = self.replay(
                consumer, 1, collector, JsonKafkaMessageSerDeser)

            assert replayed

            # CHECK: collector
            assert [i['Seq'] for i in collector.coll] == list(range(1, 10+1))

        #
        asyncio.run(my_asyncfn())

    def test_in_a_batch(self):
        async def my_asyncfn():
            (_, producer, awaiter, event_sender,) = \
                self.__build(batch_size=10)

            await producer.start()

            assert event_sender.enabled

            # produce some msgs.
            for i in range(1, 5+1):
                bs = JsonKafkaMessageSerDeser.produce_msg(i)
                event_sender.send(bs)

            event_sender.flush()

            await awaiter.gather_queue()

            # CHECK: replay
            collector = ListCollector()
            consumer = self.make_consumer()

            (replayed, _,) = self.replay(
                consumer, 1, collector, JsonKafkaMessageSerDeser)

            assert replayed

            # CHECK: collector
            assert [i['Seq'] for i in collector.coll] == list(range(1, 5+1))

        #
        asyncio.run(my_asyncfn())

    def test_multiple_batch_multiple_times(self):
        async def my_asyncfn():
            (_, producer, awaiter, event_sender,) = \
                self.__build(batch_size=3)

            await producer.start()

            assert event_sender.enabled

            # produce some msgs.
            for i in range(1, 10+1):
                bs = JsonKafkaMessageSerDeser.produce_msg(i)
                event_sender.send(bs)

            event_sender.flush()

            await awaiter.gather_queue()

            for i in range(11, 20+1):
                bs = JsonKafkaMessageSerDeser.produce_msg(i)
                event_sender.send(bs)

            event_sender.flush()

            await awaiter.gather_queue()


            # CHECK: replay
            collector = ListCollector()
            consumer = self.make_consumer()

            (replayed, _,) = self.replay(
                consumer, 1, collector, JsonKafkaMessageSerDeser)

            assert replayed

            # CHECK: collector
            assert [i['Seq'] for i in collector.coll] == list(range(1, 20+1))

        #
        asyncio.run(my_asyncfn())
