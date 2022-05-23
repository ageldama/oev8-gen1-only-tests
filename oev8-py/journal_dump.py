from typing import Optional
import argparse
import logging
import kafka  # type:ignore
from termcolor import cprint  # type:ignore
from oev8.configs import Config
from oev8.svcs.journal.kafka import to_journal_record
from oev8_pb2 import Oev8_CommandRequest


logger = logging.getLogger('journal_dump')


def main(config_fn: str,
         nocolor: bool = False,
         offset: Optional[int] = None,
         limit: Optional[int] = None):
    config = Config()

    logger.info("LOADING CONFIG FROM: %s", config_fn)
    config.read_file(config_fn)

    logger.info("LOADED CONFIG: %s", config.dump())

    config.check()

    #
    server_addr = config.get_journal_writer_kafka_bootstrap_server()
    topic = config.get_journal_writer_kafka_topic()
    partition = config.get_journal_reader_kafka_partition()
    topic_partition = kafka.TopicPartition(topic, partition)
    client_id = config.get_journal_reader_kafka_client_id()
    group_id = config.get_journal_reader_kafka_group_id()

    consumer = kafka.KafkaConsumer(
        bootstrap_servers=server_addr,
        group_id=group_id,
        client_id=client_id)

    consumer.assign([topic_partition])

    if offset is None:
        consumer.seek_to_beginning()
        consumer.assign([topic_partition])
    else:
        consumer.seek(topic_partition, offset)
        consumer.assign([topic_partition])

    end_offsets = consumer.end_offsets([topic_partition])
    end_offset = end_offsets[topic_partition]
    if nocolor:
        print(f'End offset: {end_offset}')
    else:
        cprint(f'End offset: {end_offset}', color='cyan')
    print()

    if offset is not None and end_offset <= offset:
        return

    count = 0

    while True:
        msgs = consumer.poll()
        if len(msgs) > 0:
            for msg_list in msgs.values():
                for msg in msg_list:
                    if nocolor:
                        print(msg)
                        print()
                        print(msg.value.hex())
                        print()
                    else:
                        cprint(msg, color='blue')
                        print()
                        cprint(msg.value.hex(), color='blue')
                        print()

                    journal_record = to_journal_record(msg.value)
                    if nocolor:
                        print(f'seq_num: {journal_record.seq_num}')
                    else:
                        cprint(f'seq_num: {journal_record.seq_num}', color='red')
                    print()

                    try:
                        req = Oev8_CommandRequest()
                        req.ParseFromString(journal_record.body)

                        if nocolor:
                            print(req)
                            print('-' * 70)
                        else:
                            cprint(req, color='green')
                            cprint('-' * 70, color='white')
                    except:
                        logger.warning('ParseFromString FAIL',
                                       exc_info=True)

                    count = count + 1
                    if limit is not None and count >= limit:
                        return

                    if int(msg.offset + 1) >= int(end_offset):
                        return


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', type=str)
    parser.add_argument('-o', '--offset', type=int, required=False)
    parser.add_argument('-l', '--limit', type=int, required=False)

    parser.add_argument('-bw', '--nocolor', dest='nocolor',
                        action='store_true')
    parser.set_defaults(nocolor=False)

    args = parser.parse_args()

    # print(args)

    main(args.config_file, offset=args.offset, limit=args.limit,
         nocolor=args.nocolor)
