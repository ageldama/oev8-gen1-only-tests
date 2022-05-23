import struct
import sys
import argparse
import logging
from datetime import datetime
from termcolor import cprint  # type:ignore
import xxhash  # type:ignore
from oev8_pb2 import Oev8_Event, Oev8_CommandRequest, Oev8_CommandResponse


logger = logging.getLogger('pb3_decode')


def parse_cmdreq(
        body_only: bool,
        nocolor: bool):
    # local defs.
    def parse_body(body):
        try:
            req = Oev8_CommandRequest()
            req.ParseFromString(body)

            if nocolor:
                print(f'body-len: {len(body)}')
                print(req)
            else:
                cprint(f'body-len: {len(body)}', color='green')
                cprint(req, color='green')
        except:
            logger.warning('ParseFromString FAIL',
                           exc_info=True)

    #
    bs = bytes.fromhex(sys.stdin.read().strip())

    if nocolor:
        print(f'len: {len(bs)}')
        print(bs.hex())
        print()
    else:
        cprint(f'len: {len(bs)}', color='blue')
        cprint(bs.hex(), color='blue')
        print()

    if body_only:
        parse_body(bs)
    else:
        (body_len, checksum, utc_secs,) = struct.unpack_from('!HQQ', bs)

        body = bs[18:]

        correct_len = len(body) == body_len
        correct_checksum = checksum == xxhash.xxh64_intdigest(body)

        msg_len = f'body_len (in header): {body_len} --> correct?={correct_len}'
        msg_checksum = f'body_checksum: {hex(checksum)} --> correct?={correct_checksum}'

        utc_dt = datetime.fromtimestamp(utc_secs)
        msg_dt = f'utc_secs: {utc_secs} == {utc_dt}'

        if nocolor:
            print(msg_len)
            print(msg_checksum)
            print(msg_dt)
        else:
            cprint(msg_len, color='cyan')
            cprint(msg_checksum, color='cyan')
            cprint(msg_dt, color='cyan')

        parse_body(body)


def parse_cmdresp(
        body_only: bool,
        nocolor: bool):
    # local defs.
    def parse_body(body):
        try:
            resp = Oev8_CommandResponse()
            resp.ParseFromString(body)

            if nocolor:
                print(f'body-len: {len(body)}')
                print(resp)
            else:
                cprint(f'body-len: {len(body)}', color='green')
                cprint(resp, color='green')
        except:
            logger.warning('ParseFromString FAIL',
                           exc_info=True)

    #
    bs = bytes.fromhex(sys.stdin.read().strip())

    if nocolor:
        print(f'len: {len(bs)}')
        print(bs.hex())
        print()
    else:
        cprint(f'len: {len(bs)}', color='blue')
        cprint(bs.hex(), color='blue')
        print()

    if body_only:
        parse_body(bs)
    else:
        (body_len, checksum,) = struct.unpack_from('!HQ', bs)

        body = bs[10:]

        correct_len = len(body) == body_len
        correct_checksum = checksum == xxhash.xxh64_intdigest(body)

        msg_len = f'body_len (in header): {body_len} --> correct?={correct_len}'
        msg_checksum = f'body_checksum: {hex(checksum)} --> correct?={correct_checksum}'

        if nocolor:
            print(msg_len)
            print(msg_checksum)
        else:
            cprint(msg_len, color='cyan')
            cprint(msg_checksum, color='cyan')

        parse_body(body)


def parse_event(
        nocolor: bool
):
    bs = bytes.fromhex(sys.stdin.read().strip())

    if nocolor:
        print(f'len: {len(bs)}')
        print(bs.hex())
        print()
    else:
        cprint(f'len: {len(bs)}', color='blue')
        cprint(bs.hex(), color='blue')
        print()

    try:
        evt = Oev8_Event()
        evt.ParseFromString(bs)

        if nocolor:
            print(evt)
        else:
            cprint(evt, color='green')
    except:
        logger.warning('ParseFromString FAIL',
                       exc_info=True)


def parse_journal(
        body_only: bool,
        nocolor: bool):
    # local defs.
    def parse_body(body):
        try:
            req = Oev8_CommandRequest()
            req.ParseFromString(body)

            if nocolor:
                print(f'body-len: {len(body)}')
                print(req)
            else:
                cprint(f'body-len: {len(body)}', color='green')
                cprint(req, color='green')
        except:
            logger.warning('ParseFromString FAIL',
                           exc_info=True)

    #
    bs = bytes.fromhex(sys.stdin.read().strip())

    if nocolor:
        print(f'whole-len: {len(bs)}')
        print(bs.hex())
        print()
    else:
        cprint(f'whole-len: {len(bs)}', color='blue')
        cprint(bs.hex(), color='blue')
        print()

    if body_only:
        parse_body(bs)
    else:
        pack_fmt = '!HQHQ'

        (seq_num_len, seq_num_checksum, body_len, checksum,) = \
            struct.unpack_from(pack_fmt, bs)

        seq_num_and_body = bs[struct.calcsize(pack_fmt):]

        seq_num_bs = seq_num_and_body[0:seq_num_len]
        seq_num = int(str(seq_num_bs, 'ascii'))
        actual_seq_num_checksum = xxhash.xxh64_intdigest(seq_num_bs)

        correct_seq_num = seq_num_bs_checksum == actual_seq_num_checksum

        body = seq_num_and_body[seq_num_bs_len:]
        actual_checksum = xxhash.xxh64_intdigest(body)

        correct_len = len(body) == body_len
        correct_checksum = checksum == xxhash.xxh64_intdigest(body)

        msg_seq_num = f'seq_num: {seq_num}'
        msg_len = f'body_len (in header): {body_len} --> correct?={correct_len}'
        msg_checksum = f'body_checksum: {hex(checksum)} --> correct?={correct_checksum}'
        msg_seq_num_checksum = f'seq_num_checksum: {hex(seq_num_bs_checksum)} --> correct?={correct_seq_num_checksum}'
        if nocolor:
            print(msg_seq_num)
            print(msg_len)
            print(msg_checksum)
            print(msg_seq_num_checksum)
        else:
            cprint(msg_seq_num, color='cyan')
            cprint(msg_len, color='cyan')
            cprint(msg_checksum, color='cyan')
            cprint(msg_seq_num_checksum, color='cyan')

        parse_body(body)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('type', type=str,
                        choices=['cmdreq', 'cmdreqbody',
                                 'cmdresp', 'cmdrespbody',
                                 'evt',
                                 'journal', 'journalbody'])

    parser.add_argument('-bw', '--nocolor', dest='nocolor',
                        action='store_true')
    parser.set_defaults(nocolor=False)

    args = parser.parse_args()

    # print(args)

    if args.type == 'cmdreq' or args.type == 'cmdreqbody':
        parse_cmdreq(body_only=args.type == 'cmdreqbody',
                     nocolor=args.nocolor)
    elif args.type == 'cmdresp' or args.type == 'cmdrespbody':
        parse_cmdresp(body_only=args.type == 'cmdrespbody',
                      nocolor=args.nocolor)
    elif args.type == 'evt':
        parse_event(nocolor=args.nocolor)
    elif args.type == 'journal' or args.type == 'journalbody':
        parse_journal(body_only=args.type == 'journalbody',
                      nocolor=args.nocolor)
