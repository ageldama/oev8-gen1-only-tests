from collections import namedtuple
from unittest.mock import Mock
from pytest import mark  # type:ignore
from oev8.asyncio import Awaiter
from oev8.svcs.event_writer.aiokafka import AioKafkaEventSender


AioKafkaEventSenderFixture = \
    namedtuple('AioKafkaEventSenderFixture',
               ['event_sender', 'awaiter', 'topic'])


def make_aio_kafka_event_sender_fixture(
        aio_kafka_producer_mock,
        event_loop,
        batch_size=10
):
    topic = 'topic-name'

    awaiter = Awaiter(event_loop)

    event_sender = AioKafkaEventSender(
        aio_kafka_producer=aio_kafka_producer_mock,
        topic=topic,
        awaiter=awaiter,
        batch_size=batch_size)

    return AioKafkaEventSenderFixture(
        topic=topic, event_sender=event_sender, awaiter=awaiter)


@mark.asyncio
async def test_aio_kafka_event_sender__ok_zero_events(
        event_loop,
        aio_kafka_producer_mock
):
    # record mock: aio_kafka_producer_mock
    aio_kafka_producer_mock.create_batch = Mock()

    # create subject
    fixture = make_aio_kafka_event_sender_fixture(
        aio_kafka_producer_mock, event_loop)

    event_sender = fixture.event_sender
    awaiter = fixture.awaiter

    # do it.
    assert event_sender.enabled

    event_sender.flush()

    await awaiter.gather_queue()

    # verify mock: aio_kafka_producer_mock
    aio_kafka_producer_mock.create_batch.assert_not_called()
    aio_kafka_producer_mock.send_batch.assert_not_awaited()


@mark.asyncio
async def test_aio_kafka_event_sender__ok_one_event(
        event_loop,
        aio_kafka_producer_mock
):
    # record mock: aio_kafka_producer_mock
    aio_kafka_producer_mock.create_batch = Mock()

    # create subject
    fixture = make_aio_kafka_event_sender_fixture(
        aio_kafka_producer_mock, event_loop)

    event_sender = fixture.event_sender
    awaiter = fixture.awaiter

    # do it.
    assert event_sender.enabled

    event_sender.send(b'a')
    event_sender.flush()

    await awaiter.gather_queue()

    # verify mock: aio_kafka_producer_mock
    aio_kafka_producer_mock.create_batch.assert_called_once()
    aio_kafka_producer_mock.send_batch.assert_awaited_once()


@mark.asyncio
async def test_aio_kafka_event_sender__disabled_one_event(
        event_loop,
        aio_kafka_producer_mock
):
    # record mock: aio_kafka_producer_mock
    aio_kafka_producer_mock.create_batch = Mock()

    # create subject
    fixture = make_aio_kafka_event_sender_fixture(
        aio_kafka_producer_mock, event_loop)

    event_sender = fixture.event_sender
    awaiter = fixture.awaiter

    # do it.
    event_sender.disable()
    assert not event_sender.enabled

    event_sender.send(b'a')
    event_sender.flush()

    await awaiter.gather_queue()

    # verify mock: aio_kafka_producer_mock
    aio_kafka_producer_mock.create_batch.assert_not_called()
    aio_kafka_producer_mock.send_batch.assert_not_awaited()


@mark.asyncio
async def test_aio_kafka_event_sender__ok_multiple_batches(
        event_loop,
        aio_kafka_producer_mock
):
    # record mock: aio_kafka_producer_mock
    aio_kafka_producer_mock.create_batch = Mock()

    # create subject
    fixture = make_aio_kafka_event_sender_fixture(
        aio_kafka_producer_mock, event_loop, batch_size=3)

    event_sender = fixture.event_sender
    awaiter = fixture.awaiter

    # do it.
    assert event_sender.enabled

    event_sender.send(b'a')
    event_sender.send(b'b')
    event_sender.send(b'c')
    event_sender.send(b'd')

    event_sender.flush()

    await awaiter.gather_queue()

    # verify mock: aio_kafka_producer_mock
    assert aio_kafka_producer_mock.create_batch.call_count == 2
    assert aio_kafka_producer_mock.send_batch.await_count == 2


@mark.asyncio
async def test_aio_kafka_event_sender__ok_multiple_batches_multiple_flushes(
        event_loop,
        aio_kafka_producer_mock
):
    # record mock: aio_kafka_producer_mock
    aio_kafka_producer_mock.create_batch = Mock()

    # create subject
    fixture = make_aio_kafka_event_sender_fixture(
        aio_kafka_producer_mock, event_loop, batch_size=3)

    event_sender = fixture.event_sender
    awaiter = fixture.awaiter

    # do it.
    assert event_sender.enabled

    event_sender.send(b'a')
    event_sender.send(b'b')
    event_sender.send(b'c')
    event_sender.send(b'd')
    event_sender.flush()

    event_sender.send(b'e')
    event_sender.send(b'b')
    event_sender.flush()

    await awaiter.gather_queue()

    # verify mock: aio_kafka_producer_mock
    assert aio_kafka_producer_mock.create_batch.call_count == 3
    assert aio_kafka_producer_mock.send_batch.await_count == 3
