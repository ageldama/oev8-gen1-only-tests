"""ProtobufEventWriter테스트."""
from unittest.mock import Mock, MagicMock
from pytest import mark  # type:ignore
import magicattr
from oev8_pb2 import Oev8_Event, \
    OEV8_EVT_SNAPSHOT, OEV8_EVT_SHUTDOWN, \
    OEV8_EVT_ENTER_MAINT, OEV8_EVT_LEAVE_MAINT, \
    OEV8_EVT_BALANCE_DEPOSIT, \
    OEV8_EVT_BALANCE_WITHDRAW, \
    OEV8_EVT_BALANCE_XFER_FROM, \
    OEV8_EVT_BALANCE_XFER_TO, \
    OEV8_EVT_BALANCE_CVT_XFER_TO, \
    OEV8_EVT_BALANCE_DELETE_BY_CURRENCY, \
    OEV8_EVT_BALANCE_DELETE_BY_CUSTOMER, \
    OEV8_EVT_ITEM_COUNT_INC, \
    OEV8_EVT_ITEM_COUNT_DEC, \
    OEV8_EVT_ITEM_COUNT_XFER_FROM, \
    OEV8_EVT_ITEM_COUNT_XFER_TO, \
    OEV8_EVT_ITEM_COUNT_DELETE_BY_TRADING, \
    OEV8_EVT_ITEM_COUNT_DELETE_BY_CUSTOMER, \
    OEV8_EVT_TRADING_NEW, \
    OEV8_EVT_TRADING_RESUME, \
    OEV8_EVT_TRADING_PAUSE, \
    OEV8_EVT_TRADING_FINALIZED, \
    OEV8_EVT_TRADING_EVICTED, \
    OEV8_EVT_TRADING_CANCELLED, \
    OEV8_EVT_TRADING_ORDER_MATCHED, \
    OEV8_EVT_TRADING_PROVIDE_ITEM, \
    OEV8_EVT_TRADING_UNPROVIDE_ITEM, \
    OEV8_EVT_TRADING_ORDER_LIMIT_SELL, \
    OEV8_EVT_TRADING_ORDER_LIMIT_BUY, \
    OEV8_EVT_TRADING_ORDER_MARKET_SELL, \
    OEV8_EVT_TRADING_ORDER_MARKET_BUY, \
    OEV8_EVT_TRADING_ORDER_CANCEL_REMAINING
from oev8_pb2 import OEV8_EVT_CAUSE_NONE, \
    OEV8_EVT_CAUSE_ADMIN, \
    OEV8_EVT_CAUSE_BALANCE_DEPOSIT_DEPOSIT, \
    OEV8_EVT_CAUSE_BALANCE_WITHDRAW_WITHDRAW, \
    OEV8_EVT_CAUSE_BALANCE_XFER_FROM_BUYING, \
    OEV8_EVT_CAUSE_BALANCE_XFER_FROM_SECURITY_DEPOSIT, \
    OEV8_EVT_CAUSE_BALANCE_XFER_FROM_BUYING_AUCTION, \
    OEV8_EVT_CAUSE_BALANCE_XFER_TO_CANCEL_TRADING, \
    OEV8_EVT_CAUSE_BALANCE_XFER_TO_REFUND_UNMATCHED_LIMIT_BUY, \
    OEV8_EVT_CAUSE_BALANCE_CVT_XFER_TO_EARNING_PREP, \
    OEV8_EVT_CAUSE_ITEM_COUNT_XFER_FROM_SELLING, \
    OEV8_EVT_CAUSE_ITEM_COUNT_XFER_FROM_SELLING_AUCTION, \
    OEV8_EVT_CAUSE_ITEM_COUNT_XFER_TO_BUYING, \
    OEV8_EVT_CAUSE_TRADING_ORDER_CANCEL_FOK, \
    OEV8_EVT_CAUSE_TRADING_ORDER_CANCEL_IOC, \
    OEV8_EVT_CAUSE_TRADING_ORDER_CANCEL_NOT_ENOUGH_BALANCE, \
    OEV8_EVT_CAUSE_TRADING_ORDER_CANCEL_USER_CANCEL, \
    OEV8_EVT_CAUSE_TRADING_ORDER_CANCEL_TIMED_OUT
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
    ItemCountXferFromCauseSellingAuction, \
    ItemCountXferToCauseBuying, \
    TradingOrderCancelCauseFoK, \
    TradingOrderCancelCauseIoC, \
    TradingOrderCancelCauseNotEnoughBalance, \
    TradingOrderCancelCauseUserCancel, \
    TradingOrderCancelCauseTimedOut
from oev8.svcs.event_writer.protobuf import ProtoBufEventWriter
from test.testsup import rand_cmd_uuid, rand_1mil
from oev8.typedefs import BalanceType, OrderOption


KLASS = ProtoBufEventWriter

EVENT_WRITER_CASES = [
    (
        OEV8_EVT_SNAPSHOT,
        KLASS.on_snapshot,
        {},
        {
            'evt_cause_type': OEV8_EVT_CAUSE_ADMIN,
        },
    ),

    (
        OEV8_EVT_SHUTDOWN,
        KLASS.on_shutdown,
        {},
        {
            'evt_cause_type': OEV8_EVT_CAUSE_ADMIN,
        },
    ),

    (
        OEV8_EVT_ENTER_MAINT,
        KLASS.on_entered_maint,
        {},
        {
            'evt_cause_type': OEV8_EVT_CAUSE_ADMIN,
        },
    ),

    (
        OEV8_EVT_LEAVE_MAINT,
        KLASS.on_left_maint,
        {},
        {
            'evt_cause_type': OEV8_EVT_CAUSE_ADMIN,
        },
    ),

    (
        OEV8_EVT_BALANCE_DEPOSIT,
        KLASS.on_balance_deposit,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 123,
            'cust_id': str(456),
            'amt': 789,
            'new_amt': 78613,
            'why': BalanceDepositCause(),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'balance_deposit.balance_type': BalanceType.EARNING.value,
            'balance_deposit.curr': 123,
            'balance_deposit.cust_id': str(456),
            'balance_deposit.amt': str(789),
            'balance_deposit.new_amt': str(78613),
        },
    ),

    (
        OEV8_EVT_BALANCE_DEPOSIT,
        KLASS.on_balance_deposit,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 123,
            'cust_id': str(456),
            'amt': 789,
            'new_amt': 78613,
            'why': BalanceDepositCauseDeposit(deposit_request_id=str(1234)),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_BALANCE_DEPOSIT_DEPOSIT,
            'balance_deposit.balance_type': BalanceType.EARNING.value,
            'balance_deposit.curr': 123,
            'balance_deposit.cust_id': str(456),
            'balance_deposit.amt': str(789),
            'balance_deposit.new_amt': str(78613),
            'balance_deposit.deposit.deposit_req_id': str(1234),
        },
    ),

    (
        OEV8_EVT_BALANCE_WITHDRAW,
        KLASS.on_balance_withdraw,
        # Params
        {
            'balance_type': BalanceType.EARNING,
            'curr': 631,
            'cust_id': str(378931),
            'amt': 3267,
            'new_amt': 789317861,
            'why': BalanceWithdrawCause(),
        },
        # Result
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'balance_withdraw.balance_type': BalanceType.EARNING.value,
            'balance_withdraw.curr': 631,
            'balance_withdraw.cust_id': str(378931),
            'balance_withdraw.amt': str(3267),
            'balance_withdraw.new_amt': str(789317861),
        }
    ),

    (
        OEV8_EVT_BALANCE_WITHDRAW,
        KLASS.on_balance_withdraw,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 631,
            'cust_id': str(378931),
            'amt': 3267,
            'new_amt': 789317861,
            'why': BalanceWithdrawCauseWithdraw(withdraw_request_id=str(7890)),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_BALANCE_WITHDRAW_WITHDRAW,
            'balance_withdraw.balance_type': BalanceType.EARNING.value,
            'balance_withdraw.curr': 631,
            'balance_withdraw.cust_id': str(378931),
            'balance_withdraw.amt': str(3267),
            'balance_withdraw.new_amt': str(789317861),
            'balance_withdraw.withdraw.withdraw_req_id': str(7890),
        }
    ),

    (
        OEV8_EVT_BALANCE_XFER_FROM,
        KLASS.on_balance_xfer_from,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 631,
            'cust_id': str(378931),
            'amt': 3267,
            'new_amt': 789317861,
            'new_svc': 38971897,
            'why': BalanceXferFromCause(),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'balance_xfer_from.balance_type': BalanceType.EARNING.value,
            'balance_xfer_from.curr': 631,
            'balance_xfer_from.cust_id': str(378931),
            'balance_xfer_from.new_amt': str(789317861),
            'balance_xfer_from.new_svc': str(38971897)
        }
    ),

    (
        OEV8_EVT_BALANCE_XFER_FROM,
        KLASS.on_balance_xfer_from,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 631,
            'cust_id': str(378931),
            'amt': 3267,
            'new_amt': 789317861,
            'new_svc': 38971897,
            'why': BalanceXferFromCauseBuying(
                trd_id=str(1313), ord_id=1414),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_BALANCE_XFER_FROM_BUYING,
            'balance_xfer_from.balance_type': BalanceType.EARNING.value,
            'balance_xfer_from.curr': 631,
            'balance_xfer_from.cust_id': str(378931),
            'balance_xfer_from.new_amt': str(789317861),
            'balance_xfer_from.new_svc': str(38971897),
            'balance_xfer_from.buying.trd_id': str(1313),
            'balance_xfer_from.buying.ord_id': str(1414),
        }
    ),

    (
        OEV8_EVT_BALANCE_XFER_FROM,
        KLASS.on_balance_xfer_from,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 631,
            'cust_id': str(378931),
            'amt': 3267,
            'new_amt': 789317861,
            'new_svc': 38971897,
            'why': BalanceXferFromCauseSecurityDeposit(
                trd_id=str(1313)),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_BALANCE_XFER_FROM_SECURITY_DEPOSIT,
            'balance_xfer_from.balance_type': BalanceType.EARNING.value,
            'balance_xfer_from.curr': 631,
            'balance_xfer_from.cust_id': str(378931),
            'balance_xfer_from.new_amt': str(789317861),
            'balance_xfer_from.new_svc': str(38971897),
            'balance_xfer_from.sec_deposit.trd_id': str(1313),
        }
    ),

    (
        OEV8_EVT_BALANCE_XFER_FROM,
        KLASS.on_balance_xfer_from,
        {
            'balance_type': BalanceType.EARNING,
            'curr': 631,
            'cust_id': str(378931),
            'amt': 3267,
            'new_amt': 789317861,
            'new_svc': 38971897,
            'why': BalanceXferFromCauseBuyingAuction(
                trd_id=str(1313)),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_BALANCE_XFER_FROM_BUYING_AUCTION,
            'balance_xfer_from.balance_type': BalanceType.EARNING.value,
            'balance_xfer_from.curr': 631,
            'balance_xfer_from.cust_id': str(378931),
            'balance_xfer_from.new_amt': str(789317861),
            'balance_xfer_from.new_svc': str(38971897),
            'balance_xfer_from.buying_auction.trd_id': str(1313),
        }
    ),

    (
        OEV8_EVT_BALANCE_XFER_TO,
        KLASS.on_balance_xfer_to,
        # Params
        {
            'balance_type': BalanceType.EARNING,
            'curr': 2,
            'cust_id': str(378913987),
            'amt': 3671386731,
            'new_amt': 37681328763,
            'new_svc': 3789178931,
            'why': BalanceXferToCause()
        },
        # Result
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'balance_xfer_to.balance_type': BalanceType.EARNING.value,
            'balance_xfer_to.curr': 2,
            'balance_xfer_to.cust_id': str(378913987),
            'balance_xfer_to.new_amt': str(37681328763),
            'balance_xfer_to.new_svc': str(3789178931),
        }
    ),

    (
        OEV8_EVT_BALANCE_XFER_TO,
        KLASS.on_balance_xfer_to,
        # Params
        {
            'balance_type': BalanceType.EARNING,
            'curr': 2,
            'cust_id': str(378913987),
            'amt': 3671386731,
            'new_amt': 37681328763,
            'new_svc': 3789178931,
            'why': BalanceXferToCauseRefundForUnmatchedLimitBuying(
                trd_id=str(1717), ord_id=1818)
        },
        # Result
        {
            'evt_cause_type': OEV8_EVT_CAUSE_BALANCE_XFER_TO_REFUND_UNMATCHED_LIMIT_BUY,
            'balance_xfer_to.balance_type': BalanceType.EARNING.value,
            'balance_xfer_to.curr': 2,
            'balance_xfer_to.cust_id': str(378913987),
            'balance_xfer_to.new_amt': str(37681328763),
            'balance_xfer_to.new_svc': str(3789178931),
            'balance_xfer_to.refund_for_unmatched_buying.trd_id': str(1717),
            'balance_xfer_to.refund_for_unmatched_buying.ord_id': str(1818),
        }
    ),

    (
        OEV8_EVT_BALANCE_XFER_TO,
        KLASS.on_balance_xfer_to,
        # Params
        {
            'balance_type': BalanceType.EARNING,
            'curr': 2,
            'cust_id': str(378913987),
            'amt': 3671386731,
            'new_amt': 37681328763,
            'new_svc': 3789178931,
            'why': BalanceXferToCauseTradingCancellation(trd_id=str(1717))
        },
        # Result
        {
            'evt_cause_type': OEV8_EVT_CAUSE_BALANCE_XFER_TO_CANCEL_TRADING,
            'balance_xfer_to.balance_type': BalanceType.EARNING.value,
            'balance_xfer_to.curr': 2,
            'balance_xfer_to.cust_id': str(378913987),
            'balance_xfer_to.new_amt': str(37681328763),
            'balance_xfer_to.new_svc': str(3789178931),
            'balance_xfer_to.trading_cancellation.trd_id': str(1717),
        }
    ),

    (
        OEV8_EVT_BALANCE_CVT_XFER_TO,
        KLASS.on_balance_cvt_xfer_to,
        {
            'from_balance_type': BalanceType.EARNING,
            'to_balance_type': BalanceType.BALANCE,
            'curr': 2,
            'cust_id': str(378913987),
            'amt': 3671386731,
            'new_amt': 37681328763,
            'new_svc': 3789178931,
            'why': BalanceCvtXferToCause()
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'balance_cvt_xfer_to.from_balance_type': BalanceType.EARNING.value,
            'balance_cvt_xfer_to.to_balance_type': BalanceType.BALANCE.value,
            'balance_cvt_xfer_to.curr': 2,
            'balance_cvt_xfer_to.cust_id': str(378913987),
            'balance_cvt_xfer_to.new_amt': str(37681328763),
            'balance_cvt_xfer_to.new_svc': str(3789178931),
        }
    ),

    (
        OEV8_EVT_BALANCE_CVT_XFER_TO,
        KLASS.on_balance_cvt_xfer_to,
        {
            'from_balance_type': BalanceType.EARNING,
            'to_balance_type': BalanceType.BALANCE,
            'curr': 2,
            'cust_id': str(378913987),
            'amt': 3671386731,
            'new_amt': 37681328763,
            'new_svc': 3789178931,
            'why': BalanceCvtXferToCauseEarningPrep(trd_id=str(1818))
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_BALANCE_CVT_XFER_TO_EARNING_PREP,
            'balance_cvt_xfer_to.from_balance_type': BalanceType.EARNING.value,
            'balance_cvt_xfer_to.to_balance_type': BalanceType.BALANCE.value,
            'balance_cvt_xfer_to.curr': 2,
            'balance_cvt_xfer_to.cust_id': str(378913987),
            'balance_cvt_xfer_to.new_amt': str(37681328763),
            'balance_cvt_xfer_to.new_svc': str(3789178931),
            'balance_cvt_xfer_to.earning_prep.trd_id': str(1818),
        }
    ),

    (
        OEV8_EVT_BALANCE_DELETE_BY_CURRENCY,
        KLASS.on_balance_delete_by_currency,
        {
            'curr': 123,
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'balance_delete_by_currency.curr': 123,
        }
    ),

    (
        OEV8_EVT_BALANCE_DELETE_BY_CUSTOMER,
        KLASS.on_balance_delete_by_customer,
        {
            'cust_id': str(455),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'balance_delete_by_customer.cust_id': str(455),
        }
    ),

    (
        OEV8_EVT_ITEM_COUNT_INC,
        KLASS.on_item_count_inc,
        {
            'cust_id': str(378913987),
            'trd_id': str(38971327893),
            'qty': 78986757896,
            'new_qty': 8976879243,
            'why': ItemCountIncCause(),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'item_count_inc.cust_id': str(378913987),
            'item_count_inc.trd_id': str(38971327893),
            'item_count_inc.qty': 78986757896,
            'item_count_inc.new_qty': 8976879243,
        }
    ),

    (
        OEV8_EVT_ITEM_COUNT_DEC,
        KLASS.on_item_count_dec,
        {
            'cust_id': str(378913987),
            'trd_id': str(38971327893),
            'qty': 78986757896,
            'new_qty': 8976879243,
            'why': ItemCountDecCause(),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'item_count_dec.cust_id': str(378913987),
            'item_count_dec.trd_id': str(38971327893),
            'item_count_dec.qty': 78986757896,
            'item_count_dec.new_qty': 8976879243,
        }
    ),

    (
        OEV8_EVT_ITEM_COUNT_XFER_FROM,
        KLASS.on_item_count_xfer_from,
        {
            'cust_id': str(378913987),
            'trd_id': str(38971327893),
            'qty': 78986757896,
            'new_qty': 8976879243,
            'new_svc': 78651231132,
            'why': ItemCountXferFromCause(),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'item_count_xfer_from.cust_id': str(378913987),
            'item_count_xfer_from.trd_id': str(38971327893),
            'item_count_xfer_from.qty': 78986757896,
            'item_count_xfer_from.new_qty': 8976879243,
            'item_count_xfer_from.new_svc': 78651231132,
        }
    ),

    (
        OEV8_EVT_ITEM_COUNT_XFER_FROM,
        KLASS.on_item_count_xfer_from,
        {
            'cust_id': str(378913987),
            'trd_id': str(38971327893),
            'qty': 78986757896,
            'new_qty': 8976879243,
            'new_svc': 78651231132,
            'why': ItemCountXferFromCauseSelling(ord_id=12345),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_ITEM_COUNT_XFER_FROM_SELLING,
            'item_count_xfer_from.cust_id': str(378913987),
            'item_count_xfer_from.trd_id': str(38971327893),
            'item_count_xfer_from.qty': 78986757896,
            'item_count_xfer_from.new_qty': 8976879243,
            'item_count_xfer_from.new_svc': 78651231132,
            'item_count_xfer_from.selling.ord_id': str(12345),
        }
    ),

    (
        OEV8_EVT_ITEM_COUNT_XFER_FROM,
        KLASS.on_item_count_xfer_from,
        {
            'cust_id': str(378913987),
            'trd_id': str(38971327893),
            'qty': 78986757896,
            'new_qty': 8976879243,
            'new_svc': 78651231132,
            'why': ItemCountXferFromCauseSellingAuction(),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_ITEM_COUNT_XFER_FROM_SELLING_AUCTION,
            'item_count_xfer_from.cust_id': str(378913987),
            'item_count_xfer_from.trd_id': str(38971327893),
            'item_count_xfer_from.qty': 78986757896,
            'item_count_xfer_from.new_qty': 8976879243,
            'item_count_xfer_from.new_svc': 78651231132,
        }
    ),

    (
        OEV8_EVT_ITEM_COUNT_XFER_TO,
        KLASS.on_item_count_xfer_to,
        {
            'cust_id': str(378913987),
            'trd_id': str(38971327893),
            'qty': 78986757896,
            'new_qty': 8976879243,
            'new_svc': 78651231132,
            'why': ItemCountXferToCause(),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'item_count_xfer_to.cust_id': str(378913987),
            'item_count_xfer_to.trd_id': str(38971327893),
            'item_count_xfer_to.qty': 78986757896,
            'item_count_xfer_to.new_qty': 8976879243,
            'item_count_xfer_to.new_svc': 78651231132,
        }
    ),

    (
        OEV8_EVT_ITEM_COUNT_XFER_TO,
        KLASS.on_item_count_xfer_to,
        {
            'cust_id': str(378913987),
            'trd_id': str(38971327893),
            'qty': 78986757896,
            'new_qty': 8976879243,
            'new_svc': 78651231132,
            'why': ItemCountXferToCauseBuying(match_id=1818),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_ITEM_COUNT_XFER_TO_BUYING,
            'item_count_xfer_to.cust_id': str(378913987),
            'item_count_xfer_to.trd_id': str(38971327893),
            'item_count_xfer_to.qty': 78986757896,
            'item_count_xfer_to.new_qty': 8976879243,
            'item_count_xfer_to.new_svc': 78651231132,
            'item_count_xfer_to.buying.match_id': str(1818),
        }
    ),

    (
        OEV8_EVT_ITEM_COUNT_DELETE_BY_TRADING,
        KLASS.on_item_count_delete_by_trading,
        {
            'trd_id': str(123),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'item_count_delete_by_trading.trd_id': str(123),
        }
    ),

    (
        OEV8_EVT_ITEM_COUNT_DELETE_BY_CUSTOMER,
        KLASS.on_item_count_delete_by_customer,
        {
            'cust_id': str(476),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'item_count_delete_by_customer.cust_id': str(476),
        }
    ),

    (
        OEV8_EVT_TRADING_NEW,
        KLASS.on_trading_new,
        {
            'trd_id': str(6784),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'trading_new.trd_id': str(6784),
        },
    ),

    (
        OEV8_EVT_TRADING_RESUME,
        KLASS.on_trading_resume,
        {
            'trd_id': str(123),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'trading_resume.trd_id': str(123),
        }
    ),

    (
        OEV8_EVT_TRADING_PAUSE,
        KLASS.on_trading_pause,
        {
            'trd_id': str(123),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'trading_pause.trd_id': str(123),
        }
    ),

    (
        OEV8_EVT_TRADING_FINALIZED,
        KLASS.on_trading_finalized,
        {
            'trd_id': str(123),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'trading_finalized.trd_id': str(123),
        }
    ),

    (
        OEV8_EVT_TRADING_EVICTED,
        KLASS.on_trading_evicted,
        {
            'trd_id': str(123),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'trading_evicted.trd_id': str(123),
        }
    ),

    (
        OEV8_EVT_TRADING_CANCELLED,
        KLASS.on_trading_cancelled,
        {
            'trd_id': str(123),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'trading_cancelled.trd_id': str(123),
        }
    ),


    (
        OEV8_EVT_TRADING_ORDER_MATCHED,
        KLASS.on_trading_order_matched,
        {
            't_cust_id': str(123),
            'trd_id': str(456),
            'm_ord_id': 789,
            't_ord_id': 1011,
            'match_id': 1213,
            'price': 1415,
            'qty': 1617,
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'trading_order_matched.t_cust_id': str(123),
            'trading_order_matched.trd_id': str(456),
            'trading_order_matched.m_ord_id': str(789),
            'trading_order_matched.t_ord_id': str(1011),
            'trading_order_matched.match_id': str(1213),
            'trading_order_matched.price': str(1415),
            'trading_order_matched.qty': 1617,
        },
    ),

    (
        OEV8_EVT_TRADING_PROVIDE_ITEM,
        KLASS.on_trading_provide_item,
        {
            'cust_id': str(123),
            'trd_id': str(789),
            'qty': 1011,
            'new_qty': 1415,
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'trading_provide_item.cust_id': str(123),
            'trading_provide_item.trd_id': str(789),
            'trading_provide_item.qty': 1011,
            'trading_provide_item.new_qty': 1415,
        },
    ),

    (
        OEV8_EVT_TRADING_UNPROVIDE_ITEM,
        KLASS.on_trading_unprovide_item,
        {
            'cust_id': str(123),
            'trd_id': str(789),
            'decrease_qty': 1011,
            'new_qty': 1415,
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'trading_unprovide_item.cust_id': str(123),
            'trading_unprovide_item.trd_id': str(789),
            'trading_unprovide_item.qty': 1011,
            'trading_unprovide_item.new_qty': 1415,
        },
    ),

    (
        OEV8_EVT_TRADING_ORDER_LIMIT_SELL,
        KLASS.on_trading_limit_sell_order,
        {
            'cust_id': str(123),
            'trd_id': str(456),
            'ord_id': 789,
            'price': 1011,
            'qty': 1213,
            'option': OrderOption.FILL_OR_KILL,
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'trading_order_limit_sell.cust_id': str(123),
            'trading_order_limit_sell.trd_id': str(456),
            'trading_order_limit_sell.ord_id': str(789),
            'trading_order_limit_sell.price': str(1011),
            'trading_order_limit_sell.qty': 1213,
            'trading_order_limit_sell.option': OrderOption.FILL_OR_KILL.value,
        },
    ),

    (
        OEV8_EVT_TRADING_ORDER_LIMIT_BUY,
        KLASS.on_trading_limit_buy_order,
        {
            'cust_id': str(123),
            'trd_id': str(456),
            'ord_id': 789,
            'price': 1011,
            'qty': 1213,
            'option': OrderOption.IMMEDIATE_OR_CANCEL,
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'trading_order_limit_buy.cust_id': str(123),
            'trading_order_limit_buy.trd_id': str(456),
            'trading_order_limit_buy.ord_id': str(789),
            'trading_order_limit_buy.price': str(1011),
            'trading_order_limit_buy.qty': 1213,
            'trading_order_limit_buy.option': \
            OrderOption.IMMEDIATE_OR_CANCEL.value,
        },
    ),

    (
        OEV8_EVT_TRADING_ORDER_MARKET_SELL,
        KLASS.on_trading_market_sell_order,
        {
            'cust_id': str(123),
            'trd_id': str(456),
            'ord_id': 789,
            'qty': 1213,
            'option': OrderOption.FILL_OR_KILL,
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'trading_order_market_sell.cust_id': str(123),
            'trading_order_market_sell.trd_id': str(456),
            'trading_order_market_sell.ord_id': str(789),
            'trading_order_market_sell.qty': 1213,
            'trading_order_market_sell.option': OrderOption.FILL_OR_KILL.value,
        },
    ),

    (
        OEV8_EVT_TRADING_ORDER_MARKET_BUY,
        KLASS.on_trading_market_buy_order,
        {
            'cust_id': str(123),
            'trd_id': str(456),
            'ord_id': 789,
            'qty': 1213,
            'option': OrderOption.IMMEDIATE_OR_CANCEL,
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'trading_order_market_buy.cust_id': str(123),
            'trading_order_market_buy.trd_id': str(456),
            'trading_order_market_buy.ord_id': str(789),
            'trading_order_market_buy.qty': 1213,
            'trading_order_market_buy.option': \
            OrderOption.IMMEDIATE_OR_CANCEL.value,
        },
    ),

    (
        OEV8_EVT_TRADING_ORDER_CANCEL_REMAINING,
        KLASS.on_trading_order_cancelled,
        {
            'cust_id': str(123),
            'trd_id': str(456),
            'ord_id': 789,
            'price': 1011,
            'qty': 1213,
            'remaining_qty': 1415,
            'why': TradingOrderCancelCause(),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_NONE,
            'trading_order_cancelled.cust_id': str(123),
            'trading_order_cancelled.trd_id': str(456),
            'trading_order_cancelled.ord_id': str(789),
            'trading_order_cancelled.price': str(1011),
            'trading_order_cancelled.qty': 1213,
            'trading_order_cancelled.remaining_qty': 1415,
        }
    ),

    (
        OEV8_EVT_TRADING_ORDER_CANCEL_REMAINING,
        KLASS.on_trading_order_cancelled,
        {
            'cust_id': str(123),
            'trd_id': str(456),
            'ord_id': 789,
            'price': 1011,
            'qty': 1213,
            'remaining_qty': 1415,
            'why': TradingOrderCancelCauseUserCancel(),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_TRADING_ORDER_CANCEL_USER_CANCEL,
            'trading_order_cancelled.cust_id': str(123),
            'trading_order_cancelled.trd_id': str(456),
            'trading_order_cancelled.ord_id': str(789),
            'trading_order_cancelled.price': str(1011),
            'trading_order_cancelled.qty': 1213,
            'trading_order_cancelled.remaining_qty': 1415,
            'trading_order_cancelled.user_cancel.ok': True,
        }
    ),

    (
        OEV8_EVT_TRADING_ORDER_CANCEL_REMAINING,
        KLASS.on_trading_order_cancelled,
        {
            'cust_id': str(123),
            'trd_id': str(456),
            'ord_id': 789,
            'price': 1011,
            'qty': 1213,
            'remaining_qty': 1415,
            'why': TradingOrderCancelCauseNotEnoughBalance(),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_TRADING_ORDER_CANCEL_NOT_ENOUGH_BALANCE,
            'trading_order_cancelled.cust_id': str(123),
            'trading_order_cancelled.trd_id': str(456),
            'trading_order_cancelled.ord_id': str(789),
            'trading_order_cancelled.price': str(1011),
            'trading_order_cancelled.qty': 1213,
            'trading_order_cancelled.remaining_qty': 1415,
            'trading_order_cancelled.not_enough_balance.ok': True,
        }
    ),

    (
        OEV8_EVT_TRADING_ORDER_CANCEL_REMAINING,
        KLASS.on_trading_order_cancelled,
        {
            'cust_id': str(123),
            'trd_id': str(456),
            'ord_id': 789,
            'price': 1011,
            'qty': 1213,
            'remaining_qty': 1415,
            'why': TradingOrderCancelCauseFoK(),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_TRADING_ORDER_CANCEL_FOK,
            'trading_order_cancelled.cust_id': str(123),
            'trading_order_cancelled.trd_id': str(456),
            'trading_order_cancelled.ord_id': str(789),
            'trading_order_cancelled.price': str(1011),
            'trading_order_cancelled.qty': 1213,
            'trading_order_cancelled.remaining_qty': 1415,
            'trading_order_cancelled.fok.ok': True,
        }
    ),

    (
        OEV8_EVT_TRADING_ORDER_CANCEL_REMAINING,
        KLASS.on_trading_order_cancelled,
        {
            'cust_id': str(123),
            'trd_id': str(456),
            'ord_id': 789,
            'price': 1011,
            'qty': 1213,
            'remaining_qty': 1415,
            'why': TradingOrderCancelCauseIoC(),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_TRADING_ORDER_CANCEL_IOC,
            'trading_order_cancelled.cust_id': str(123),
            'trading_order_cancelled.trd_id': str(456),
            'trading_order_cancelled.ord_id': str(789),
            'trading_order_cancelled.price': str(1011),
            'trading_order_cancelled.qty': 1213,
            'trading_order_cancelled.remaining_qty': 1415,
            'trading_order_cancelled.ioc.ok': True,
        }
    ),

    (
        OEV8_EVT_TRADING_ORDER_CANCEL_REMAINING,
        KLASS.on_trading_order_cancelled,
        {
            'cust_id': str(123),
            'trd_id': str(456),
            'ord_id': 789,
            'price': 1011,
            'qty': 1213,
            'remaining_qty': 1415,
            'why': TradingOrderCancelCauseTimedOut(),
        },
        {
            'evt_cause_type': OEV8_EVT_CAUSE_TRADING_ORDER_CANCEL_TIMED_OUT,
            'trading_order_cancelled.cust_id': '123',
            'trading_order_cancelled.trd_id': '456',
            'trading_order_cancelled.ord_id': '789',
            'trading_order_cancelled.price': '1011',
            'trading_order_cancelled.qty': 1213,
            'trading_order_cancelled.remaining_qty': 1415,
            'trading_order_cancelled.timed_out.ok': True,
        }
    ),
]


@mark.parametrize(
    "evt_type,method,params,result",
    EVENT_WRITER_CASES)
def test_protobuf_event_writer(
        evt_type, method, params, result
):
    cmd_uuid = rand_cmd_uuid()
    seq_num = rand_1mil()

    event_sender = Mock()
    event_sender.send = MagicMock(side_effect=lambda x: x)

    event_writer = ProtoBufEventWriter(event_sender)
    event_writer.set_current(cmd_uuid, seq_num)

    method(event_writer, **params)

    event_writer.commit_buffer()  # 사실 없어도 이 클래스는 바로 send.

    assert 1 == event_sender.send.call_count
    called_args = event_sender.send.call_args[0][0]

    evt = Oev8_Event()
    evt.ParseFromString(called_args)

    for k, v in result.items():
        assert magicattr.get(evt, k) == v

    #
    assert evt.cmd_uuid == cmd_uuid
    assert int(evt.seq_num) == seq_num
    assert evt.evt_type == evt_type


@mark.parametrize(
    "evt_type,method,params,result",
    EVENT_WRITER_CASES)
def test_protobuf_event_writer__clear_buffer(
        evt_type, method, params, result
):
    cmd_uuid = rand_cmd_uuid()
    seq_num = rand_1mil()

    event_sender = Mock()
    event_sender.send = MagicMock(side_effect=lambda x: x)

    event_writer = ProtoBufEventWriter(event_sender)
    event_writer.set_current(cmd_uuid, seq_num)

    method(event_writer, **params)

    event_writer.clear_buffer()  # 있어도 이 클래스는 바로 send.

    assert 1 == event_sender.send.call_count
    called_args = event_sender.send.call_args[0][0]

    evt = Oev8_Event()
    evt.ParseFromString(called_args)

    for k, v in result.items():
        assert magicattr.get(evt, k) == v

    #
    assert evt.cmd_uuid == cmd_uuid
    assert int(evt.seq_num) == seq_num
    assert evt.evt_type == evt_type
