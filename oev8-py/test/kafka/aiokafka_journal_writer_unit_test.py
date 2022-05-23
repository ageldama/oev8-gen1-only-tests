from unittest.mock import call
from pytest import mark  # type:ignore
from xxhash import xxh64_intdigest  # type:ignore
from oev8.asyncio import Awaiter
from oev8.svcs.journal.aiokafka import AioKafkaJournalWriter
from oev8.journal.bytes import BytesJournalRecords


@mark.asyncio
async def test_aio_kafka_journal_writer__enabled(
        event_loop,
        aio_kafka_producer_mock,
        null_logging_stopwatch
):
    # consts
    topic = 'topic-name'
    seq_num = 123
    journal_bytes = b'1234567890'
    checksum = xxh64_intdigest(journal_bytes)

    # record mock: aio_kafka_producer_mock

    # create subject
    awaiter = Awaiter(event_loop)

    journal_writer = AioKafkaJournalWriter(
        aio_kafka_producer=aio_kafka_producer_mock,
        topic=topic,
        awaiter=awaiter,
        logging_stopwatch=null_logging_stopwatch)

    # do it.
    assert journal_writer.enabled

    journal_writer.write(seq_num=seq_num,
                         byte_len=len(journal_bytes),
                         checksum=checksum,
                         byte_seq=journal_bytes)

    await awaiter.gather_queue()

    # verify mock: aio_kafka_producer_mock
    expecting_byte_seq = BytesJournalRecords.pack(seq_num, journal_bytes)[1]

    aio_kafka_producer_mock.send_and_wait.assert_has_awaits([
        call(topic, expecting_byte_seq)
    ])


@mark.asyncio
async def test_aio_kafka_journal_writer__disabled(
        event_loop,
        aio_kafka_producer_mock,
        null_logging_stopwatch
):
    # consts
    topic = 'topic-name'
    seq_num = 123
    journal_bytes = b'1234567890'
    checksum = xxh64_intdigest(journal_bytes)

    # record mock: aio_kafka_producer_mock

    # create subject
    awaiter = Awaiter(event_loop)

    journal_writer = AioKafkaJournalWriter(
        aio_kafka_producer=aio_kafka_producer_mock,
        topic=topic,
        awaiter=awaiter,
        logging_stopwatch=null_logging_stopwatch)

    # do it.
    journal_writer.disable()
    assert not journal_writer.enabled

    journal_writer.write(seq_num=seq_num,
                         byte_len=len(journal_bytes),
                         checksum=checksum,
                         byte_seq=journal_bytes)

    await awaiter.gather_queue()

    # verify mock: aio_kafka_producer_mock
    aio_kafka_producer_mock.send_and_wait.assert_not_awaited()
