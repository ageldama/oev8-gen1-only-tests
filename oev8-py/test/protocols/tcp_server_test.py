  # pylint: disable=wrong-import-order
import abc
import asyncio
import logging
import json
import datetime
from unittest import TestCase
from unittest.mock import call, Mock, AsyncMock, ANY
import struct
import xxhash  # type:ignore
from pytest import raises  # type:ignore
from oev8_pb2 import Oev8_CommandResponse  # type:ignore
from oev8_pb2 import ERR_OEV8_TIMEOUT
from test.testsup import BytesStreamReader, make_StreamWriter_mock, \
    make_request_bytes
from oev8.protocols.tcp import TcpServerProcessor
from oev8.excs import RequestTimedOut
from oev8.excs import CodedError
from oev8.svcs.event_writer import EventWriterFail
from oev8.svcs.journal import JournalWriterFail
from test.conftest import AsyncIOLoopContext


def test_BytesStreamReader(asyncio_loop_and_runner):
    reader = BytesStreamReader(b'\x00\x01\x02')

    async def do_reader(reader):
        assert (await reader.read(1)) == b'\x00'
        assert (await reader.read(3)) == b'\x01\x02'
        assert (await reader.read(10)) == b''

    with asyncio_loop_and_runner as lnr:
        lnr[1](do_reader(reader))


def test_StreamWriter_mock(asyncio_loop_and_runner):
    writer = make_StreamWriter_mock()

    writer.write(b'\x00')
    writer.write(b'\x01\x02')

    async def drainer(writer):
        await writer.drain()

    with asyncio_loop_and_runner as lnr:
        lnr[1](drainer(writer))

    writer.write.assert_has_calls([
        call(b'\x00'),
        call(b'\x01\x02'),
    ])

    writer.drain.assert_called_once()


class BaseTcpServerProcessorTestCase(TestCase, abc.ABC):

    @abc.abstractmethod
    def request_bytes(self):
        pass

    @abc.abstractmethod
    def prepare(self):
        pass

    def expected_exception(self):
        return None

    def setUp(self):
        self.logger = logging.getLogger()
        self.cmd_handler = Mock()
        self.request_timeout_secs = 10

        self.lock = Mock()
        self.lock.__aenter__ = AsyncMock()
        self.lock.__aexit__ = AsyncMock(return_value=None)

        self.awaiter = AsyncMock()

        self.processor = TcpServerProcessor(
            self.cmd_handler,
            self.awaiter,
            self.request_timeout_secs)

        self.req_bytes = self.request_bytes()
        self.reader = BytesStreamReader(self.req_bytes)
        self.writer = make_StreamWriter_mock()

        self.prepare()

        self.loop_and_runner = AsyncIOLoopContext()

        self.keep_conn = False
        print(self.expected_exception())
        if self.expected_exception() is None:
            with self.loop_and_runner as lnr:
                lnr[1](self.run_loop())
        else:
            with raises(self.expected_exception()):
                with self.loop_and_runner as lnr:
                    lnr[1](self.run_loop())

    async def run_loop(self):
        self.keep_conn = await self.processor(
            self.reader, self.writer, self.lock, '')


class AllOk_TcpServerProcessorTest(BaseTcpServerProcessorTestCase):
    """sizelen만큼 읽고 bytes이 xx64 체크섬과 같고 타임아웃 아닐 때.
    --> True & yes to mock-invks(cmd_handler, writer)."""

    def request_bytes(self) -> bytes:
        self.body = b'foobarzoo'
        self.reqtime = datetime.datetime.utcnow()
        req_bytes = make_request_bytes(self.body, self.reqtime)
        return req_bytes

    def prepare(self):
        self.resp_body = b'HELLO'
        self.cmd_handler.handle = Mock(
            side_effect=lambda sizelen, xx64, req_bytes:
            (self.resp_body, True,))

    def test_01(self):
        assert self.keep_conn

        self.cmd_handler.handle.assert_has_calls([
            call(9, xxhash.xxh64_intdigest(self.body), self.body)
        ])

        self.writer.write.assert_called()
        self.writer.drain.assert_awaited_once()

        # 응답 결과 바이트열 검사.
        joined_bs = b''
        for c in self.writer.write.call_args_list:
            joined_bs = joined_bs + c.args[0]

        hdr_bs = struct.pack('!HQ',
                             len(self.resp_body),
                             xxhash.xxh64_intdigest(self.resp_body))

        assert joined_bs == hdr_bs + self.resp_body

        # lock
        self.lock.__aenter__.assert_awaited_once()
        self.lock.__aexit__.assert_awaited_once_with(ANY, ANY, ANY)

        # awaiter
        self.processor.awaiter.gather_queue.assert_awaited_once()


class ShortBody_TcpServerProcessorTest(BaseTcpServerProcessorTestCase):
    'sizelen만큼 읽지 못할 때 --> ConnectionError & no mock-invks.'

    def request_bytes(self) -> bytes:
        self.body = b'foobarzoo'
        self.reqtime = datetime.datetime.utcnow()
        req_bytes = make_request_bytes(self.body, self.reqtime)
        return req_bytes[:-3]

    def prepare(self):
        self.cmd_handler.handle = Mock(
            side_effect=lambda sizelen, xx64, req_bytes: (b'', True,))

    def expected_exception(self):
        return ConnectionError

    def test_01(self):
        assert not self.keep_conn

        self.cmd_handler.handle.assert_not_called()

        self.writer.write.assert_not_called()
        self.writer.drain.assert_not_awaited()

        # lock
        self.lock.__aenter__.assert_not_awaited()
        self.lock.__aexit__.assert_not_awaited()

        # awaiter
        self.processor.awaiter.gather_queue.assert_awaited_once()


class TimedOut_TcpServerProcessorTest(BaseTcpServerProcessorTestCase):
    """타임아웃일 때 --> True & no mock-invks."""

    def request_bytes(self) -> bytes:
        self.body = b'foobarzoo'
        self.reqtime = datetime.datetime.utcnow() + \
            datetime.timedelta(seconds=-1 * (self.request_timeout_secs + 1))
        req_bytes = make_request_bytes(self.body, self.reqtime)
        return req_bytes

    def prepare(self):
        self.cmd_handler.handle = Mock(
            side_effect=lambda sizelen, xx64, req_bytes: (b'', True,))

    def test_01(self):
        assert self.keep_conn

        self.cmd_handler.handle.assert_not_called()

        self.writer.write.assert_called_once()
        self.writer.drain.assert_awaited_once()

        # lock
        self.lock.__aenter__.assert_not_awaited()
        self.lock.__aexit__.assert_not_awaited()

        # response
        joined_bs = b''
        for c in self.writer.write.call_args_list:
            joined_bs = joined_bs + c.args[0]

        # (resp_len, resp_xxh64,) = struct.unpack_from('!HQ', joined_bs)
        resp = Oev8_CommandResponse()
        resp.ParseFromString(joined_bs[10:])

        assert len(resp.err_str) > 0
        exc = CodedError(**json.loads(resp.err_str))

        assert exc.err_code == ERR_OEV8_TIMEOUT

        # awaiter
        self.processor.awaiter.gather_queue.assert_awaited_once()


class WrongChecksum_TcpServerProcessorTest(BaseTcpServerProcessorTestCase):
    "xx64 체크섬 틀릴 때 --> False & no mock-invks."

    def request_bytes(self) -> bytes:
        self.body = b'foobarzoo'
        self.reqtime = datetime.datetime.utcnow()
        req_bytes = make_request_bytes(self.body, self.reqtime)
        req_bytes = req_bytes[:2] + \
            struct.pack('!Q', xxhash.xxh64_intdigest(b'whatever')) + \
            req_bytes[10:]
        assert len(req_bytes) == 18 + len(self.body)
        return req_bytes

    def prepare(self):
        self.cmd_handler.handle = Mock(
            side_effect=lambda sizelen, xx64, req_bytes: (b'', True,))

    def test_01(self):
        assert not self.keep_conn

        self.cmd_handler.handle.assert_not_called()

        self.writer.write.assert_not_called()
        self.writer.drain.assert_not_awaited()

        self.lock.__aenter__.assert_not_awaited()
        self.lock.__aexit__.assert_not_awaited()

        # awaiter
        self.processor.awaiter.gather_queue.assert_awaited_once()


class EventWriterFail_TcpServerProcessorTest(BaseTcpServerProcessorTestCase):
    def request_bytes(self) -> bytes:
        self.body = b'foobarzoo'
        self.reqtime = datetime.datetime.utcnow()
        req_bytes = make_request_bytes(self.body, self.reqtime)
        return req_bytes

    def prepare(self):
        self.resp_body = b''
        self.cmd_handler.handle = Mock(side_effect=EventWriterFail)

    def expected_exception(self):
        return EventWriterFail

    def test_01(self):
        self.cmd_handler.handle.assert_called_once()
        self.awaiter.gather_queue.assert_awaited_once()


class JournalWriterFail_TcpServerProcessorTest(BaseTcpServerProcessorTestCase):
    def request_bytes(self) -> bytes:
        self.body = b'foobarzoo'
        self.reqtime = datetime.datetime.utcnow()
        req_bytes = make_request_bytes(self.body, self.reqtime)
        return req_bytes

    def prepare(self):
        self.resp_body = b''
        self.cmd_handler.handle = Mock(side_effect=JournalWriterFail)

    def expected_exception(self):
        return JournalWriterFail

    def test_01(self):
        self.cmd_handler.handle.assert_called_once()
        self.awaiter.gather_queue.assert_awaited_once()


class EventWriterFail_Awaiter_TcpServerProcessorTest(BaseTcpServerProcessorTestCase):
    def request_bytes(self) -> bytes:
        self.body = b'foobarzoo'
        self.reqtime = datetime.datetime.utcnow()
        req_bytes = make_request_bytes(self.body, self.reqtime)
        return req_bytes

    def prepare(self):
        self.resp_body = b''
        self.cmd_handler.handle = Mock(return_value=(b'', True,))
        self.awaiter.gather_queue = AsyncMock(side_effect=EventWriterFail)

    def expected_exception(self):
        return EventWriterFail

    def test_01(self):
        self.cmd_handler.handle.assert_called_once()
        self.awaiter.gather_queue.assert_awaited_once()


class EventWriterFail_CmdHandler_Awaiter_TcpServerProcessorTest(BaseTcpServerProcessorTestCase):
    def request_bytes(self) -> bytes:
        self.body = b'foobarzoo'
        self.reqtime = datetime.datetime.utcnow()
        req_bytes = make_request_bytes(self.body, self.reqtime)
        return req_bytes

    def prepare(self):
        self.resp_body = b''
        self.cmd_handler.handle = Mock(side_effect=EventWriterFail)
        self.awaiter.gather_queue = AsyncMock(side_effect=EventWriterFail)

    def expected_exception(self):
        return EventWriterFail

    def test_01(self):
        self.cmd_handler.handle.assert_called_once()
        self.awaiter.gather_queue.assert_awaited_once()


class JournalWriterFail_Awaiter_TcpServerProcessorTest(BaseTcpServerProcessorTestCase):
    def request_bytes(self) -> bytes:
        self.body = b'foobarzoo'
        self.reqtime = datetime.datetime.utcnow()
        req_bytes = make_request_bytes(self.body, self.reqtime)
        return req_bytes

    def prepare(self):
        self.resp_body = b''
        self.cmd_handler.handle = Mock(return_value=(b'', True,))
        self.awaiter.gather_queue = AsyncMock(side_effect=JournalWriterFail)

    def expected_exception(self):
        return JournalWriterFail

    def test_01(self):
        self.cmd_handler.handle.assert_called_once()
        self.awaiter.gather_queue.assert_awaited_once()


class JournalWriterFail_CmdHandler_Awaiter_TcpServerProcessorTest(BaseTcpServerProcessorTestCase):
    def request_bytes(self) -> bytes:
        self.body = b'foobarzoo'
        self.reqtime = datetime.datetime.utcnow()
        req_bytes = make_request_bytes(self.body, self.reqtime)
        return req_bytes

    def prepare(self):
        self.resp_body = b''
        self.cmd_handler.handle = Mock(side_effect=JournalWriterFail)
        self.awaiter.gather_queue = AsyncMock(side_effect=JournalWriterFail)

    def expected_exception(self):
        return JournalWriterFail

    def test_01(self):
        self.cmd_handler.handle.assert_called_once()
        self.awaiter.gather_queue.assert_awaited_once()
