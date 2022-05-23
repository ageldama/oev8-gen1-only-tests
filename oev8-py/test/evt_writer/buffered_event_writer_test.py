"""BufferedEventWriter테스트."""
import random
from unittest.mock import Mock, MagicMock, call
from pytest import mark  # type:ignore
from oev8.values.event_writer import \
    BalanceDepositCause, BalanceWithdrawCause, \
    BalanceXferFromCause, BalanceXferToCause, \
    BalanceCvtXferToCause, \
    ItemCountIncCause, ItemCountDecCause, \
    ItemCountXferFromCause, ItemCountXferToCause, \
    TradingOrderCancelCause
from oev8.values.event_writer import \
    BalanceDepositCauseDeposit, BalanceWithdrawCauseWithdraw, \
    BalanceXferFromCauseBuying, BalanceXferFromCauseSecurityDeposit, \
    BalanceXferFromCauseBuyingAuction, \
    BalanceXferToCauseTradingCancellation, \
    BalanceXferToCauseRefundForUnmatchedLimitBuying, \
    BalanceCvtXferToCauseEarningPrep, \
    ItemCountXferFromCauseSelling, \
    ItemCountXferToCauseBuying, \
    TradingOrderCancelCauseFoK, \
    TradingOrderCancelCauseIoC, \
    TradingOrderCancelCauseNotEnoughBalance, \
    TradingOrderCancelCauseUserCancel
from oev8.svcs.event_writer.virtual import BufferedEventWriter
from test.testsup import rand_cmd_uuid, rand_1mil
from oev8.typedefs import BalanceType, OrderOption


KLASS = BufferedEventWriter

EVENT_WRITER_CASES = [
    (
        KLASS.on_snapshot,
        {},
    ),

    (
        KLASS.on_shutdown,
        {},
    ),

    (
        KLASS.on_entered_maint,
        {},
    ),

    (
        KLASS.on_left_maint,
        {},
    ),

    (
        KLASS.on_balance_deposit,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 123,
            'cust_id': '456',
            'amt': 789,
            'new_amt': 78613,
            'why': BalanceDepositCause(),
        },
    ),

    (
        KLASS.on_balance_deposit,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 123,
            'cust_id': '456',
            'amt': 789,
            'new_amt': 78613,
            'why': BalanceDepositCauseDeposit(deposit_request_id='1234'),
        },
    ),

    (
        KLASS.on_balance_withdraw,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 631,
            'cust_id': '378931',
            'amt': 3267,
            'new_amt': 789317861,
            'why': BalanceWithdrawCause(),
        },
    ),

    (
        KLASS.on_balance_withdraw,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 631,
            'cust_id': '378931',
            'amt': 3267,
            'new_amt': 789317861,
            'why': BalanceWithdrawCauseWithdraw(withdraw_request_id='7890'),
        },
    ),

    (
        KLASS.on_balance_xfer_from,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 631,
            'cust_id': '378931',
            'amt': 3267,
            'new_amt': 789317861,
            'new_svc': 38971897,
            'why': BalanceXferFromCause(),
        },
    ),

    (
        KLASS.on_balance_xfer_from,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 631,
            'cust_id': '378931',
            'amt': 3267,
            'new_amt': 789317861,
            'new_svc': 38971897,
            'why': BalanceXferFromCauseBuying(
                trd_id='1313', ord_id='1414'),
        },
    ),

    (
        KLASS.on_balance_xfer_from,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 631,
            'cust_id': '378931',
            'amt': 3267,
            'new_amt': 789317861,
            'new_svc': 38971897,
            'why': BalanceXferFromCauseSecurityDeposit(
                trd_id='1313'),
        },
    ),

    (
        KLASS.on_balance_xfer_from,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 631,
            'cust_id': '378931',
            'amt': 3267,
            'new_amt': 789317861,
            'new_svc': 38971897,
            'why': BalanceXferFromCauseBuyingAuction(
                trd_id='1313'),
        },
    ),

    (
        KLASS.on_balance_xfer_to,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 2,
            'cust_id': '378913987',
            'amt': 3671386731,
            'new_amt': 37681328763,
            'new_svc': 3789178931,
            'why': BalanceXferToCause()
        },
    ),

    (
        KLASS.on_balance_xfer_to,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 2,
            'cust_id': '378913987',
            'amt': 3671386731,
            'new_amt': 37681328763,
            'new_svc': 3789178931,
            'why': BalanceXferToCauseRefundForUnmatchedLimitBuying(
                trd_id='1717', ord_id=1818)
        },
    ),

    (
        KLASS.on_balance_xfer_to,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 2,
            'cust_id': '378913987',
            'amt': 3671386731,
            'new_amt': 37681328763,
            'new_svc': 3789178931,
            'why': BalanceXferToCauseTradingCancellation(trd_id='1717')
        },
    ),

    (
        KLASS.on_balance_cvt_xfer_to,
        {
            'from_balance_type': BalanceType.EARNING,
            'to_balance_type': BalanceType.BALANCE,
            'curr': 2,
            'cust_id': '378913987',
            'amt': 3671386731,
            'new_amt': 37681328763,
            'new_svc': 3789178931,
            'why': BalanceCvtXferToCause()
        },
    ),

    (
        KLASS.on_balance_cvt_xfer_to,
        {
            'from_balance_type': BalanceType.EARNING,
            'to_balance_type': BalanceType.BALANCE,
            'curr': 2,
            'cust_id': '378913987',
            'amt': 3671386731,
            'new_amt': 37681328763,
            'new_svc': 3789178931,
            'why': BalanceCvtXferToCauseEarningPrep(trd_id='1818')
        },
    ),

    (
        KLASS.on_balance_delete_by_currency,
        {
            'curr': 123,
        },
    ),

    (
        KLASS.on_balance_delete_by_customer,
        {
            'cust_id': '455',
        },
    ),

    (
        KLASS.on_item_count_inc,
        {
            'cust_id': '378913987',
            'trd_id': '38971327893',
            'qty': 78986757896,
            'new_qty': 8976879243,
            'why': ItemCountIncCause(),
        },
    ),

    (
        KLASS.on_item_count_dec,
        {
            'cust_id': '378913987',
            'trd_id': '38971327893',
            'qty': 78986757896,
            'new_qty': 8976879243,
            'why': ItemCountDecCause(),
        },
    ),

    (
        KLASS.on_item_count_xfer_from,
        {
            'cust_id': '378913987',
            'trd_id': '38971327893',
            'qty': 78986757896,
            'new_qty': 8976879243,
            'new_svc': 78651231132,
            'why': ItemCountXferFromCause(),
        },
    ),

    (
        KLASS.on_item_count_xfer_from,
        {
            'cust_id': '378913987',
            'trd_id': '38971327893',
            'qty': 78986757896,
            'new_qty': 8976879243,
            'new_svc': 78651231132,
            'why': ItemCountXferFromCauseSelling(ord_id=12345),
        },
    ),

    (
        KLASS.on_item_count_xfer_to,
        {
            'cust_id': '378913987',
            'trd_id': '38971327893',
            'qty': 78986757896,
            'new_qty': 8976879243,
            'new_svc': 78651231132,
            'why': ItemCountXferToCause(),
        },
    ),

    (
        KLASS.on_item_count_xfer_to,
        {
            'cust_id': '378913987',
            'trd_id': '38971327893',
            'qty': 78986757896,
            'new_qty': 8976879243,
            'new_svc': 78651231132,
            'why': ItemCountXferToCauseBuying(match_id=1818),
        },
    ),

    (
        KLASS.on_item_count_delete_by_trading,
        {
            'trd_id': '123',
        },
    ),

    (
        KLASS.on_item_count_delete_by_customer,
        {
            'cust_id': '476',
        },
    ),

    (
        KLASS.on_trading_new,
        {
            'trd_id': '6784',
        },
    ),

    (
        KLASS.on_trading_resume,
        {
            'trd_id': '123',
        },
    ),

    (
        KLASS.on_trading_pause,
        {
            'trd_id': '123',
        },
    ),

    (
        KLASS.on_trading_finalized,
        {
            'trd_id': '123',
        },
    ),

    (
        KLASS.on_trading_evicted,
        {
            'trd_id': '123',
        },
    ),

    (
        KLASS.on_trading_cancelled,
        {
            'trd_id': '123',
        },
    ),


    (
        KLASS.on_trading_order_matched,
        {
            't_cust_id': '123',
            'trd_id': '456',
            'm_ord_id': 789,
            't_ord_id': 1011,
            'match_id': 1213,
            'price': 1415,
            'qty': 1617,
        },
    ),

    (
        KLASS.on_trading_provide_item,
        {
            'cust_id': '123',
            'trd_id': '789',
            'qty': 1011,
            'new_qty': 1415,
        },
    ),

    (
        KLASS.on_trading_unprovide_item,
        {
            'cust_id': '123',
            'trd_id': '789',
            'decrease_qty': 1011,
            'new_qty': 1415,
        },
    ),

    (
        KLASS.on_trading_limit_sell_order,
        {
            'cust_id': '123',
            'trd_id': '456',
            'ord_id': 789,
            'price': 1011,
            'qty': 1213,
            'option': OrderOption.FILL_OR_KILL,
        },
    ),

    (
        KLASS.on_trading_limit_buy_order,
        {
            'cust_id': '123',
            'trd_id': '456',
            'ord_id': 789,
            'price': 1011,
            'qty': 1213,
            'option': OrderOption.IMMEDIATE_OR_CANCEL,
        },
    ),

    (
        KLASS.on_trading_market_sell_order,
        {
            'cust_id': '123',
            'trd_id': '456',
            'ord_id': 789,
            'qty': 1213,
            'option': OrderOption.FILL_OR_KILL,
        },
    ),

    (
        KLASS.on_trading_market_buy_order,
        {
            'cust_id': '123',
            'trd_id': '456',
            'ord_id': 789,
            'qty': 1213,
            'option': OrderOption.IMMEDIATE_OR_CANCEL,
        },
    ),

    (
        KLASS.on_trading_order_cancelled,
        {
            'cust_id': '123',
            'trd_id': '456',
            'ord_id': 789,
            'price': 1011,
            'qty': 1213,
            'remaining_qty': 1415,
            'why': TradingOrderCancelCause(),
        },
    ),

    (
        KLASS.on_trading_order_cancelled,
        {
            'cust_id': '123',
            'trd_id': '456',
            'ord_id': 789,
            'price': 1011,
            'qty': 1213,
            'remaining_qty': 1415,
            'why': TradingOrderCancelCauseUserCancel(),
        },
    ),

    (
        KLASS.on_trading_order_cancelled,
        {
            'cust_id': '123',
            'trd_id': '456',
            'ord_id': 789,
            'price': 1011,
            'qty': 1213,
            'remaining_qty': 1415,
            'why': TradingOrderCancelCauseNotEnoughBalance(),
        },
    ),

    (
        KLASS.on_trading_order_cancelled,
        {
            'cust_id': '123',
            'trd_id': '456',
            'ord_id': 789,
            'price': 1011,
            'qty': 1213,
            'remaining_qty': 1415,
            'why': TradingOrderCancelCauseFoK(),
        },
    ),

    (
        KLASS.on_trading_order_cancelled,
        {
            'cust_id': '123',
            'trd_id': '456',
            'ord_id': 789,
            'price': 1011,
            'qty': 1213,
            'remaining_qty': 1415,
            'why': TradingOrderCancelCauseIoC(),
        },
    ),
]


@mark.parametrize(
    "method,params,",
    EVENT_WRITER_CASES)
def test_buffered_event_writer(
        method, params,
        null_logging_stopwatch
):
    evt_writer = Mock()

    bew = BufferedEventWriter(
        delegate=evt_writer,
        logging_stopwatch=null_logging_stopwatch
    )

    #
    cmd_uuid = rand_cmd_uuid()
    seq_num = rand_1mil()

    bew.set_current(cmd_uuid, seq_num)
    method(bew, **params)

    method2 = getattr(evt_writer, method.__name__)
    assert method2

    # BEFORE
    evt_writer.set_current.assert_not_called()
    method2.assert_not_called()

    # COMMIT
    bew.commit_buffer()

    # AFTER
    evt_writer.set_current.assert_has_calls([
        call(cmd_uuid, seq_num)
    ])

    evt_writer.commit_buffer.assert_called_once()

    method2.assert_has_calls([call(**params)])

    null_logging_stopwatch.__enter__.assert_called()
    null_logging_stopwatch.__exit__.assert_called()

    # RESET MOCKS
    evt_writer.set_current.reset_mock()
    method2.reset_mock()

    # hope it's gone after commit. (no commit twice)
    bew.commit_buffer()
    evt_writer.set_current.assert_not_called()
    method2.assert_not_called()

    # do it again
    bew.set_current(cmd_uuid, seq_num)
    method(bew, **params)

    # ROLLBACK
    bew.clear_buffer()

    # no effects
    evt_writer.set_current.assert_not_called()
    method2.assert_not_called()


@mark.parametrize('execution_number', range(5))
def test_buffered_event_writer__multiple(
        execution_number,
        null_logging_stopwatch
):
    n_items = random.randint(0, len(EVENT_WRITER_CASES) + 1)

    items = []
    for _ in range(n_items):
        items.append(random.choice(EVENT_WRITER_CASES))


    evt_writer = Mock()
    bew = BufferedEventWriter(
        delegate=evt_writer,
        logging_stopwatch=null_logging_stopwatch
    )

    #
    cmd_uuid = rand_cmd_uuid()
    seq_num = rand_1mil()

    bew.set_current(cmd_uuid, seq_num)

    for item in items:
        (method, params,) = item
        method(bew, **params)

    # COMMIT
    bew.commit_buffer()

    # AFTER
    evt_writer.set_current.assert_has_calls([
        call(cmd_uuid, seq_num)
    ])

    for item in items:
        (method, params,) = item

        method2 = getattr(evt_writer, method.__name__)
        assert method2

        method2.assert_has_calls([call(**params)])


def test_buffered_event_writer__inorder(
        null_logging_stopwatch
):
    items = [
        EVENT_WRITER_CASES[0],
        EVENT_WRITER_CASES[5],
        EVENT_WRITER_CASES[7],
        EVENT_WRITER_CASES[12],
    ]

    evt_writer = Mock()
    bew = BufferedEventWriter(
        delegate=evt_writer,
        logging_stopwatch=null_logging_stopwatch)

    #
    cmd_uuid = rand_cmd_uuid()
    seq_num = rand_1mil()

    bew.set_current(cmd_uuid, seq_num)

    for item in items:
        (method, params,) = item
        method(bew, **params)

    # COMMIT
    bew.commit_buffer()

    # AFTER
    evt_writer.set_current.assert_has_calls([
        call(cmd_uuid, seq_num)
    ])

    expected_calls = [
        call.on_snapshot(),
        call.on_balance_deposit(amt=789,
                                balance_type=BalanceType.EARNING,
                                curr=123,
                                cust_id='456',
                                new_amt=78613,
                                why=BalanceDepositCauseDeposit(
                                    deposit_request_id='1234')),
        call.on_balance_withdraw(amt=3267,
                                 balance_type=BalanceType.EARNING,
                                 curr=631,
                                 cust_id='378931',
                                 new_amt=789317861,
                                 why=BalanceWithdrawCauseWithdraw(
                                     withdraw_request_id='7890')),
        call.on_balance_xfer_to(amt=3671386731,
                                balance_type=BalanceType.EARNING,
                                curr=2, cust_id='378913987',
                                new_amt=37681328763, new_svc=3789178931,
                                why=BalanceXferToCause()),
        call.commit_buffer()
    ]

    assert expected_calls == evt_writer.mock_calls[1:]



@mark.parametrize(
    "method,params,",
    EVENT_WRITER_CASES)
def test_buffered_event_writer__clear_buffer(
        method, params,
        null_logging_stopwatch
):
    evt_writer = Mock()

    bew = BufferedEventWriter(
        delegate=evt_writer,
        logging_stopwatch=null_logging_stopwatch
    )

    #
    cmd_uuid = rand_cmd_uuid()
    seq_num = rand_1mil()

    bew.set_current(cmd_uuid, seq_num)
    method(bew, **params)

    method2 = getattr(evt_writer, method.__name__)
    assert method2

    # BEFORE
    evt_writer.set_current.assert_not_called()
    method2.assert_not_called()

    # ROLLBACK
    bew.clear_buffer()

    # AFTER
    evt_writer.commit_buffer.assert_not_called()
    evt_writer.rollback_buffer.assert_not_called()

    method2.assert_not_called()

    null_logging_stopwatch.__enter__.assert_not_called()
    null_logging_stopwatch.__exit__.assert_not_called()

    # RESET MOCKS
    evt_writer.set_current.reset_mock()
    method2.reset_mock()

    # hope it's gone after commit. (no commit twice)
    bew.commit_buffer()
    evt_writer.set_current.assert_not_called()
    method2.assert_not_called()

    # do it again
    bew.set_current(cmd_uuid, seq_num)
    method(bew, **params)

    # ROLLBACK
    bew.clear_buffer()

    # no effects
    evt_writer.set_current.assert_not_called()
    method2.assert_not_called()
