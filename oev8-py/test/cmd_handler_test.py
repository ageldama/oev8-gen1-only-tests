'''tests on CmdHandler.'''

# pylint: disable=too-many-lines, too-many-locals, too-many-public-methods
# pylint: disable=too-many-instance-attributes

import json
import time
import datetime
from itertools import islice
from unittest import TestCase
from unittest.mock import Mock, MagicMock, call, ANY, patch
from pytest import raises  # type:ignore
from oev8_pb2 import Oev8_CommandRequest, Oev8_CommandResponse
from oev8_pb2 import OEV8_CMD_NOPE, \
    OEV8_CMD_SNAPSHOT, OEV8_CMD_SHUTDOWN, \
    OEV8_CMD_SAVE_QUIT, \
    OEV8_CMD_ENTER_MAINT, OEV8_CMD_LEAVE_MAINT, \
    OEV8_CMD_PING, OEV8_CMD_SLEEP, \
    OEV8_CMD_BALANCE_GET, OEV8_CMD_BALANCE_DEPOSIT, \
    OEV8_CMD_BALANCE_WITHDRAW, \
    OEV8_CMD_BALANCE_DELETE_BY_CURRENCY, \
    OEV8_CMD_BALANCE_DELETE_BY_CUSTOMER, \
    OEV8_CMD_BALANCE_XFER_FROM, \
    OEV8_CMD_BALANCE_XFER_TO, \
    OEV8_CMD_BALANCE_CVT_XFER_TO, \
    OEV8_CMD_ITEM_COUNT_GET, \
    OEV8_CMD_ITEM_COUNT_INC, \
    OEV8_CMD_ITEM_COUNT_DEC, \
    OEV8_CMD_ITEM_COUNT_DELETE_BY_TRADING, \
    OEV8_CMD_ITEM_COUNT_DELETE_BY_CUSTOMER, \
    OEV8_CMD_ITEM_COUNT_XFER_FROM, \
    OEV8_CMD_ITEM_COUNT_XFER_TO, \
    OEV8_CMD_TRADING_NEW, OEV8_CMD_TRADING_JOIN, \
    OEV8_CMD_TRADING_RESUME, OEV8_CMD_TRADING_PAUSE, \
    OEV8_CMD_TRADING_FINALIZE, OEV8_CMD_TRADING_CANCEL, \
    OEV8_CMD_TRADING_EVICT, OEV8_CMD_TRADING_PROVIDE_ITEM, \
    OEV8_CMD_TRADING_UNPROVIDE_ITEM, \
    OEV8_CMD_TRADING_ORDER_LIMIT_SELL, \
    OEV8_CMD_TRADING_ORDER_LIMIT_BUY, \
    OEV8_CMD_TRADING_ORDER_MARKET_SELL, \
    OEV8_CMD_TRADING_ORDER_MARKET_BUY, \
    OEV8_CMD_TRADING_ORDER_CANCEL_REMAINING, \
    OEV8_CMD_TRADING_UNTIL, \
    OEV8_CMD_LIST_TRADING_ID, \
    OEV8_CMD_COUNT_TRADING_ID, \
    OEV8_CMD_TRADING_INFO, \
    OEV8_CMD_LIST_ITEM_PROVIDING, \
    OEV8_CMD_COUNT_ITEM_PROVIDING, \
    OEV8_CMD_LIST_ORDER, \
    OEV8_CMD_COUNT_ORDER, \
    OEV8_CMD_LIST_MATCH, \
    OEV8_CMD_COUNT_MATCH, \
    OEV8_CMD_LIST_PRICE, \
    OEV8_CMD_COUNT_PRICE, \
    OEV8_CMD_LIST_ORDER_ID_BY_PRICE, \
    OEV8_CMD_COUNT_ORDER_ID_BY_PRICE, \
    OEV8_CMD_TRADING_AUCTION_INFO, \
    OEV8_CMD_TRADING_NEW_SELLING_AUCTION, \
    OEV8_CMD_TRADING_BID_BUYING, \
    OEV8_CMD_TRADING_NEW_BUYING_AUCTION, \
    OEV8_CMD_TRADING_ASK_SELLING
from oev8_pb2 import ERR_OEV8_CMD_UNKNOWN, ERR_OEV8_CMD_INVALID, \
    ERR_OEV8_INTERNAL_ERROR, ERR_NOT_ENOUGH_BALANCE, \
    ERR_OEV8_UNDER_MAINT, ERR_TRADING_IS_NOT_FOUND
from oev8.svcs import ShutdownService
from oev8.svcs.seq_num import SeqNumService
from oev8.svcs.cmd_handler import CmdHandler
from oev8.svcs.journal import JournalWriter, JournalWriterFail
from oev8.svcs.snapshot import SnapshotService
from oev8.svcs.event_writer import EventWriterFail
from oev8.svcs.event_writer.virtual import BufferedEventWriter
from oev8.svcs.clockwork.trading import TradingClockworkService
from oev8.excs import NotEnoughBalance, TradingIsNotFound
from oev8.typedefs import BalanceType, CurrencyType, TradingState
from oev8.typedefs import OrderSide, OrderType, OrderOption, TradingType
from oev8.typedefs import AuctionSide, SeqType
from oev8.values.orders import OrderOfferLine, MatchedOrderLine
from oev8.values.tradings import Trading
from oev8.values.auctions import Auction
from oev8.values.event_writer import \
    BalanceDepositCauseDeposit, BalanceWithdrawCauseWithdraw, \
    BalanceXferFromCause, BalanceXferToCause, BalanceCvtXferToCause, \
    ItemCountIncCause, ItemCountDecCause, ItemCountXferFromCause, \
    ItemCountXferToCause
from test.testsup import rand_cmd_uuid, \
    rand_balance_type, rand_curr, rand_1mil, rand_order_option
from test.testsup import make_null_logging_stopwatch
from oev8.bench import Stopwatch


def cmd_req_of(cmd_type):
    req = Oev8_CommandRequest()
    req.cmd_type = cmd_type
    return req


class CmdHandlerTests(TestCase):

    def setUp(self):
        self.shutdown_service = Mock(ShutdownService)
        self.seq_num_service = SeqNumService()
        self.balance_service = Mock()
        self.item_count_service = Mock()
        self.trading_service = Mock()
        self.trading_service.balance_service = self.balance_service
        self.trading_service.item_count_service = self.item_count_service
        self.event_writer = Mock(BufferedEventWriter)
        self.journal_writer = Mock(JournalWriter)
        self.snapshot_service = Mock(SnapshotService)
        self.trading_clockwork_service = Mock(TradingClockworkService)
        self.logging_stopwatch = make_null_logging_stopwatch()

        self.cmd_handler = CmdHandler(self.seq_num_service,
                                      self.trading_service,
                                      self.event_writer,
                                      self.shutdown_service,
                                      self.snapshot_service,
                                      self.journal_writer,
                                      self.trading_clockwork_service,
                                      self.logging_stopwatch)
        self.cmd_type = None
        self.cmd_uuid = None

    def __run(self, cmd,
              resp_field_name,
              expect_keep_conn=True,
              no_error=True):
        # 실행.
        self.cmd_uuid = rand_cmd_uuid()
        cmd.cmd_uuid = self.cmd_uuid
        req_bs = cmd.SerializeToString()
        req_len = len(req_bs)
        checksum = rand_1mil()
        resp_bs = self.cmd_handler.handle(
            req_len, checksum, req_bs)

        # CHK: 헤더.
        assert resp_bs[1] == expect_keep_conn

        resp = Oev8_CommandResponse()
        resp.ParseFromString(resp_bs[0])

        assert resp.cmd_uuid == self.cmd_uuid
        assert resp.cmd_type == cmd.cmd_type
        assert int(resp.seq_num) >= 0

        if no_error:
            assert resp.seq_num is not None and int(resp.seq_num) > 0
            assert resp.err_str is None or resp.err_str == ''

            self.event_writer.set_current.assert_has_calls([call(ANY, ANY)])

            self.event_writer.commit_buffer.assert_called()
            # self.event_writer.clear_buffer.assert_not_called()

            self.logging_stopwatch.__enter__.assert_called()
            self.logging_stopwatch.__exit__.assert_called()

        if resp_field_name is not None:
            assert resp.HasField(resp_field_name)

        # 어떤 예외가 발생해도 저널은 기록한다.
        self.journal_writer.write.assert_has_calls([
            call(ANY, req_len, checksum, req_bs)])

        return (resp, resp_bs[0], resp_bs[1],)

    def test_balance_get(self):
        # 요청 만들기.
        balance_type = rand_balance_type()
        curr = rand_curr()
        cust_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_BALANCE_GET)
        cmd.balance_get.balance_type = balance_type.value
        cmd.balance_get.curr = curr
        cmd.balance_get.cust_id = cust_id

        # record mock
        amt = rand_1mil()
        self.balance_service.get = MagicMock(side_effect=lambda *x, **y: amt)

        # 실행.
        (resp, _, _,) = self.__run(cmd, 'balance_get')

        # CHK: 응답 값.
        assert resp.balance_get.amt == str(amt)

        # CHK: 서비스에 전달된 파라미터.
        self.balance_service.get.assert_has_calls([
            call(balance_type=balance_type, cust_id=cust_id, curr=curr)])

    def test_balance_deposit(self):
        # 요청 만들기.
        balance_type = rand_balance_type()
        curr = rand_curr()
        cust_id = str(rand_1mil())
        amt = rand_1mil()

        cmd = cmd_req_of(OEV8_CMD_BALANCE_DEPOSIT)
        cmd.balance_deposit.balance_type = balance_type.value
        cmd.balance_deposit.curr = curr
        cmd.balance_deposit.cust_id = cust_id
        cmd.balance_deposit.amt = str(amt)

        # record mock
        new_amt = rand_1mil()
        self.balance_service.deposit = \
            MagicMock(side_effect=lambda *x, **y: new_amt)

        # 실행.
        (resp, _, _,) = self.__run(cmd, 'balance_deposit')

        # CHK: 응답.
        assert resp.balance_deposit.new_amt== str(new_amt)

        # CHK: interaction with mocked service
        self.balance_service.deposit.assert_has_calls([
            call(balance_type=balance_type, cust_id=cust_id,
                 curr=curr, amt=amt)
        ])

        self.event_writer.on_balance_deposit.assert_has_calls([
            call(balance_type=balance_type, curr=curr, cust_id=cust_id,
                 amt=amt, new_amt=new_amt,
                 why=BalanceDepositCauseDeposit(deposit_request_id=ANY))
        ])

    def test_balance_withdraw(self):
        # BUILD: 요청.
        balance_type = rand_balance_type()
        curr = rand_curr()
        cust_id = str(rand_1mil())
        amt = rand_1mil()

        cmd = cmd_req_of(OEV8_CMD_BALANCE_WITHDRAW)
        cmd.balance_withdraw.balance_type = balance_type.value
        cmd.balance_withdraw.curr = curr
        cmd.balance_withdraw.cust_id = cust_id
        cmd.balance_withdraw.amt = str(amt)

        # BUILD: Mock
        new_amt = rand_1mil()
        self.balance_service.withdraw = \
            MagicMock(side_effect=lambda *x, **y: new_amt)

        # do it
        (resp, _, _,) = self.__run(cmd, 'balance_withdraw')

        # CHK: response body
        assert resp.balance_withdraw.new_amt == str(new_amt)

        # CHK: interaction with mocked service
        self.balance_service.withdraw.assert_has_calls([
            call(balance_type=balance_type, cust_id=cust_id,
                 curr=curr, amt=amt)
        ])

        self.event_writer.on_balance_withdraw.assert_has_calls([
            call(balance_type=balance_type, curr=curr,
                 amt=amt, new_amt=new_amt,
                 why=BalanceWithdrawCauseWithdraw(withdraw_request_id=ANY))
        ])

    def test_balance_delete_by_currency(self):
        # BUILD: 요청.
        curr = rand_curr()

        cmd = cmd_req_of(OEV8_CMD_BALANCE_DELETE_BY_CURRENCY)
        cmd.balance_delete_by_currency.curr = curr

        # BUILD: Mock
        self.balance_service.delete_by_currency = \
            MagicMock(side_effect=lambda *x, **y: None)

        # do it
        self.__run(cmd, None)

        # CHK: interaction with mocked service
        self.balance_service.delete_by_currency.assert_has_calls([
            call(curr=curr)])

        self.event_writer.on_balance_delete_by_currency.assert_has_calls([
            call(curr=curr)
        ])

    def test_balance_delete_by_customer(self):
        # BUILD: 요청.
        cust_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_BALANCE_DELETE_BY_CUSTOMER)
        cmd.balance_delete_by_customer.cust_id = cust_id

        # BUILD: Mock
        self.balance_service.delete_by_customer = \
            MagicMock(side_effect=lambda *x, **y: None)

        # do it
        self.__run(cmd, None)

        # CHK: interaction with mocked service
        self.balance_service.delete_by_customer.assert_has_calls([
            call(cust_id=cust_id)])

        self.event_writer.on_balance_delete_by_customer.assert_has_calls([
            call(cust_id=cust_id)
        ])

    def test_balance_xfer_from(self):
        # BUILD: 요청.

        balance_type = rand_balance_type()
        curr = rand_curr()
        cust_id = str(rand_1mil())
        amt = rand_1mil()

        cmd = cmd_req_of(OEV8_CMD_BALANCE_XFER_FROM)
        cmd.balance_xfer_from.balance_type = balance_type.value
        cmd.balance_xfer_from.curr = curr
        cmd.balance_xfer_from.cust_id = cust_id
        cmd.balance_xfer_from.amt = str(amt)

        # BUILD: Mock
        new_amt = rand_1mil()
        new_svc = rand_1mil()
        self.balance_service.xfer_from = MagicMock(
            side_effect=lambda *x, **y: (new_amt, new_svc,))

        # do it
        (resp, _, _,) = self.__run(cmd, 'balance_xfer_from')

        # CHK: response body
        assert (str(new_amt), str(new_svc),) == \
            (resp.balance_xfer_from.new_amt,
             resp.balance_xfer_from.new_svc,)

        # CHK: interaction with mocked service
        self.balance_service.xfer_from.assert_has_calls([
            call(balance_type=balance_type, cust_id=cust_id,
                 curr=curr, amt=amt)
        ])

        self.event_writer.on_balance_xfer_from.assert_has_calls([
            call(balance_type=balance_type, curr=curr, cust_id=cust_id,
                 amt=amt, new_amt=new_amt, new_svc=new_svc,
                 why=BalanceXferFromCause())
        ])

    def test_balance_xfer_to(self):
        # BUILD: 요청.
        balance_type = rand_balance_type()
        curr = rand_curr()
        cust_id = str(rand_1mil())
        amt = rand_1mil()

        cmd = cmd_req_of(OEV8_CMD_BALANCE_XFER_TO)
        cmd.balance_xfer_to.balance_type = balance_type.value
        cmd.balance_xfer_to.curr = curr
        cmd.balance_xfer_to.cust_id = cust_id
        cmd.balance_xfer_to.amt = str(amt)

        # BUILD: Mock
        new_amt = rand_1mil()
        new_svc = rand_1mil()
        self.balance_service.xfer_to = MagicMock(
            side_effect=lambda *x, **y: (new_amt, new_svc,))

        # do it
        (resp, _, _,) = self.__run(cmd, 'balance_xfer_to')

        # CHK: response body
        assert (str(new_amt), str(new_svc),) == \
            (resp.balance_xfer_to.new_amt, resp.balance_xfer_to.new_svc,)

        # CHK: interaction with mocked service
        self.balance_service.xfer_to.assert_has_calls([
            call(balance_type=balance_type, cust_id=cust_id,
                 curr=curr, amt=amt)
        ])

        self.event_writer.on_balance_xfer_to.assert_has_calls([
            call(balance_type=balance_type, curr=curr, cust_id=cust_id,
                 amt=amt, new_amt=new_amt, new_svc=new_svc, why=BalanceXferToCause())
        ])

    def test_balance_cvt_xfer_to(self):
        # BUILD: 요청.
        from_balance_type = rand_balance_type()
        to_balance_type = rand_balance_type()
        curr = rand_curr()
        cust_id = str(rand_1mil())
        amt = rand_1mil()

        cmd = cmd_req_of(OEV8_CMD_BALANCE_CVT_XFER_TO)
        cmd.balance_cvt_xfer_to.from_balance_type = from_balance_type.value
        cmd.balance_cvt_xfer_to.to_balance_type = to_balance_type.value
        cmd.balance_cvt_xfer_to.curr = curr
        cmd.balance_cvt_xfer_to.cust_id = cust_id
        cmd.balance_cvt_xfer_to.amt = str(amt)

        # BUILD: Mock
        new_amt = rand_1mil()
        new_svc = rand_1mil()
        self.balance_service.cvt_xfer_to = MagicMock(
            side_effect=lambda *x, **y: (new_amt, new_svc,))

        # do it
        (resp, _, _,) = self.__run(cmd, 'balance_cvt_xfer_to')

        # CHK: response body
        assert (str(new_amt), str(new_svc),) == \
            (resp.balance_cvt_xfer_to.new_amt,
             resp.balance_cvt_xfer_to.new_svc,)

        # CHK: interaction with mocked service
        self.balance_service.cvt_xfer_to.assert_has_calls([
            call(from_balance_type=from_balance_type,
                 to_balance_type=to_balance_type,
                 cust_id=cust_id, curr=curr, amt=amt)
        ])

        self.event_writer.on_balance_cvt_xfer_to.assert_has_calls([
            call(from_balance_type=from_balance_type,
                 to_balance_type=to_balance_type,
                 curr=curr, cust_id=cust_id,
                 amt=amt, new_amt=new_amt, new_svc=new_svc,
                 why=BalanceCvtXferToCause())
        ])

    def test_item_count_get(self):
        # BUILD: 요청.
        cust_id = str(rand_1mil())
        trd_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_ITEM_COUNT_GET)
        cmd.item_count_get.cust_id = cust_id
        cmd.item_count_get.trd_id = trd_id

        # BUILD: Mock
        qty = rand_1mil()
        self.item_count_service.get = MagicMock(
            side_effect=lambda *x, **y: qty)

        # do it
        (resp, _, _,) = self.__run(cmd, 'item_count_get')

        # CHK: response body
        assert qty == resp.item_count_get.qty

        # CHK: interaction with mocked service
        self.item_count_service.get.assert_has_calls([
            call(cust_id=cust_id, trd_id=trd_id)
        ])

    def test_item_count_inc(self):
        # BUILD: 요청.
        cust_id = str(rand_1mil())
        trd_id = str(rand_1mil())
        qty = rand_1mil()

        cmd = cmd_req_of(OEV8_CMD_ITEM_COUNT_INC)
        cmd.item_count_inc.cust_id = cust_id
        cmd.item_count_inc.trd_id = trd_id
        cmd.item_count_inc.qty = qty

        # BUILD: Mock
        new_qty = rand_1mil()
        self.item_count_service.inc = MagicMock(
            side_effect=lambda *x, **y: new_qty)

        # do it
        (resp, _, _,) = self.__run(cmd, 'item_count_inc')

        # CHK: response body
        assert new_qty == resp.item_count_inc.qty

        # CHK: interaction with mocked service
        self.item_count_service.inc.assert_has_calls([
            call(cust_id=cust_id, trd_id=trd_id, qty=qty)
        ])

        self.event_writer.on_item_count_inc.assert_has_calls([
            call(cust_id=cust_id, trd_id=trd_id, qty=qty, new_qty=new_qty,
                 why=ItemCountIncCause())
        ])

    def test_item_count_dec(self):
        # BUILD: 요청.
        cust_id = str(rand_1mil())
        trd_id = str(rand_1mil())
        qty = rand_1mil()

        cmd = cmd_req_of(OEV8_CMD_ITEM_COUNT_DEC)
        cmd.item_count_dec.cust_id = cust_id
        cmd.item_count_dec.trd_id = trd_id
        cmd.item_count_dec.qty = qty

        # BUILD: Mock
        new_qty = rand_1mil()
        self.item_count_service.dec = MagicMock(
            side_effect=lambda *x, **y: new_qty)

        # do it
        (resp, _, _,) = self.__run(cmd, 'item_count_dec')

        # CHK: response body
        assert new_qty == resp.item_count_dec.qty

        # CHK: interaction with mocked service
        self.item_count_service.dec.assert_has_calls([
            call(cust_id=cust_id, trd_id=trd_id, qty=qty)
        ])

        self.event_writer.on_item_count_dec.assert_has_calls([
            call(cust_id=cust_id, trd_id=trd_id, qty=qty, new_qty=new_qty,
                 why=ItemCountDecCause())
        ])

    def test_item_count_delete_by_trading(self):
        # BUILD: 요청.
        trd_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_ITEM_COUNT_DELETE_BY_TRADING)
        cmd.item_count_delete_by_trading.trd_id = trd_id

        # BUILD: Mock
        self.item_count_service.delete_by_trading = MagicMock()

        # do it
        self.__run(cmd, None)

        # CHK: interaction with mocked service
        self.item_count_service.delete_by_trading.assert_has_calls([
            call(trd_id=trd_id)])

        self.event_writer.on_item_count_delete_by_trading.assert_has_calls([
            call(trd_id=trd_id)
        ])

    def test_item_count_delete_by_customer(self):
        # BUILD: 요청.
        cust_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_ITEM_COUNT_DELETE_BY_CUSTOMER)
        cmd.item_count_delete_by_customer.cust_id = cust_id

        # BUILD: Mock
        self.item_count_service.delete_by_trading = MagicMock()

        # do it
        self.__run(cmd, None)

        # CHK: interaction with mocked service
        self.item_count_service.delete_by_customer.assert_has_calls([
            call(cust_id=cust_id)])

        self.event_writer.on_item_count_delete_by_customer.assert_has_calls([
            call(cust_id=cust_id)
        ])

    def test_item_count_xfer_from(self):
        # BUILD: 요청.
        cust_id = str(rand_1mil())
        trd_id = str(rand_1mil())
        qty = rand_1mil()

        cmd = cmd_req_of(OEV8_CMD_ITEM_COUNT_XFER_FROM)
        cmd.item_count_xfer_from.cust_id = cust_id
        cmd.item_count_xfer_from.trd_id = trd_id
        cmd.item_count_xfer_from.qty = qty

        # BUILD: Mock
        new_qty = rand_1mil()
        new_svc = rand_1mil()
        self.item_count_service.xfer_from = MagicMock(
            side_effect=lambda *x, **y: (new_qty, new_svc,))

        # do it
        (resp, _, _,) = self.__run(cmd, 'item_count_xfer_from')

        # CHK: response body
        assert (new_qty, new_svc,) == \
            (resp.item_count_xfer_from.new_qty,
             resp.item_count_xfer_from.new_svc,)

        # CHK: interaction with mocked service
        self.item_count_service.xfer_from.assert_has_calls([
            call(cust_id=cust_id, trd_id=trd_id, qty=qty)
        ])

        self.event_writer.on_item_count_xfer_from.assert_has_calls([
            call(cust_id=cust_id, trd_id=trd_id,
                 qty=qty, new_qty=new_qty, new_svc=new_svc,
                 why=ItemCountXferFromCause())
        ])

    def test_item_count_xfer_to(self):
        # BUILD: 요청.
        cust_id = str(rand_1mil())
        trd_id = str(rand_1mil())
        qty = rand_1mil()

        cmd = cmd_req_of(OEV8_CMD_ITEM_COUNT_XFER_TO)
        cmd.item_count_xfer_to.cust_id = cust_id
        cmd.item_count_xfer_to.trd_id = trd_id
        cmd.item_count_xfer_to.qty = qty

        # BUILD: Mock
        new_qty = rand_1mil()
        new_svc = rand_1mil()
        self.item_count_service.xfer_to = MagicMock(
            side_effect=lambda *x, **y: (new_qty, new_svc,))

        # do it
        (resp, _, _,) = self.__run(cmd, 'item_count_xfer_to')

        # CHK: response body
        assert (new_qty, new_svc,) == \
            (resp.item_count_xfer_to.new_qty,
             resp.item_count_xfer_to.new_svc,)

        # CHK: interaction with mocked service
        self.item_count_service.xfer_to.assert_has_calls([
            call(cust_id=cust_id, trd_id=trd_id, qty=qty)
        ])

        self.event_writer.on_item_count_xfer_to.assert_has_calls([
            call(cust_id=cust_id, trd_id=trd_id,
                 qty=qty, new_qty=new_qty, new_svc=new_svc,
                 why=ItemCountXferToCause())
        ])

    def test_trading_new(self):
        # BUILD: 요청.
        curr = rand_curr()
        cust_id = str(rand_1mil())
        trd_id = str(rand_1mil())
        qty = rand_1mil()
        sec_deposit_amt = rand_1mil()
        price = rand_1mil()
        timestamp = rand_1mil()

        cmd = cmd_req_of(OEV8_CMD_TRADING_NEW)
        cmd.trading_new.curr = curr
        cmd.trading_new.cust_id = cust_id
        cmd.trading_new.trd_id = trd_id
        cmd.trading_new.sec_deposit_amt = str(sec_deposit_amt)
        cmd.trading_new.qty = qty
        cmd.trading_new.price = str(price)
        cmd.trading_new.until_utc_timestamp_secs = timestamp

        # BUILD: Mock
        new_ord_id = str(rand_1mil())
        self.trading_service.start_new_trading_as_seller = MagicMock(
            side_effect=lambda *x, **y: new_ord_id)

        # do it
        (resp, _, _,) = self.__run(cmd, 'trading_new')

        # CHK: response body
        assert str(new_ord_id) == resp.trading_new.ord_id

        # CHK: interaction with mocked service
        self.trading_service.start_new_trading_as_seller.assert_has_calls([
            call(curr=curr, cust_id=cust_id, trd_id=trd_id,
                 security_deposit_amt=sec_deposit_amt,
                 limit_sell_unit_price=price, qty=qty,
                 until_utc_timestamp_secs=timestamp)
        ])

    def test_trading_join(self):
        # BUILD: 요청.
        cust_id = str(rand_1mil())
        trd_id = str(rand_1mil())
        qty = rand_1mil()
        sec_deposit_amt = rand_1mil()

        cmd = cmd_req_of(OEV8_CMD_TRADING_JOIN)
        cmd.trading_join.cust_id = cust_id
        cmd.trading_join.trd_id = trd_id
        cmd.trading_join.qty = qty
        cmd.trading_join.sec_deposit_amt = str(sec_deposit_amt)

        # BUILD: Mock
        self.trading_service.join_as_item_provider = MagicMock()

        # do it
        self.__run(cmd, None)

        # CHK: interaction with mocked service
        self.trading_service.join_as_item_provider.assert_has_calls([
            call(cust_id=cust_id, trd_id=trd_id,
                 security_deposit_amt=sec_deposit_amt, qty=qty)
        ])

    def test_trading_resume(self):
        # BUILD: 요청.
        trd_id = str(rand_1mil())
        cmd = cmd_req_of(OEV8_CMD_TRADING_RESUME)
        cmd.trading_resume.trd_id = trd_id

        # BUILD: Mock
        self.trading_service.resume_trading = MagicMock()

        # do it
        self.__run(cmd, None)

        # CHK: interaction with mocked service
        self.trading_service.resume_trading.assert_has_calls([
            call(trd_id=trd_id)
        ])

    def test_trading_pause(self):
        # BUILD: 요청.
        trd_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_TRADING_PAUSE)
        cmd.trading_pause.trd_id = trd_id

        # BUILD: Mock
        self.trading_service.pause_trading = MagicMock()

        # do it
        self.__run(cmd, None)

        # CHK: interaction with mocked service
        self.trading_service.pause_trading.assert_has_calls([
            call(trd_id=trd_id)
        ])

    def test_trading_finalize(self):
        # BUILD: 요청.
        trd_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_TRADING_FINALIZE)
        cmd.trading_finalize.trd_id = trd_id

        # BUILD: Mock
        self.trading_service.finalize_trading = MagicMock()

        # do it
        self.__run(cmd, None)

        # CHK: interaction with mocked service
        self.trading_service.finalize_trading.assert_has_calls([
            call(trd_id=trd_id)
        ])

    def test_trading_cancel(self):
        # BUILD: 요청.
        trd_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_TRADING_CANCEL)
        cmd.trading_cancel.trd_id = trd_id

        # BUILD: Mock
        self.trading_service.cancel_trading = MagicMock()

        # do it
        self.__run(cmd, None)

        # CHK: interaction with mocked service
        self.trading_service.cancel_trading.assert_has_calls([
            call(trd_id=trd_id)
        ])

    def test_trading_evict(self):
        # BUILD: 요청.
        trd_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_TRADING_EVICT)
        cmd.trading_evict.trd_id = trd_id

        # BUILD: Mock
        self.trading_service.evict_trading = MagicMock()

        # do it
        self.__run(cmd, None)

        # CHK: interaction with mocked service
        self.trading_service.evict_trading.assert_has_calls([
            call(trd_id=trd_id)
        ])

    def test_trading_provide_item(self):
        # BUILD: 요청.
        cust_id = str(rand_1mil())
        trd_id = str(rand_1mil())
        qty = rand_1mil()

        cmd = cmd_req_of(OEV8_CMD_TRADING_PROVIDE_ITEM)
        cmd.trading_provide_item.cust_id = cust_id
        cmd.trading_provide_item.trd_id = trd_id
        cmd.trading_provide_item.qty = qty

        # BUILD: Mock
        new_qty = rand_1mil()
        self.trading_service.provide_item = MagicMock(
            side_effect=lambda *x, **y: new_qty)

        # do it
        (resp, _, _,) = self.__run(cmd, 'trading_provide_item')

        # CHK: response body
        assert new_qty == resp.trading_provide_item.qty

        # CHK: interaction with mocked service
        self.trading_service.provide_item.assert_has_calls([
            call(cust_id=cust_id, trd_id=trd_id, qty=qty)
        ])

    def test_trading_unprovide_item(self):
        # BUILD: 요청.
        cust_id = str(rand_1mil())
        trd_id = str(rand_1mil())
        qty = rand_1mil()

        cmd = cmd_req_of(OEV8_CMD_TRADING_UNPROVIDE_ITEM)
        cmd.trading_unprovide_item.cust_id = cust_id
        cmd.trading_unprovide_item.trd_id = trd_id
        cmd.trading_unprovide_item.qty = qty

        # BUILD: Mock
        new_qty = rand_1mil()
        self.trading_service.unprovide_item = MagicMock(
            side_effect=lambda *x, **y: new_qty)

        # do it
        (resp, _, _,) = self.__run(cmd, 'trading_unprovide_item')

        # CHK: response body
        assert new_qty == resp.trading_unprovide_item.qty

        # CHK: interaction with mocked service
        self.trading_service.unprovide_item.assert_has_calls([
            call(cust_id=cust_id, trd_id=trd_id, decrease_qty=qty)
        ])

    def test_trading_order_limit_sell(self):
        # BUILD: 요청.
        cust_id = str(rand_1mil())
        trd_id = str(rand_1mil())
        price = rand_1mil()
        qty = rand_1mil()
        option = rand_order_option()

        cmd = cmd_req_of(OEV8_CMD_TRADING_ORDER_LIMIT_SELL)
        cmd.trading_order_limit_sell.cust_id = cust_id
        cmd.trading_order_limit_sell.trd_id = trd_id
        cmd.trading_order_limit_sell.price = str(price)
        cmd.trading_order_limit_sell.qty = qty
        cmd.trading_order_limit_sell.option = option.value

        # BUILD: Mock
        new_ord_id = rand_1mil()
        self.trading_service.order_limit_sell = MagicMock(
            side_effect=lambda *x, **y: new_ord_id)

        # do it
        (resp, _, _,) = self.__run(cmd, 'trading_order_new')

        # CHK: response body
        assert str(new_ord_id) == resp.trading_order_new.ord_id

        # CHK: interaction with mocked service
        self.trading_service.order_limit_sell.assert_has_calls([
            call(cust_id=cust_id, trd_id=trd_id, price=price, qty=qty,
                 option=option)
        ])

    def test_trading_order_limit_buy(self):
        # BUILD: 요청.
        cust_id = str(rand_1mil())
        trd_id = str(rand_1mil())
        price = rand_1mil()
        qty = rand_1mil()
        option = rand_order_option()

        cmd = cmd_req_of(OEV8_CMD_TRADING_ORDER_LIMIT_BUY)
        cmd.trading_order_limit_buy.cust_id = cust_id
        cmd.trading_order_limit_buy.trd_id = trd_id
        cmd.trading_order_limit_buy.price = str(price)
        cmd.trading_order_limit_buy.qty = qty
        cmd.trading_order_limit_buy.option = option.value

        # BUILD: Mock
        new_ord_id = rand_1mil()
        self.trading_service.order_limit_buy = MagicMock(
            side_effect=lambda *x, **y: new_ord_id)

        # do it
        (resp, _, _,) = self.__run(cmd, 'trading_order_new')

        # CHK: response body
        assert str(new_ord_id) == resp.trading_order_new.ord_id

        # CHK: interaction with mocked service
        self.trading_service.order_limit_buy.assert_has_calls([
            call(cust_id=cust_id, trd_id=trd_id, price=price, qty=qty,
                 option=option)
        ])

    def test_trading_order_market_sell(self):
        # BUILD: 요청.
        cust_id = str(rand_1mil())
        trd_id = str(rand_1mil())
        qty = rand_1mil()
        option = rand_order_option()

        cmd = cmd_req_of(OEV8_CMD_TRADING_ORDER_MARKET_SELL)
        cmd.trading_order_market_sell.cust_id = cust_id
        cmd.trading_order_market_sell.trd_id = trd_id
        cmd.trading_order_market_sell.qty = qty
        cmd.trading_order_market_sell.option = option.value

        # BUILD: Mock
        new_ord_id = rand_1mil()
        self.trading_service.order_market_sell = MagicMock(
            side_effect=lambda *x, **y: new_ord_id)

        # do it
        (resp, _, _,) = self.__run(cmd, 'trading_order_new')

        # CHK: response body
        assert str(new_ord_id) == resp.trading_order_new.ord_id

        # CHK: interaction with mocked service
        self.trading_service.order_market_sell.assert_has_calls([
            call(cust_id=cust_id, trd_id=trd_id, qty=qty, option=option)
        ])

    def test_trading_order_market_buy(self):
        # BUILD: 요청.
        cust_id = str(rand_1mil())
        trd_id = str(rand_1mil())
        qty = rand_1mil()
        option = rand_order_option()

        cmd = cmd_req_of(OEV8_CMD_TRADING_ORDER_MARKET_BUY)
        cmd.trading_order_market_buy.cust_id = cust_id
        cmd.trading_order_market_buy.trd_id = trd_id
        cmd.trading_order_market_buy.qty = qty
        cmd.trading_order_market_buy.option = option.value

        # BUILD: Mock
        new_ord_id = rand_1mil()
        self.trading_service.order_market_buy = MagicMock(
            side_effect=lambda *x, **y: new_ord_id)

        # do it
        (resp, _, _,) = self.__run(cmd, 'trading_order_new')

        # CHK: response body
        assert str(new_ord_id) == resp.trading_order_new.ord_id

        # CHK: interaction with mocked service
        self.trading_service.order_market_buy.assert_has_calls([
            call(cust_id=cust_id, trd_id=trd_id, qty=qty, option=option)
        ])

    def test_trading_order_cancel_remaining(self):
        # BUILD: 요청.
        trd_id = str(rand_1mil())
        ord_id = rand_1mil()

        cmd = cmd_req_of(OEV8_CMD_TRADING_ORDER_CANCEL_REMAINING)
        cmd.trading_order_cancel_remaining.trd_id = trd_id
        cmd.trading_order_cancel_remaining.ord_id = str(ord_id)

        # BUILD: Mock
        self.trading_service.cancel_remaining_offer = MagicMock()

        # do it
        self.__run(cmd, None)

        # CHK: interaction with mocked service
        self.trading_service.cancel_remaining_offer.assert_has_calls([
            call(trd_id=trd_id, ord_id=ord_id)
        ])

    def test_trading_until_get(self):
        # BUILD: 요청.
        trd_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_TRADING_UNTIL)
        cmd.trading_until.trd_id = trd_id
        cmd.trading_until.until_utc_timestamp_secs = 0  # for getting

        # BUILD: Mock
        timestamp = rand_1mil()
        self.trading_clockwork_service.find = MagicMock(
            side_effect=lambda *x, **y: timestamp)

        # do it
        (resp, _, _,) = self.__run(cmd, 'trading_until')

        # CHK: response body
        assert trd_id == resp.trading_until.trd_id
        assert timestamp == resp.trading_until.until_utc_timestamp_secs
        assert not resp.trading_until.updated

        # CHK: interaction with mocked service
        self.trading_clockwork_service.find.assert_has_calls([
            call(trd_id)
        ])

    def test_trading_until_get_fail(self):
        # BUILD: 요청.
        trd_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_TRADING_UNTIL)
        cmd.trading_until.trd_id = trd_id
        cmd.trading_until.until_utc_timestamp_secs = 0  # for getting

        # BUILD: Mock
        self.trading_clockwork_service.find = MagicMock(
            side_effect=TradingIsNotFound(trd_id=trd_id))

        # do it
        (resp, _, _,) = self.__run(cmd, None, True, False)

        # CHK: response body
        assert resp.err_str is not None
        err = json.loads(resp.err_str)
        assert err['err_code'] == ERR_TRADING_IS_NOT_FOUND
        assert err['trd_id'] == trd_id

    def test_trading_until_set(self):
        # BUILD: 요청.
        trd_id = str(rand_1mil())
        timestamp = rand_1mil()

        cmd = cmd_req_of(OEV8_CMD_TRADING_UNTIL)
        cmd.trading_until.trd_id = trd_id
        cmd.trading_until.until_utc_timestamp_secs = timestamp

        # BUILD: Mock
        self.trading_clockwork_service.update = MagicMock(
            side_effect=lambda *x, **y: timestamp)

        # do it
        (resp, _, _,) = self.__run(cmd, 'trading_until')

        # CHK: response body
        assert trd_id == resp.trading_until.trd_id
        assert timestamp == resp.trading_until.until_utc_timestamp_secs
        assert resp.trading_until.updated

        # CHK: interaction with mocked service
        self.trading_clockwork_service.update.assert_has_calls([
            call(trd_id, timestamp)
        ])

    def test_no_such_mapping(self):
        # BUILD: 요청.
        cmd = cmd_req_of(OEV8_CMD_NOPE)

        # do it
        (resp, _, keep_connection,) = self.__run(cmd, None, False, False)

        #
        assert not keep_connection

        #
        assert resp.err_str is not None
        err = json.loads(resp.err_str)
        assert err['err_code'] == ERR_OEV8_CMD_UNKNOWN
        assert 'cmd_type' in err
        assert err['cmd_type'] == OEV8_CMD_NOPE

    def test_with_extra_bytes(self):
        # BUILD: 요청.
        cmd = cmd_req_of(OEV8_CMD_BALANCE_GET)
        cmd.balance_get.balance_type = rand_balance_type().value
        cmd.balance_get.curr = rand_curr()
        cmd.balance_get.cust_id = str(rand_1mil())

        cmd_bs = cmd.SerializeToString()

        # do it
        (resp_bs, keep_connection,) = self.cmd_handler.handle(
            0, 0, cmd_bs + b'123')

        #
        assert not keep_connection

        #
        resp = Oev8_CommandResponse()
        resp.ParseFromString(resp_bs)

        assert resp.err_str is not None

        err = json.loads(resp.err_str)
        assert err['err_code'] == ERR_OEV8_CMD_INVALID
        assert 'err_mesg' in err
        assert len(err['err_mesg']) > 0

    def test_empty_bytes(self):
        # do it
        (resp_bs, keep_connection,) = self.cmd_handler.handle(0, 0, b'')

        #
        assert not keep_connection

        #
        resp = Oev8_CommandResponse()
        resp.ParseFromString(resp_bs)

        assert resp.err_str is not None

        err = json.loads(resp.err_str)
        assert err['err_code'] == ERR_OEV8_CMD_UNKNOWN

    def test_shorter_bytes(self):
        # BUILD: 요청.
        cmd = cmd_req_of(OEV8_CMD_BALANCE_GET)
        cmd.balance_get.balance_type = rand_balance_type().value
        cmd.balance_get.curr = rand_curr()
        cmd.balance_get.cust_id = str(rand_1mil())

        cmd_bs = cmd.SerializeToString()

        # do it
        (resp_bs, keep_connection,) = self.cmd_handler.handle(
            0, 0, cmd_bs[:-2])

        #
        assert not keep_connection

        #
        resp = Oev8_CommandResponse()
        resp.ParseFromString(resp_bs)

        assert resp.err_str is not None

        err = json.loads(resp.err_str)
        assert err['err_code'] == ERR_OEV8_CMD_INVALID
        assert 'err_mesg' in err
        assert len(err['err_mesg']) > 0

    def test_coded_error(self):
        # 요청 만들기.
        balance_type = rand_balance_type()
        curr = rand_curr()
        cust_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_BALANCE_GET)
        cmd.balance_get.balance_type = balance_type.value
        cmd.balance_get.curr = curr
        cmd.balance_get.cust_id = cust_id

        # record mock
        exc = NotEnoughBalance(
            balance_type=BalanceType.BALANCE,
            cust_id=str(123),
            curr=CurrencyType(0),
            current_amt=456,
            requested_amt=789)

        self.balance_service.get = MagicMock(side_effect=exc)

        # 실행.
        (resp, _, keep_connection,) = self.__run(cmd, None, True, False)

        #
        assert keep_connection

        #
        err = json.loads(resp.err_str)
        assert err['err_code'] == ERR_NOT_ENOUGH_BALANCE

    def test_non_coded_error(self):
        # 요청 만들기.
        balance_type = rand_balance_type()
        curr = rand_curr()
        cust_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_BALANCE_GET)
        cmd.balance_get.balance_type = balance_type.value
        cmd.balance_get.curr = curr
        cmd.balance_get.cust_id = cust_id

        # record mock
        self.balance_service.get = MagicMock(side_effect=RuntimeError('idk2'))

        # 실행.
        (resp, _, keep_connection,) = self.__run(cmd, None, True, False)

        #
        assert keep_connection

        #
        err = json.loads(resp.err_str)
        assert err['err_code'] == ERR_OEV8_INTERNAL_ERROR
        assert len(err['err_mesg']) > 0

    def test_enter_maint(self):
        # 요청 만들기.
        cmd = cmd_req_of(OEV8_CMD_ENTER_MAINT)

        # REC
        self.event_writer.on_entered_maint = MagicMock()

        # 실행.
        (_, _, keep_connection,) = self.__run(cmd, None, True, False)

        #
        assert keep_connection

        # CHK: event_writer
        self.event_writer.on_entered_maint.assert_has_calls([call()])

    def test_leave_maint(self):
        # REC
        self.event_writer.on_entered_maint = MagicMock()
        self.event_writer.on_left_maint = MagicMock()

        # 일단 enter.
        cmd = cmd_req_of(OEV8_CMD_ENTER_MAINT)
        (_, _, keep_connection,) = self.__run(cmd, None, True, False)

        # 요청 만들기.
        cmd = cmd_req_of(OEV8_CMD_LEAVE_MAINT)

        # 실행.
        (_, _, keep_connection,) = self.__run(cmd, None, True, False)

        #
        assert keep_connection

        # CHK: event_writer
        self.event_writer.on_left_maint.assert_has_calls([call()])

    def test_maint_mode_rejection(self):
        # enter maint-mode
        cmd = cmd_req_of(OEV8_CMD_ENTER_MAINT)
        self.__run(cmd, None, True, False)

        # record mock
        amt = rand_1mil()
        self.balance_service.get = MagicMock(side_effect=lambda *x, **y: amt)

        # try: balance_get
        balance_type = rand_balance_type()
        curr = rand_curr()
        cust_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_BALANCE_GET)
        cmd.balance_get.balance_type = balance_type.value
        cmd.balance_get.curr = curr
        cmd.balance_get.cust_id = str(cust_id)

        (resp, _, _,) = self.__run(
            cmd, None, False, False)

        err = json.loads(resp.err_str)
        assert err['err_code'] == ERR_OEV8_UNDER_MAINT

        # leave maint-mode
        cmd = cmd_req_of(OEV8_CMD_LEAVE_MAINT)
        self.__run(cmd, None, True, False)

        # try again: now it's fine.
        (resp, _, _,) = self.__run(
            cmd, None, True, True)

    def test_trading_list_ids(self):
        # record mock
        list_trading_id = MagicMock(
            return_value=['18', '1818', '69', '6969'])
        self.trading_service.list_trading_id = list_trading_id

        # req.
        cmd = cmd_req_of(OEV8_CMD_LIST_TRADING_ID)
        cmd.trading_list_id.offset = 1
        cmd.trading_list_id.limit = 2

        (resp, _, _,) = self.__run(cmd, 'trading_list_id')

        # verify mock
        list_trading_id.assert_has_calls([call(offset=1, limit=2)])

        #
        assert resp.trading_list_id.trd_ids == ['18', '1818', '69', '6969']

    def test_trading_count_ids(self):
        # record mock
        count_trading_id = MagicMock(return_value=18)
        self.trading_service.count_trading_id = count_trading_id

        # req.
        cmd = cmd_req_of(OEV8_CMD_COUNT_TRADING_ID)

        (resp, _, _,) = self.__run(cmd, 'trading_count_id')

        # verify mock
        count_trading_id.assert_called_once()

        #
        assert resp.trading_count_id.count == 18

    def test_trading_get_info(self):
        # record mock
        trd = Trading()
        trd.state = TradingState.OPEN
        trd.curr = 18
        trd.trading_type = TradingType.AUCTION
        get_trading_info = MagicMock(return_value=trd)
        self.trading_service.get_trading_info = get_trading_info

        # req.
        req = cmd_req_of(OEV8_CMD_TRADING_INFO)
        req.trading_get_info.trd_id = str(123)

        (resp, _, _,) = self.__run(req, 'trading_get_info')

        # verify mock
        get_trading_info.assert_has_calls([call(trd_id=str(123))])

        #
        assert resp.trading_get_info.state == TradingState.OPEN.value
        assert resp.trading_get_info.curr == 18
        assert resp.trading_get_info.trading_type == TradingType.AUCTION.value

    def test_trading_get_auction_info(self):
        # record mock
        auction = Auction()
        auction.cust_id = str(18)
        auction.price = 1818
        auction.qty = 181818
        auction.auction_side = AuctionSide.SELLING
        self.trading_service.get_auction_info = MagicMock(
            return_value=auction)

        # req.
        req = cmd_req_of(OEV8_CMD_TRADING_AUCTION_INFO)
        req.trading_get_auction_info.trd_id = str(123)

        (resp, _, _,) = self.__run(req, 'trading_get_auction_info')

        # verify mock
        self.trading_service.get_auction_info.assert_has_calls([
            call(trd_id=str(123))
        ])

        #
        assert resp.trading_get_auction_info.cust_id == str(18)
        assert resp.trading_get_auction_info.price == str(1818)
        assert resp.trading_get_auction_info.qty == 181818
        assert resp.trading_get_auction_info.auction_side == AuctionSide.SELLING.value

    def test_trading_list_providing(self):
        # record mock
        providings = {
            '12': 34,
            '56': 78,
        }
        list_item_providing = MagicMock(return_value=islice(providings.items(), 0, 100))
        self.trading_service.list_item_providing = list_item_providing

        # req.
        req = cmd_req_of(OEV8_CMD_LIST_ITEM_PROVIDING)
        req.trading_list_item_providing.trd_id = str(123)
        req.trading_list_item_providing.offset = 456
        req.trading_list_item_providing.limit = 789

        (resp, _, _,) = self.__run(req, 'trading_list_item_providing')

        # verify mock
        list_item_providing.assert_has_calls([
            call(trd_id=str(123), offset=456, limit=789)
        ])

        #
        qty_per_cust = resp.trading_list_item_providing.qty_per_cust
        assert str(12) in qty_per_cust
        assert str(56) in qty_per_cust
        assert str(34) not in qty_per_cust
        assert 34 == qty_per_cust['12']
        assert 78 == qty_per_cust['56']

    def test_trading_count_providing(self):
        # record mock
        count_item_providing = MagicMock(return_value=42)
        self.trading_service.count_item_providing = count_item_providing

        # req.
        req = cmd_req_of(OEV8_CMD_COUNT_ITEM_PROVIDING)
        req.trading_count_item_providing.trd_id = str(123)

        (resp, _, _,) = self.__run(req, 'trading_count_item_providing')

        # verify mock
        count_item_providing.assert_has_calls([call(trd_id=str(123))])

        #
        assert 42 == resp.trading_count_item_providing.count

    def test_trading_list_order(self):
        # record mock
        results = {
            12: OrderOfferLine(cust_id='1',
                               side=OrderSide.BUY,
                               order_type=OrderType.LIMIT,
                               option=OrderOption.FILL_OR_KILL,
                               qty=123,
                               price=456,
                               fulfilled=False,
                               cancelled=False),
            34: OrderOfferLine(cust_id='2',
                               side=OrderSide.SELL,
                               order_type=OrderType.MARKET,
                               option=OrderOption.NONE,
                               qty=1011,
                               price=1213,
                               fulfilled=False,
                               cancelled=True),
        }
        list_order = MagicMock(return_value=islice(results.items(), 0, 100))
        self.trading_service.list_order = list_order

        # req.
        req = cmd_req_of(OEV8_CMD_LIST_ORDER)
        req.trading_list_order.trd_id = '123'
        req.trading_list_order.offset = 456
        req.trading_list_order.limit = 789
        (resp, _, _,) = self.__run(req, 'trading_list_order')

        # verify mock
        list_order.assert_has_calls([
            call(trd_id='123', offset=456, limit=789)
        ])

        assert 2 == len(resp.trading_list_order.orders)

        # o_1
        o_1 = resp.trading_list_order.orders[0]
        assert '12' == o_1.order_id
        assert '1' == o_1.cust_id
        assert OrderSide.BUY.value == o_1.order_side
        assert OrderType.LIMIT.value == o_1.order_type
        assert OrderOption.FILL_OR_KILL.value == o_1.order_option
        assert 123 == o_1.qty
        assert '456' == o_1.price
        assert not o_1.fulfilled
        assert not o_1.cancelled

        # o_2
        o_2 = resp.trading_list_order.orders[1]
        assert '34' == o_2.order_id
        assert '2' == o_2.cust_id
        assert OrderSide.SELL.value == o_2.order_side
        assert OrderType.MARKET.value == o_2.order_type
        assert OrderOption.NONE.value == o_2.order_option
        assert 1011 == o_2.qty
        assert '1213' == o_2.price
        assert not o_2.fulfilled
        assert o_2.cancelled

    def test_trading_count_order(self):
        count_order = MagicMock(return_value=42)
        self.trading_service.count_order = count_order

        # req.
        req = cmd_req_of(OEV8_CMD_COUNT_ORDER)
        req.trading_count_order.trd_id = str(123)

        (resp, _, _,) = self.__run(req, 'trading_count_order')

        # verify mock
        count_order.assert_has_calls([call(trd_id=str(123))])

        #
        assert 42 == resp.trading_count_order.count

    def test_trading_list_match(self):
        matches = [
            MatchedOrderLine(
                match_id=12,
                qty=18, price=1818,
                making_taking_order_pair=(12, 34,)),
        ]
        list_match = MagicMock(return_value=matches)
        self.trading_service.list_match = list_match

        # req.
        req = cmd_req_of(OEV8_CMD_LIST_MATCH)
        req.trading_list_match.trd_id = '1234'
        req.trading_list_match.offset = 10
        req.trading_list_match.limit = 11

        (resp, _, _,) = self.__run(req, 'trading_list_match')

        # verify mock
        list_match.assert_has_calls([call(trd_id='1234',
                                          offset=10, limit=11)])

        #
        assert 1 == len(resp.trading_list_match.matches)

        m_1 = resp.trading_list_match.matches[0]
        assert '12' == m_1.match_id
        assert 18 == m_1.qty
        assert '1818' == m_1.price
        assert '12' == m_1.making_order_id
        assert '34' == m_1.taking_order_id

    def test_trading_count_match(self):
        count_match = MagicMock(return_value=42)
        self.trading_service.count_match = count_match

        # req.
        req = cmd_req_of(OEV8_CMD_COUNT_MATCH)
        req.trading_count_match.trd_id = str(1234)

        (resp, _, _,) = self.__run(req, 'trading_count_match')

        # verify mock
        count_match.assert_has_calls([call(trd_id=str(1234))])

        #
        assert 42 == resp.trading_count_match.count

    def test_trading_list_price(self):
        list_price = MagicMock(return_value=[123, 456, 789])
        self.trading_service.list_price = list_price

        # req.
        req = cmd_req_of(OEV8_CMD_LIST_PRICE)
        req.trading_list_price.trd_id = str(12)
        req.trading_list_price.order_side = OrderSide.BUY.value
        req.trading_list_price.offset = 13
        req.trading_list_price.limit = 45

        (resp, _, _,) = self.__run(req, 'trading_list_price')

        # verify mock
        list_price.assert_has_calls([
            call(trd_id=str(12), order_side=OrderSide.BUY,
                 offset=13, limit=45)
        ])

        #
        assert ['123', '456', '789'] == resp.trading_list_price.prices

    def test_trading_count_price(self):
        count_price = MagicMock(return_value=12345)
        self.trading_service.count_price = count_price

        # req.
        req = cmd_req_of(OEV8_CMD_COUNT_PRICE)
        req.trading_count_price.trd_id = str(12)
        req.trading_count_price.order_side = OrderSide.BUY.value

        (resp, _, _,) = self.__run(req, 'trading_count_price')

        # verify mock
        count_price.assert_has_calls([
            call(trd_id=str(12), order_side=OrderSide.BUY)
        ])

        #
        assert 12345 == resp.trading_count_price.count

    def test_trading_list_order_by_price(self):
        list_order_by_price = MagicMock(return_value=islice({
            12: 34, 45: 78, 90: 1112,
        }.items(), 0, 100))
        self.trading_service.list_order_id_by_price = list_order_by_price

        # req.
        req = cmd_req_of(OEV8_CMD_LIST_ORDER_ID_BY_PRICE)
        req.trading_list_order_by_price.trd_id = str(123)
        req.trading_list_order_by_price.order_side = OrderSide.SELL.value
        req.trading_list_order_by_price.price = str(456)
        req.trading_list_order_by_price.offset = 78
        req.trading_list_order_by_price.limit = 90

        (resp, _, _,) = self.__run(req, 'trading_list_order_by_price')

        #
        assert {'12': 34, '45': 78, '90': 1112} == \
            resp.trading_list_order_by_price.qty_per_order_id

        # verify mock
        list_order_by_price.assert_has_calls([
            call(trd_id=str(123), order_side=OrderSide.SELL,
                 price=456, offset=78, limit=90)
        ])

    def test_trading_count_order_by_price(self):
        count_order_by_price = MagicMock(return_value=1818)
        self.trading_service.count_order_id_by_price = count_order_by_price

        # req.
        req = cmd_req_of(OEV8_CMD_COUNT_ORDER_ID_BY_PRICE)
        req.trading_count_order_by_price.trd_id = str(123)
        req.trading_count_order_by_price.order_side = OrderSide.SELL.value
        req.trading_count_order_by_price.price = str(456)

        (resp, _, _,) = self.__run(req, 'trading_count_order_by_price')

        #
        assert 1818 == \
            resp.trading_count_order_by_price.count

        # verify mock
        count_order_by_price.assert_has_calls([
            call(trd_id=str(123), order_side=OrderSide.SELL, price=456)
        ])

    def test_trading_new_selling_auction(self):
        start_new_selling_auction = MagicMock()
        self.trading_service.start_new_selling_auction = \
            start_new_selling_auction

        # req.
        req = cmd_req_of(OEV8_CMD_TRADING_NEW_SELLING_AUCTION)
        req.trading_new_selling_auction.trd_id = str(123)
        req.trading_new_selling_auction.curr = 45
        req.trading_new_selling_auction.cust_id = str(181818)
        req.trading_new_selling_auction.price = str(678)
        req.trading_new_selling_auction.qty = 91011
        req.trading_new_selling_auction.security_deposit_amt = str(1213)
        req.trading_new_selling_auction.until_utc_timestamp_secs = 141516

        (resp, _, _,) = self.__run(req, 'trading_new_selling_auction')

        #
        resp_body = resp.trading_new_selling_auction

        assert str(123) == resp_body.trd_id

        # verify mock
        start_new_selling_auction.assert_has_calls([
            call(trd_id=str(123), curr=45, cust_id=str(181818),
                 price=678, qty=91011,
                 security_deposit_amt=1213,
                 until_utc_timestamp_secs=141516)
        ])

    def test_trading_new_buying_auction(self):
        start_new_buying_auction = MagicMock()
        self.trading_service.start_new_buying_auction = \
            start_new_buying_auction

        # req.
        req = cmd_req_of(OEV8_CMD_TRADING_NEW_BUYING_AUCTION)
        req.trading_new_buying_auction.trd_id = str(123)
        req.trading_new_buying_auction.curr = 45
        req.trading_new_buying_auction.cust_id = str(181818)
        req.trading_new_buying_auction.price = str(678)
        req.trading_new_buying_auction.qty = 91011
        req.trading_new_buying_auction.security_deposit_amt = str(1213)
        req.trading_new_buying_auction.until_utc_timestamp_secs = 141516

        (resp, _, _,) = self.__run(req, 'trading_new_buying_auction')

        #
        resp_body = resp.trading_new_buying_auction

        assert str(123) == resp_body.trd_id

        # verify mock
        start_new_buying_auction.assert_has_calls([
            call(trd_id=str(123), curr=45, cust_id=str(181818),
                 price=678, qty=91011,
                 security_deposit_amt=1213,
                 until_utc_timestamp_secs=141516)
        ])

    def test_trading_bid_buying(self):
        bid_buying = MagicMock(return_value=181818)
        self.trading_service.bid_buying = bid_buying

        # req.
        req = cmd_req_of(OEV8_CMD_TRADING_BID_BUYING)
        req.trading_bid_buying.trd_id = str(123)
        req.trading_bid_buying.cust_id = str(456)
        req.trading_bid_buying.price = str(789)
        req.trading_bid_buying.qty = 1011
        req.trading_bid_buying.option = OrderOption.FILL_OR_KILL.value

        (resp, _, _,) = self.__run(req, 'trading_bid_buying')

        #
        assert str(181818) == resp.trading_bid_buying.ord_id

        # verify mock
        bid_buying.assert_has_calls([
            call(trd_id=str(123),
                 cust_id=str(456),
                 price=789,
                 qty=1011,
                 option=OrderOption.FILL_OR_KILL)
        ])

    def test_trading_ask_selling(self):
        ask_selling = MagicMock(return_value=181818)
        self.trading_service.ask_selling= ask_selling

        # req.
        req = cmd_req_of(OEV8_CMD_TRADING_ASK_SELLING)
        req.trading_ask_selling.trd_id = str(123)
        req.trading_ask_selling.cust_id = str(456)
        req.trading_ask_selling.price = str(789)
        req.trading_ask_selling.qty = 1011
        req.trading_ask_selling.security_deposit_amt = str(1213)
        req.trading_ask_selling.option = OrderOption.FILL_OR_KILL.value

        (resp, _, _,) = self.__run(req, 'trading_ask_selling')

        #
        assert str(181818) == resp.trading_ask_selling.ord_id

        # verify mock
        ask_selling.assert_has_calls([
            call(trd_id=str(123),
                 cust_id=str(456),
                 price=789,
                 qty=1011,
                 security_deposit_amt=1213,
                 option=OrderOption.FILL_OR_KILL)
        ])

    def test_replaying_cmds(self):
        no_replaying_cmds = [
            OEV8_CMD_ENTER_MAINT, OEV8_CMD_LEAVE_MAINT,
            OEV8_CMD_SNAPSHOT, OEV8_CMD_SHUTDOWN,
            OEV8_CMD_SAVE_QUIT,
            # TODO: OEV8_CMD_LIST_TRADING_ID,
            # TODO: OEV8_CMD_COUNT_TRADING_ID,
            # TODO: OEV8_CMD_TRADING_INFO,
            # TODO: OEV8_CMD_LIST_ITEM_PROVIDING,
            # TODO: OEV8_CMD_COUNT_ITEM_PROVIDING,
            # TODO: OEV8_CMD_LIST_ORDER,
            # TODO: OEV8_CMD_COUNT_ORDER,
            # TODO: OEV8_CMD_LIST_MATCH,
            # TODO: OEV8_CMD_COUNT_MATCH,
            # TODO: OEV8_CMD_LIST_PRICE,
            # TODO: OEV8_CMD_COUNT_PRICE,
            # TODO: OEV8_CMD_LIST_ORDER_ID_BY_PRICE,
            # TODO: OEV8_CMD_COUNT_ORDER_ID_BY_PRICE,
        ]

        seq_num_svc = self.seq_num_service

        for no_replaying_cmd in no_replaying_cmds:
            before_seq_num = seq_num_svc.cur_val(SeqType.CMD_REQ)

            cmd = cmd_req_of(no_replaying_cmd)
            self.__run(cmd, None, True, True)

            after_seq_num = seq_num_svc.cur_val(SeqType.CMD_REQ)

            assert before_seq_num + 1 == after_seq_num

    def test_shutdown(self):
        cmd = cmd_req_of(OEV8_CMD_SHUTDOWN)

        # do it
        self.__run(cmd, None)

        # CHK: interaction with mocked service
        self.shutdown_service.shutdown.assert_called_once()

        self.event_writer.on_shutdown.assert_called_once()

    def test_snapshot(self):
        cmd = cmd_req_of(OEV8_CMD_SNAPSHOT)

        # do it
        self.__run(cmd, None, no_error=False)

        # CHK: interaction with mocked service
        self.snapshot_service.save.assert_called_once()

    def test_save_quit(self):
        cmd = cmd_req_of(OEV8_CMD_SAVE_QUIT)

        # do it
        self.__run(cmd, None)

        # CHK: interaction with mocked service
        self.shutdown_service.shutdown.assert_called_once()
        self.snapshot_service.save.assert_called_once()

        self.event_writer.on_snapshot.assert_called_once()
        self.event_writer.on_shutdown.assert_called_once()

    def test_ping(self):
        cmd = cmd_req_of(OEV8_CMD_PING)
        self.__run(cmd, None)

    @patch('time.sleep')
    def test_sleep(self, sleep_patch):
        cmd = cmd_req_of(OEV8_CMD_SLEEP)
        cmd.sys_sleep.seconds = 13

        # do it
        self.__run(cmd, None)

        # VERIFY: time.sleep
        sleep_patch.assert_has_calls([call(13)])

    def test_event_writer_and_journal_writer(self):
        # 요청 만들기.
        balance_type = rand_balance_type()
        curr = rand_curr()
        cust_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_BALANCE_GET)
        cmd.balance_get.balance_type = balance_type.value
        cmd.balance_get.curr = curr
        cmd.balance_get.cust_id = cust_id

        # record mock
        amt = rand_1mil()
        self.balance_service.get = MagicMock(side_effect=lambda *x, **y: amt)

        # 실행.
        (resp, _, _,) = self.__run(cmd, 'balance_get')

        # CHK: 응답 값.
        assert resp.balance_get.amt == str(amt)

        self.event_writer.clear_buffer.assert_has_calls([call()])  # only at starting.
        self.event_writer.set_current.assert_called()
        self.event_writer.commit_buffer.assert_called_once()

        self.journal_writer.write.assert_called_once()

    def test_event_writer_and_journal_writer__replaying(self):
        # 요청 만들기.
        balance_type = rand_balance_type()
        curr = rand_curr()
        cust_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_BALANCE_GET)
        cmd.balance_get.balance_type = balance_type.value
        cmd.balance_get.curr = curr
        cmd.balance_get.cust_id = cust_id

        # record mock
        amt = rand_1mil()
        self.balance_service.get = MagicMock(side_effect=lambda *x, **y: amt)

        # 실행.
        cmd.cmd_uuid = rand_cmd_uuid()
        req_bs = cmd.SerializeToString()
        req_len = len(req_bs)
        checksum = rand_1mil()
        resp_bs = self.cmd_handler.handle(
            req_len, checksum, req_bs, replaying=True)

        # CHK: 헤더.
        assert resp_bs[1]

        resp = Oev8_CommandResponse()
        resp.ParseFromString(resp_bs[0])

        assert resp.cmd_uuid == cmd.cmd_uuid
        assert resp.cmd_type == cmd.cmd_type
        assert int(resp.seq_num) >= 0

        #
        self.event_writer.set_current.assert_called()
        self.event_writer.commit_buffer.assert_not_called()

        self.journal_writer.write.assert_not_called()

    def __run_replaying_and_chk_seq(self, cmd):
        seq_num_svc = self.seq_num_service
        before_seq_num = seq_num_svc.cur_val(SeqType.CMD_REQ)

        self.cmd_uuid = rand_cmd_uuid()
        cmd.cmd_uuid = self.cmd_uuid
        req_bs = cmd.SerializeToString()
        req_len = len(req_bs)
        checksum = rand_1mil()

        resp_bs = self.cmd_handler.handle(
            req_len, checksum, req_bs, replaying=True)

        after_seq_num = seq_num_svc.cur_val(SeqType.CMD_REQ)
        assert before_seq_num + 1 == after_seq_num

        return resp_bs

    def test_enter_maint_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_ENTER_MAINT)
        self.__run_replaying_and_chk_seq(cmd)

    def test_leave_maint_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_LEAVE_MAINT)
        self.__run_replaying_and_chk_seq(cmd)

    def test_snapshot_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_SNAPSHOT)
        self.__run_replaying_and_chk_seq(cmd)

    def test_shutdown_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_SHUTDOWN)
        self.__run_replaying_and_chk_seq(cmd)

        self.shutdown_service.shutdown.assert_not_called()

    def test_save_quit_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_SAVE_QUIT)
        self.__run_replaying_and_chk_seq(cmd)

        self.shutdown_service.shutdown.assert_not_called()
        self.snapshot_service.save.assert_not_called()

    def test_ping_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_PING)
        self.__run_replaying_and_chk_seq(cmd)

    def test_sleep_replaying(self):
        sw = Stopwatch()

        cmd = cmd_req_of(OEV8_CMD_SLEEP)
        cmd.sys_sleep.seconds = 13

        with sw:
            self.__run_replaying_and_chk_seq(cmd)

        assert sw.timedelta < datetime.timedelta(seconds=1)

    def test_list_trading_id_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_LIST_TRADING_ID)
        cmd.trading_list_id.offset = 1
        cmd.trading_list_id.limit = 2
        self.__run_replaying_and_chk_seq(cmd)

    def test_count_trading_id_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_COUNT_TRADING_ID)
        self.__run_replaying_and_chk_seq(cmd)

    def test_trading_info_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_TRADING_INFO)
        cmd.trading_get_info.trd_id = str(123)
        self.__run_replaying_and_chk_seq(cmd)

    def test_auction_info_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_TRADING_AUCTION_INFO)
        cmd.trading_get_auction_info.trd_id = str(123)
        self.__run_replaying_and_chk_seq(cmd)

    def test_list_item_providing_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_LIST_ITEM_PROVIDING)
        cmd.trading_list_item_providing.trd_id = str(123)
        cmd.trading_list_item_providing.offset = 456
        cmd.trading_list_item_providing.limit = 789
        self.__run_replaying_and_chk_seq(cmd)

    def test_count_item_providing_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_COUNT_ITEM_PROVIDING)
        cmd.trading_count_item_providing.trd_id = str(123)
        self.__run_replaying_and_chk_seq(cmd)

    def test_list_order_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_LIST_ORDER)
        cmd.trading_list_order.trd_id = str(123)
        cmd.trading_list_order.offset = 456
        cmd.trading_list_order.limit = 789
        self.__run_replaying_and_chk_seq(cmd)

    def test_count_order_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_LIST_ORDER)
        cmd.trading_count_order.trd_id = str(123)
        self.__run_replaying_and_chk_seq(cmd)

    def test_list_match_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_LIST_MATCH)
        cmd.trading_list_match.trd_id = str(123)
        cmd.trading_list_match.offset = 456
        cmd.trading_list_match.limit = 789
        self.__run_replaying_and_chk_seq(cmd)

    def test_count_match_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_COUNT_MATCH)
        cmd.trading_count_match.trd_id = str(123)
        self.__run_replaying_and_chk_seq(cmd)

    def test_list_price_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_LIST_PRICE)
        cmd.trading_list_price.trd_id = str(123)
        cmd.trading_list_price.offset = 456
        cmd.trading_list_price.limit = 789
        self.__run_replaying_and_chk_seq(cmd)

    def test_count_price_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_COUNT_MATCH)
        cmd.trading_count_price.trd_id = str(123)
        self.__run_replaying_and_chk_seq(cmd)

    def test_list_order_id_by_price_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_LIST_ORDER_ID_BY_PRICE)
        cmd.trading_list_order_by_price.trd_id = str(123)
        cmd.trading_list_order_by_price.order_side = OrderSide.SELL.value
        cmd.trading_list_order_by_price.price = str(456)
        cmd.trading_list_order_by_price.offset = 78
        cmd.trading_list_order_by_price.limit = 90
        self.__run_replaying_and_chk_seq(cmd)

    def test_count_order_id_by_price_replaying(self):
        cmd = cmd_req_of(OEV8_CMD_COUNT_ORDER_ID_BY_PRICE)
        cmd.trading_count_order_by_price.trd_id = str(123)
        cmd.trading_count_order_by_price.order_side = OrderSide.SELL.value
        cmd.trading_count_order_by_price.price = str(456)
        self.__run_replaying_and_chk_seq(cmd)

    def test_event_writer_fail(self):
        # 요청 만들기.
        balance_type = rand_balance_type()
        curr = rand_curr()
        cust_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_BALANCE_GET)
        cmd.balance_get.balance_type = balance_type.value
        cmd.balance_get.curr = curr
        cmd.balance_get.cust_id = cust_id

        # record mock: balance_service
        amt = rand_1mil()
        self.balance_service.get = MagicMock(side_effect=EventWriterFail)

        # 실행: 그냥 event-writer 예외가 발생되면 그대로 위로 올리도록.
        with raises(EventWriterFail):
            (_, _, _,) = self.__run(cmd, 'balance_get')

        # CHK: journal-writer은 그대로 기록이 되어야한다 -- YES.
        self.journal_writer.write.assert_called_once()

    def test_joural_writer_fail(self):
        # 요청 만들기.
        balance_type = rand_balance_type()
        curr = rand_curr()
        cust_id = str(rand_1mil())

        cmd = cmd_req_of(OEV8_CMD_BALANCE_GET)
        cmd.balance_get.balance_type = balance_type.value
        cmd.balance_get.curr = curr
        cmd.balance_get.cust_id = cust_id

        # record mock: journal_writer
        self.journal_writer.write = MagicMock(side_effect=JournalWriterFail)

        # 실행: 그냥 journal-writer 예외가 발생되면 그대로 위로 올리도록.
        with raises(JournalWriterFail):
            (_, _, _,) = self.__run(cmd, 'balance_get')
