import sys
import logging
import argparse
import asyncio
from datetime import datetime, timezone
import uuid
from multiprocessing import Process
import cmd2  # type:ignore
import kafka  # type:ignore
from termcolor import cprint  # type:ignore
import isodate  # type:ignore
from oev8_pb2 import Oev8_Event
from oev8.typedefs import BalanceType, OrderOption, OrderSide
from oev8.configs import Config
from oev8.client import TCPClient, CmdClient
from oev8.funcs import to_timestamp_secs


logger = logging.getLogger('cmd_shell')

balance_type_choices = ['balance', 'earning']
limit_order_option_choices = ['none', 'fok', 'ioc']
market_order_option_choices = ['none', 'fok']
bid_order_option_choices = ['none', 'fok']
order_side_choices = ['buy', 'sell']


def map_balance_type(balance_type_str):
    return {
        'balance': BalanceType.BALANCE,
        'earning': BalanceType.EARNING,
    }[balance_type_str]


def map_order_option(order_option_str):
    return {
        'none': OrderOption.NONE,
        'fok': OrderOption.FILL_OR_KILL,
        'ioc': OrderOption.IMMEDIATE_OR_CANCEL,
    }[order_option_str]


def map_order_side(order_side_str):
    return {
        'buy': OrderSide.BUY,
        'sell': OrderSide.SELL,
    }[order_side_str]


def event_tailf(config: Config,
                client_id: str,
                group_id: str,
                nocolor: bool = False):
    config = Config()

    logger.info("LOADING CONFIG FROM: %s", config_fn)
    config.read_file(config_fn)

    logger.info("LOADED CONFIG: %s", config.dump())

    config.check()

    #
    server_addr = config.get_journal_writer_kafka_bootstrap_server()
    topic = config.get_event_writer_kafka_topic()

    consumer = kafka.KafkaConsumer(
        topic,
        bootstrap_servers=server_addr,
        group_id=group_id,
        client_id=client_id)

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

                    try:
                        evt = Oev8_Event()
                        evt.ParseFromString(msg.value)

                        if nocolor:
                            print(evt)
                            print('-' * 70)
                        else:
                            cprint(evt, color='green')
                            cprint('-' * 70, color='white')
                    except:
                        logger.warning('ParseFromString FAIL',
                                       exc_info=True)


def run_event_tailf(config):
    event_tailf(config,
                str(uuid.uuid4()),
                str(uuid.uuid4()))


def config_logger():
    "configure default logger."
    stdout_handler = logging.StreamHandler(sys.stdout)
    tmpfile_handler = None  # logging.FileHandler('/tmp/oev8.log')
    handlers = [stdout_handler]
    if tmpfile_handler is not None:
        handlers.append(tmpfile_handler)

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03d %(name)s [%(filename)s:%(lineno)d] : %(message)s',  # noqa:E501
        datefmt='%y-%m-%d_%H:%M:%S',
        handlers=handlers
    )

    logging.getLogger('kafka').setLevel(logging.INFO)


class CmdShellApp(cmd2.Cmd):
    def __init__(self, config: Config, config_fn: str):
        super().__init__(use_ipython=True,
                         allow_cli_args=False,
                         persistent_history_file='~/.oev8_cmd_shell_history',
                         startup_script='.oev8_cmd_shell_rc')

        self.prompt = '[OeV8-CmdShell]: '

        self.config_fn = config_fn
        self.config = config
        self.aio_loop = asyncio.new_event_loop()
        self.__new_cmd_client()
        self.event_tailf_proc = None

        self.register_precmd_hook(self.sw_precmd)
        self.register_postcmd_hook(self.sw_postcmd)

    def sw_precmd(
            self,
            data: cmd2.plugin.PrecommandData
    ) -> cmd2.plugin.PrecommandData:
        self.started_at = datetime.now()
        return data

    def sw_postcmd(
            self, data: cmd2.plugin.PostcommandData
    ) -> cmd2.plugin.PostcommandData:
        timedelta = datetime.now() - self.started_at
        msg = f'Took {timedelta.total_seconds():f} secs.'
        cprint(msg, color='magenta')

        return data

    def __new_cmd_client(self):
        return self.__new_cmd_client2(
            self.config.get_server_host(),
            self.config.get_server_port())

    def __new_cmd_client2(self, host, port):
        self.tcp_client = TCPClient(host, port)
        self.cmd_client = CmdClient(self.tcp_client)

    # CATEGORIES
    CMD_CAT_CONN = 'Connection'
    CMD_CAT_MAINT = 'Maintenence'
    CMD_CAT_BALANCE = 'Balance'
    CMD_CAT_ITEM_COUNT = 'Item-Count'
    CMD_CAT_TRADING = 'Trading'
    CMD_CAT_TRADING_ORDER = 'Trading/Order'
    CMD_CAT_TRADING_INQUIRY = 'Trading/Inquiry'
    CMD_CAT_HELPERS = 'Helpers'

    # connect
    conn_parser = argparse.ArgumentParser()
    conn_parser.add_argument('--host', type=str,
                             metavar='host',
                             required=False, default='')
    conn_parser.add_argument('--port', type=int,
                             metavar='port',
                             required=False, default=0)

    @cmd2.with_category(CMD_CAT_CONN)
    @cmd2.with_argparser(conn_parser)
    def do_connect(self, args):
        host = self.config.get_server_host()
        port = self.config.get_server_port()

        if len(args.host) > 0:
            host = args.host

        if args.port > 0:
            port = args.port

        logger.info('Connecting to %s:%s ...', host, port)

        self.__new_cmd_client2(host, port)

        self.poutput(self.aio_loop.run_until_complete(
            self.tcp_client.connect()))

    # disconnect
    @cmd2.with_category(CMD_CAT_CONN)
    def do_disconnect(self, _):
        try:
            self.poutput(self.aio_loop.run_until_complete(
                self.tcp_client.disconnect()))
        except:
            logger.warning('disconnect fail', exc_info=True)

        self.__new_cmd_client()

    # start/stop_event_tailf
    @cmd2.with_category(CMD_CAT_CONN)
    def do_start_event_tailf(self, _):
        if self.event_tailf_proc is None:
            self.event_tailf_proc = Process(target=run_event_tailf,
                                            daemon=True,
                                            args=(self.config,))
            self.event_tailf_proc.start()
        else:
            logger.warning(f'Already running: {self.event_tailf_proc}')

    @cmd2.with_category(CMD_CAT_CONN)
    def do_stop_event_tailf(self, _):
        if self.event_tailf_proc is not None:
            try:
                self.event_tailf_proc.kill()
            except:
                logger.warning(f'Kill {self.event_tailf_proc} FAIL',
                               exc_info=True)
            self.event_tailf_proc = None
        else:
            logger.warning('Not running.')

    # ping
    @cmd2.with_category(CMD_CAT_MAINT)
    def do_ping(self, _):
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.ping()))

    # sleep(secs)
    sleep_parser = argparse.ArgumentParser()
    sleep_parser.add_argument('secs', type=int)

    @cmd2.with_category(CMD_CAT_MAINT)
    @cmd2.with_argparser(sleep_parser)
    def do_sleep(self, args):
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.sleep(args.secs)))

    # enter_maint_mode
    @cmd2.with_category(CMD_CAT_MAINT)
    def do_enter_maint_mode(self, _):
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.enter_maint_mode()))

    # leave_maint_mode
    @cmd2.with_category(CMD_CAT_MAINT)
    def do_leave_maint_mode(self, _):
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.leave_maint_mode()))

    # shutdown
    @cmd2.with_category(CMD_CAT_MAINT)
    def do_shutdown(self, _):
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.shutdown()))

    # snapshot
    @cmd2.with_category(CMD_CAT_MAINT)
    def do_snapshot(self, _):
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.snapshot()))

    # save_quit
    @cmd2.with_category(CMD_CAT_MAINT)
    def do_save_quit(self, _):
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.save_quit()))

    # balance_get(cust_id, balance_type, curr)
    balance_get_parser = argparse.ArgumentParser()
    balance_get_parser.add_argument('cust_id', type=str)
    balance_get_parser.add_argument('balance_type', type=str,
                                    choices=balance_type_choices)
    balance_get_parser.add_argument('curr', type=int)

    @cmd2.with_category(CMD_CAT_BALANCE)
    @cmd2.with_argparser(balance_get_parser)
    def do_balance_get(self, args):
        cust_id = args.cust_id
        curr = args.curr
        balance_type = map_balance_type(args.balance_type)
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.balance_get(cust_id, balance_type, curr)))

    # balance_deposit(cust_id, balance_type, curr, amt)
    balance_deposit_parser = argparse.ArgumentParser()
    balance_deposit_parser.add_argument('cust_id', type=str)
    balance_deposit_parser.add_argument('balance_type', type=str,
                                        choices=balance_type_choices)
    balance_deposit_parser.add_argument('curr', type=int)
    balance_deposit_parser.add_argument('amt', type=str)

    @cmd2.with_category(CMD_CAT_BALANCE)
    @cmd2.with_argparser(balance_deposit_parser)
    def do_balance_deposit(self, args):
        cust_id = args.cust_id
        curr = args.curr
        balance_type = map_balance_type(args.balance_type)
        amt = args.amt
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.balance_deposit(
                cust_id, balance_type, curr, amt)))

    # balance_withdraw(cust_id, balance_type, curr, amt)
    balance_withdraw_parser = argparse.ArgumentParser()
    balance_withdraw_parser.add_argument('cust_id', type=str)
    balance_withdraw_parser.add_argument('balance_type', type=str,
                                         choices=balance_type_choices)
    balance_withdraw_parser.add_argument('curr', type=int)
    balance_withdraw_parser.add_argument('amt', type=str)

    @cmd2.with_category(CMD_CAT_BALANCE)
    @cmd2.with_argparser(balance_withdraw_parser)
    def do_balance_withdraw(self, args):
        cust_id = args.cust_id
        curr = args.curr
        balance_type = map_balance_type(args.balance_type)
        amt = args.amt
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.balance_withdraw(
                cust_id, balance_type, curr, amt)))

    # balance_delete_by_currency(curr)
    balance_delete_by_currency_parser = argparse.ArgumentParser()
    balance_delete_by_currency_parser.add_argument('curr', type=int)

    @cmd2.with_category(CMD_CAT_BALANCE)
    @cmd2.with_argparser(balance_delete_by_currency_parser)
    def do_balance_delete_by_currency(self, args):
        curr = args.curr
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.balance_delete_by_currency(curr)))

    # balance_delete_by_customer(cust_id)
    balance_delete_by_customer_parser = argparse.ArgumentParser()
    balance_delete_by_customer_parser.add_argument('cust_id', type=str)

    @cmd2.with_category(CMD_CAT_BALANCE)
    @cmd2.with_argparser(balance_delete_by_customer_parser)
    def do_balance_delete_by_customer(self, args):
        cust_id = args.cust_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.balance_delete_by_customer(cust_id)))

    # balance_xfer_from(balance_type, cust_id, curr, amt)
    balance_xfer_from_parser = argparse.ArgumentParser()
    balance_xfer_from_parser.add_argument('balance_type', type=str,
                                          choices=balance_type_choices)
    balance_xfer_from_parser.add_argument('cust_id', type=str)
    balance_xfer_from_parser.add_argument('curr', type=int)
    balance_xfer_from_parser.add_argument('amt', type=str)

    @cmd2.with_category(CMD_CAT_BALANCE)
    @cmd2.with_argparser(balance_xfer_from_parser)
    def do_balance_xfer_from(self, args):
        balance_type = map_balance_type(args.balance_type)
        curr = args.curr
        amt = args.amt
        cust_id = args.cust_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.balance_xfer_from(
                balance_type, cust_id, curr, amt)))

    # balance_xfer_to(balance_type, cust_id, curr, amt)
    balance_xfer_to_parser = argparse.ArgumentParser()
    balance_xfer_to_parser.add_argument('balance_type', type=str,
                                        choices=balance_type_choices)
    balance_xfer_to_parser.add_argument('cust_id', type=str)
    balance_xfer_to_parser.add_argument('curr', type=int)
    balance_xfer_to_parser.add_argument('amt', type=str)

    @cmd2.with_category(CMD_CAT_BALANCE)
    @cmd2.with_argparser(balance_xfer_to_parser)
    def do_balance_xfer_to(self, args):
        balance_type = map_balance_type(args.balance_type)
        curr = args.curr
        amt = args.amt
        cust_id = args.cust_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.balance_xfer_to(
                balance_type, cust_id, curr, amt)))

    # balance_cvt_xfer_to(from_balance_type, to_balance_type, cust_id, curr, amt)
    balance_cvt_xfer_to_parser = argparse.ArgumentParser()
    balance_cvt_xfer_to_parser.add_argument('from_balance_type', type=str,
                                            choices=balance_type_choices)
    balance_cvt_xfer_to_parser.add_argument('to_balance_type', type=str,
                                            choices=balance_type_choices)
    balance_cvt_xfer_to_parser.add_argument('cust_id', type=str)
    balance_cvt_xfer_to_parser.add_argument('curr', type=int)
    balance_cvt_xfer_to_parser.add_argument('amt', type=str)

    @cmd2.with_category(CMD_CAT_BALANCE)
    @cmd2.with_argparser(balance_cvt_xfer_to_parser)
    def do_balance_cvt_xfer_to(self, args):
        from_balance_type = map_balance_type(args.from_balance_type)
        to_balance_type = map_balance_type(args.to_balance_type)
        curr = args.curr
        amt = args.amt
        cust_id = args.cust_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.balance_cvt_xfer_to(
                from_balance_type, to_balance_type, cust_id, curr, amt)))

    # item_count_get(cust_id, trd_id)
    item_count_get_parser = argparse.ArgumentParser()
    item_count_get_parser.add_argument('cust_id', type=str)
    item_count_get_parser.add_argument('trd_id', type=str)

    @cmd2.with_category(CMD_CAT_ITEM_COUNT)
    @cmd2.with_argparser(item_count_get_parser)
    def do_item_count_get(self, args):
        cust_id = args.cust_id
        trd_id = args.trd_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.item_count_get(
                cust_id, trd_id)))

    # item_count_inc(cust_id, trd_id, qty)
    item_count_inc_parser = argparse.ArgumentParser()
    item_count_inc_parser.add_argument('cust_id', type=str)
    item_count_inc_parser.add_argument('trd_id', type=str)
    item_count_inc_parser.add_argument('qty', type=int)

    @cmd2.with_category(CMD_CAT_ITEM_COUNT)
    @cmd2.with_argparser(item_count_inc_parser)
    def do_item_count_inc(self, args):
        cust_id = args.cust_id
        trd_id = args.trd_id
        qty = args.qty
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.item_count_inc(
                cust_id, trd_id, qty)))

    # item_count_dec(cust_id, trd_id, qty)
    item_count_dec_parser = argparse.ArgumentParser()
    item_count_dec_parser.add_argument('cust_id', type=str)
    item_count_dec_parser.add_argument('trd_id', type=str)
    item_count_dec_parser.add_argument('qty', type=int)

    @cmd2.with_category(CMD_CAT_ITEM_COUNT)
    @cmd2.with_argparser(item_count_dec_parser)
    def do_item_count_dec(self, args):
        cust_id = args.cust_id
        trd_id = args.trd_id
        qty = args.qty
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.item_count_dec(
                cust_id, trd_id, qty)))

    # item_count_delete_by_trading(trd_id)
    item_count_delete_by_trading_parser = argparse.ArgumentParser()
    item_count_delete_by_trading_parser.add_argument('trd_id', type=str)

    @cmd2.with_category(CMD_CAT_ITEM_COUNT)
    @cmd2.with_argparser(item_count_delete_by_trading_parser)
    def do_item_count_delete_by_trading(self, args):
        trd_id = args.trd_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.item_count_delete_by_trading(
                trd_id)))

    # item_count_delete_by_customer(cust_id)
    item_count_delete_by_customer_parser = argparse.ArgumentParser()
    item_count_delete_by_customer_parser.add_argument('cust_id', type=str)

    @cmd2.with_category(CMD_CAT_ITEM_COUNT)
    @cmd2.with_argparser(item_count_delete_by_customer_parser)
    def do_item_count_delete_by_customer(self, args):
        cust_id = args.cust_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.item_count_delete_by_customer(
                cust_id)))

    # item_count_xfer_from(cust_id, trd_id, qty)
    item_count_xfer_from_parser = argparse.ArgumentParser()
    item_count_xfer_from_parser.add_argument('cust_id', type=str)
    item_count_xfer_from_parser.add_argument('trd_id', type=str)
    item_count_xfer_from_parser.add_argument('qty', type=int)

    @cmd2.with_category(CMD_CAT_ITEM_COUNT)
    @cmd2.with_argparser(item_count_xfer_from_parser)
    def do_item_count_xfer_from(self, args):
        cust_id = args.cust_id
        trd_id = args.trd_id
        qty = args.qty
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.item_count_xfer_from(
                cust_id, trd_id, qty)))

    # item_count_xfer_to(cust_id, trd_id, qty)
    item_count_xfer_to_parser = argparse.ArgumentParser()
    item_count_xfer_to_parser.add_argument('cust_id', type=str)
    item_count_xfer_to_parser.add_argument('trd_id', type=str)
    item_count_xfer_to_parser.add_argument('qty', type=int)

    @cmd2.with_category(CMD_CAT_ITEM_COUNT)
    @cmd2.with_argparser(item_count_xfer_to_parser)
    def do_item_count_xfer_to(self, args):
        cust_id = args.cust_id
        trd_id = args.trd_id
        qty = args.qty
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.item_count_xfer_to(
                cust_id, trd_id, qty)))

    # trading_start_new(cust_id, trd_id, curr, sec_deposit_amt, qty, limit_sell_price, until_utc_timestamp_secs)
    trading_start_new_parser = argparse.ArgumentParser()
    trading_start_new_parser.add_argument('cust_id', type=str)
    trading_start_new_parser.add_argument('trd_id', type=str)
    trading_start_new_parser.add_argument('curr', type=int)
    trading_start_new_parser.add_argument('sec_deposit_amt', type=str)
    trading_start_new_parser.add_argument('qty', type=int)
    trading_start_new_parser.add_argument('limit_sell_price', type=str)
    trading_start_new_parser.add_argument('until_utc_timestamp_secs', type=int)

    @cmd2.with_category(CMD_CAT_TRADING)
    @cmd2.with_argparser(trading_start_new_parser)
    def do_trading_start_new(self, args):
        cust_id = args.cust_id
        trd_id = args.trd_id
        curr = args.curr
        sec_deposit_amt = args.sec_deposit_amt
        qty = args.qty
        limit_sell_price = args.limit_sell_price
        until_utc_timestamp_secs = args.until_utc_timestamp_secs
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_start_new(
                cust_id, trd_id, curr, sec_deposit_amt,
                qty, limit_sell_price, until_utc_timestamp_secs)))

    # trading_set_until(trd_id, until_utc_timestamp_secs)
    trading_set_until_parser = argparse.ArgumentParser()
    trading_set_until_parser.add_argument('trd_id', type=str)
    trading_set_until_parser.add_argument('until_utc_timestamp_secs', type=int)

    @cmd2.with_category(CMD_CAT_TRADING)
    @cmd2.with_argparser(trading_set_until_parser)
    def do_trading_set_until(self, args):
        trd_id = args.trd_id
        until_utc_timestamp_secs = args.until_utc_timestamp_secs
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_set_until(
                trd_id, until_utc_timestamp_secs)))

    # trading_new_selling_auction(cust_id, trd_id, curr, security_deposit_amt, qty, limit_sell_unit_price, until_utc_timestamp_secs)
    trading_new_selling_auction_parser = argparse.ArgumentParser()
    trading_new_selling_auction_parser.add_argument('cust_id', type=str)
    trading_new_selling_auction_parser.add_argument('trd_id', type=str)
    trading_new_selling_auction_parser.add_argument('curr', type=int)
    trading_new_selling_auction_parser.add_argument('sec_deposit_amt', type=str)
    trading_new_selling_auction_parser.add_argument('qty', type=int)
    trading_new_selling_auction_parser.add_argument('limit_sell_price', type=str)
    trading_new_selling_auction_parser.add_argument('until_utc_timestamp_secs', type=int)

    trading_new_buying_auction_parser = argparse.ArgumentParser()
    trading_new_buying_auction_parser.add_argument('cust_id', type=int)
    trading_new_buying_auction_parser.add_argument('trd_id', type=str)
    trading_new_buying_auction_parser.add_argument('curr', type=int)
    trading_new_buying_auction_parser.add_argument('sec_deposit_amt', type=str)
    trading_new_buying_auction_parser.add_argument('qty', type=int)
    trading_new_buying_auction_parser.add_argument('limit_buy_price', type=str)
    trading_new_buying_auction_parser.add_argument('until_utc_timestamp_secs', type=int)

    @cmd2.with_category(CMD_CAT_TRADING)
    @cmd2.with_argparser(trading_new_selling_auction_parser)
    def do_trading_new_selling_auction(self, args):
        cust_id = args.cust_id
        trd_id = args.trd_id
        curr = args.curr
        sec_deposit_amt = args.sec_deposit_amt
        qty = args.qty
        limit_sell_price = args.limit_sell_price
        until_utc_timestamp_secs = args.until_utc_timestamp_secs
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_new_selling_auction(
                cust_id, trd_id, curr, sec_deposit_amt,
                qty, limit_sell_price, until_utc_timestamp_secs)))

    # trading_join(cust_id, trd_id, qty, sec_deposit_amt)
    trading_join_parser = argparse.ArgumentParser()
    trading_join_parser.add_argument('cust_id', type=str)
    trading_join_parser.add_argument('trd_id', type=str)
    trading_join_parser.add_argument('qty', type=int)
    trading_join_parser.add_argument('sec_deposit_amt', type=str)

    @cmd2.with_category(CMD_CAT_TRADING)
    @cmd2.with_argparser(trading_new_buying_auction_parser)
    def do_trading_new_buying_auction(self, args):
        cust_id = args.cust_id
        trd_id = args.trd_id
        curr = args.curr
        sec_deposit_amt = args.sec_deposit_amt
        qty = args.qty
        limit_buy_price = args.limit_buy_price
        until_utc_timestamp_secs = args.until_utc_timestamp_secs
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_new_buying_auction(
                cust_id, trd_id, curr, sec_deposit_amt,
                qty, limit_buy_price, until_utc_timestamp_secs)))

    # trading_join(cust_id, trd_id, qty, sec_deposit_amt)
    trading_join_parser = argparse.ArgumentParser()
    trading_join_parser.add_argument('cust_id', type=str)
    trading_join_parser.add_argument('trd_id', type=str)
    trading_join_parser.add_argument('qty', type=int)
    trading_join_parser.add_argument('sec_deposit_amt', type=str)

    @cmd2.with_category(CMD_CAT_TRADING)
    @cmd2.with_argparser(trading_join_parser)
    def do_trading_join(self, args):
        cust_id = args.cust_id
        trd_id = args.trd_id
        qty = args.qty
        sec_deposit_amt = args.sec_deposit_amt
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_join(
                cust_id, trd_id, qty, sec_deposit_amt)))

    # trading_provide_item(cust_id, trd_id, qty)
    trading_provide_item_parser = argparse.ArgumentParser()
    trading_provide_item_parser.add_argument('cust_id', type=str)
    trading_provide_item_parser.add_argument('trd_id', type=str)
    trading_provide_item_parser.add_argument('qty', type=int)

    @cmd2.with_category(CMD_CAT_TRADING)
    @cmd2.with_argparser(trading_provide_item_parser)
    def do_trading_provide_item(self, args):
        cust_id = args.cust_id
        trd_id = args.trd_id
        qty = args.qty
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_provide_item(
                cust_id, trd_id, qty)))

    # trading_unprovide_item(cust_id, trd_id, qty)
    trading_unprovide_item_parser = argparse.ArgumentParser()
    trading_unprovide_item_parser.add_argument('cust_id', type=str)
    trading_unprovide_item_parser.add_argument('trd_id', type=str)
    trading_unprovide_item_parser.add_argument('qty', type=int)

    @cmd2.with_category(CMD_CAT_TRADING)
    @cmd2.with_argparser(trading_unprovide_item_parser)
    def do_trading_unprovide_item(self, args):
        cust_id = args.cust_id
        trd_id = args.trd_id
        qty = args.qty
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_unprovide_item(
                cust_id, trd_id, qty)))

    # trading_resume(trd_id)
    trading_resume_parser = argparse.ArgumentParser()
    trading_resume_parser.add_argument('trd_id', type=str)

    @cmd2.with_category(CMD_CAT_TRADING)
    @cmd2.with_argparser(trading_resume_parser)
    def do_trading_resume(self, args):
        trd_id = args.trd_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_resume(trd_id)))

    # trading_pause(trd_id)
    trading_pause_parser = argparse.ArgumentParser()
    trading_pause_parser.add_argument('trd_id', type=str)

    @cmd2.with_category(CMD_CAT_TRADING)
    @cmd2.with_argparser(trading_pause_parser)
    def do_trading_pause(self, args):
        trd_id = args.trd_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_pause(trd_id)))

    # trading_finalize(trd_id)
    trading_finalize_parser = argparse.ArgumentParser()
    trading_finalize_parser.add_argument('trd_id', type=str)

    @cmd2.with_category(CMD_CAT_TRADING)
    @cmd2.with_argparser(trading_finalize_parser)
    def do_trading_finalize(self, args):
        trd_id = args.trd_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_finalize(trd_id)))

    # trading_cancel(trd_id)
    trading_cancel_parser = argparse.ArgumentParser()
    trading_cancel_parser.add_argument('trd_id', type=str)

    @cmd2.with_category(CMD_CAT_TRADING)
    @cmd2.with_argparser(trading_cancel_parser)
    def do_trading_cancel(self, args):
        trd_id = args.trd_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_cancel(trd_id)))

    # trading_evict(trd_id)
    trading_evict_parser = argparse.ArgumentParser()
    trading_evict_parser.add_argument('trd_id', type=str)

    @cmd2.with_category(CMD_CAT_TRADING)
    @cmd2.with_argparser(trading_evict_parser)
    def do_trading_evict(self, args):
        trd_id = args.trd_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_evict(trd_id)))

    # trading_order_limit_sell(cust_id, trd_id, price, qty, option)
    trading_order_limit_sell_parser = argparse.ArgumentParser()
    trading_order_limit_sell_parser.add_argument('cust_id', type=str)
    trading_order_limit_sell_parser.add_argument('trd_id', type=str)
    trading_order_limit_sell_parser.add_argument('price', type=str)
    trading_order_limit_sell_parser.add_argument('qty', type=int)
    trading_order_limit_sell_parser.add_argument('--option', type=str,
                                                 dest='order_option',
                                                 choices=limit_order_option_choices,
                                                 default='none')

    @cmd2.with_category(CMD_CAT_TRADING_ORDER)
    @cmd2.with_argparser(trading_order_limit_sell_parser)
    def do_trading_order_limit_sell(self, args):
        cust_id = args.cust_id
        trd_id = args.trd_id
        price = args.price
        qty = args.qty
        option = map_order_option(args.order_option)
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_order_limit_sell(
                cust_id, trd_id, price, qty, option)))

    # trading_order_limit_buy(cust_id, trd_id, price, qty, option)
    trading_order_limit_buy_parser = argparse.ArgumentParser()
    trading_order_limit_buy_parser.add_argument('cust_id', type=str)
    trading_order_limit_buy_parser.add_argument('trd_id', type=str)
    trading_order_limit_buy_parser.add_argument('price', type=str)
    trading_order_limit_buy_parser.add_argument('qty', type=int)
    trading_order_limit_buy_parser.add_argument('--option', type=str,
                                                dest='order_option',
                                                choices=limit_order_option_choices,
                                                default='none')

    @cmd2.with_category(CMD_CAT_TRADING_ORDER)
    @cmd2.with_argparser(trading_order_limit_buy_parser)
    def do_trading_order_limit_buy(self, args):
        cust_id = args.cust_id
        trd_id = args.trd_id
        price = args.price
        qty = args.qty
        option = map_order_option(args.order_option)
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_order_limit_buy(
                cust_id, trd_id, price, qty, option)))

    # trading_order_market_sell(cust_id, trd_id, qty, option)
    trading_order_market_sell_parser = argparse.ArgumentParser()
    trading_order_market_sell_parser.add_argument('cust_id', type=str)
    trading_order_market_sell_parser.add_argument('trd_id', type=str)
    trading_order_market_sell_parser.add_argument('qty', type=int)
    trading_order_market_sell_parser.add_argument('--option', type=str,
                                                  dest='order_option',
                                                  choices=market_order_option_choices,
                                                  default='none')

    @cmd2.with_category(CMD_CAT_TRADING_ORDER)
    @cmd2.with_argparser(trading_order_market_sell_parser)
    def do_trading_order_market_sell(self, args):
        cust_id = args.cust_id
        trd_id = args.trd_id
        qty = args.qty
        option = map_order_option(args.order_option)
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_order_market_sell(
                cust_id, trd_id, qty, option)))

    # trading_order_market_buy(cust_id, trd_id, qty, option)
    trading_order_market_buy_parser = argparse.ArgumentParser()
    trading_order_market_buy_parser.add_argument('cust_id', type=str)
    trading_order_market_buy_parser.add_argument('trd_id', type=str)
    trading_order_market_buy_parser.add_argument('qty', type=int)
    trading_order_market_buy_parser.add_argument('--option', type=str,
                                                 dest='order_option',
                                                 choices=market_order_option_choices,
                                                 default='none')

    @cmd2.with_category(CMD_CAT_TRADING_ORDER)
    @cmd2.with_argparser(trading_order_market_buy_parser)
    def do_trading_order_market_buy(self, args):
        cust_id = args.cust_id
        trd_id = args.trd_id
        qty = args.qty
        option = map_order_option(args.order_option)
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_order_market_buy(
                cust_id, trd_id, qty, option)))

    # trading_order_cancel(trd_id, ord_id)
    trading_order_cancel_parser = argparse.ArgumentParser()
    trading_order_cancel_parser.add_argument('trd_id', type=str)
    trading_order_cancel_parser.add_argument('ord_id', type=str)

    @cmd2.with_category(CMD_CAT_TRADING_ORDER)
    @cmd2.with_argparser(trading_order_cancel_parser)
    def do_trading_order_cancel(self, args):
        trd_id = args.trd_id
        ord_id = args.ord_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_order_cancel(
                trd_id, ord_id)))

    # trading_bid_buying(trd_id, cust_id, price, qty, option)
    trading_bid_buying_parser = argparse.ArgumentParser()
    trading_bid_buying_parser.add_argument('cust_id', type=str)
    trading_bid_buying_parser.add_argument('trd_id', type=str)
    trading_bid_buying_parser.add_argument('price', type=str)
    trading_bid_buying_parser.add_argument('qty', type=int)
    trading_bid_buying_parser.add_argument('--option', type=str,
                                           dest='order_option',
                                           choices=bid_order_option_choices,
                                           default='none')

    @cmd2.with_category(CMD_CAT_TRADING_ORDER)
    @cmd2.with_argparser(trading_bid_buying_parser)
    def do_trading_bid_buying(self, args):
        cust_id = args.cust_id
        trd_id = args.trd_id
        price = args.price
        qty = args.qty
        option = map_order_option(args.order_option)
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_bid_buying(
                trd_id, cust_id, price, qty, option)))

    trading_ask_selling_parser = argparse.ArgumentParser()
    trading_ask_selling_parser.add_argument('cust_id', type=str)
    trading_ask_selling_parser.add_argument('trd_id', type=str)
    trading_ask_selling_parser.add_argument('price', type=str)
    trading_ask_selling_parser.add_argument('qty', type=int)
    trading_ask_selling_parser.add_argument('sec_deposit_amt', type=str)
    trading_ask_selling_parser.add_argument('--option', type=str,
                                            dest='order_option',
                                            choices=bid_order_option_choices,
                                            default='none')

    @cmd2.with_category(CMD_CAT_TRADING_ORDER)
    @cmd2.with_argparser(trading_ask_selling_parser)
    def do_trading_ask_selling(self, args):
        cust_id = args.cust_id
        trd_id = args.trd_id
        price = args.price
        qty = args.qty
        sec_deposit_amt = args.sec_deposit_amt
        option = map_order_option(args.order_option)
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_ask_selling(
                trd_id, cust_id, price, qty, sec_deposit_amt, option)))

    # trading_list_id(offset, limit)
    trading_list_id_parser = argparse.ArgumentParser()
    trading_list_id_parser.add_argument('offset', type=int)
    trading_list_id_parser.add_argument('limit', type=int)

    @cmd2.with_category(CMD_CAT_TRADING_INQUIRY)
    @cmd2.with_argparser(trading_list_id_parser)
    def do_trading_list_id(self, args):
        offset = args.offset
        limit = args.limit
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_list_id(offset, limit)))

    # trading_count_id
    @cmd2.with_category(CMD_CAT_TRADING_INQUIRY)
    def do_trading_count_id(self, args):
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_count_id()))

    # trading_get_info(trd_id)
    trading_get_info_parser = argparse.ArgumentParser()
    trading_get_info_parser.add_argument('trd_id', type=str)

    @cmd2.with_category(CMD_CAT_TRADING_INQUIRY)
    @cmd2.with_argparser(trading_get_info_parser)
    def do_trading_get_info(self, args):
        trd_id = args.trd_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_get_info(trd_id)))

    # trading_get_auction_info(trd_id)
    trading_get_auction_info_parser = argparse.ArgumentParser()
    trading_get_auction_info_parser.add_argument('trd_id', type=str)

    @cmd2.with_category(CMD_CAT_TRADING_INQUIRY)
    @cmd2.with_argparser(trading_get_auction_info_parser)
    def do_trading_get_auction_info(self, args):
        trd_id = args.trd_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_get_auction_info(trd_id)))

    # trading_list_item_providing(trd_id, offset, limit)
    trading_list_item_providing_parser = argparse.ArgumentParser()
    trading_list_item_providing_parser.add_argument('trd_id', type=str)
    trading_list_item_providing_parser.add_argument('offset', type=int)
    trading_list_item_providing_parser.add_argument('limit', type=int)

    @cmd2.with_category(CMD_CAT_TRADING_INQUIRY)
    @cmd2.with_argparser(trading_list_item_providing_parser)
    def do_trading_list_item_providing(self, args):
        trd_id = args.trd_id
        offset = args.offset
        limit = args.limit
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_list_item_providing(
                trd_id, offset, limit)))

    # trading_count_item_providing(trd_id)
    trading_count_item_providing_parser = argparse.ArgumentParser()
    trading_count_item_providing_parser.add_argument('trd_id', type=str)

    @cmd2.with_category(CMD_CAT_TRADING_INQUIRY)
    @cmd2.with_argparser(trading_count_item_providing_parser)
    def do_trading_count_item_providing(self, args):
        trd_id = args.trd_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_count_item_providing(trd_id)))

    # trading_list_order(trd_id, offset, limit)
    trading_list_order_parser = argparse.ArgumentParser()
    trading_list_order_parser.add_argument('trd_id', type=str)
    trading_list_order_parser.add_argument('offset', type=int)
    trading_list_order_parser.add_argument('limit', type=int)

    @cmd2.with_category(CMD_CAT_TRADING_INQUIRY)
    @cmd2.with_argparser(trading_list_order_parser)
    def do_trading_list_order(self, args):
        trd_id = args.trd_id
        offset = args.offset
        limit = args.limit
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_list_order(
                trd_id, offset, limit)))

    # trading_count_order(trd_id)
    trading_count_order_parser = argparse.ArgumentParser()
    trading_count_order_parser.add_argument('trd_id', type=str)

    @cmd2.with_category(CMD_CAT_TRADING_INQUIRY)
    @cmd2.with_argparser(trading_count_order_parser)
    def do_trading_count_order(self, args):
        trd_id = args.trd_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_count_order(trd_id)))

    # trading_list_match(trd_id, offset, limit)
    trading_list_match_parser = argparse.ArgumentParser()
    trading_list_match_parser.add_argument('trd_id', type=str)
    trading_list_match_parser.add_argument('offset', type=int)
    trading_list_match_parser.add_argument('limit', type=int)

    @cmd2.with_category(CMD_CAT_TRADING_INQUIRY)
    @cmd2.with_argparser(trading_list_match_parser)
    def do_trading_list_match(self, args):
        trd_id = args.trd_id
        offset = args.offset
        limit = args.limit
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_list_match(
                trd_id, offset, limit)))

    # trading_count_match(trd_id)
    trading_count_match_parser = argparse.ArgumentParser()
    trading_count_match_parser.add_argument('trd_id', type=str)

    @cmd2.with_category(CMD_CAT_TRADING_INQUIRY)
    @cmd2.with_argparser(trading_count_match_parser)
    def do_trading_count_match(self, args):
        trd_id = args.trd_id
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_count_match(trd_id)))

    # trading_list_price(trd_id, order_side, offset, limit)
    trading_list_price_parser = argparse.ArgumentParser()
    trading_list_price_parser.add_argument('trd_id', type=str)
    trading_list_price_parser.add_argument('side', type=str,
                                           choices=order_side_choices)
    trading_list_price_parser.add_argument('offset', type=int)
    trading_list_price_parser.add_argument('limit', type=int)

    @cmd2.with_category(CMD_CAT_TRADING_INQUIRY)
    @cmd2.with_argparser(trading_list_price_parser)
    def do_trading_list_price(self, args):
        trd_id = args.trd_id
        limit = args.limit
        offset = args.offset
        side = map_order_side(args.side)
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_list_price(trd_id, side, offset, limit)))

    # trading_count_price(trd_id, order_side)
    trading_count_price_parser = argparse.ArgumentParser()
    trading_count_price_parser.add_argument('trd_id', type=str)
    trading_count_price_parser.add_argument('side', type=str,
                                            choices=order_side_choices)

    @cmd2.with_category(CMD_CAT_TRADING_INQUIRY)
    @cmd2.with_argparser(trading_count_price_parser)
    def do_trading_count_price(self, args):
        trd_id = args.trd_id
        side = map_order_side(args.side)
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_count_price(trd_id, side)))

    # trading_list_order_by_price(trd_id, order_side, price, offset, limit)
    trading_list_order_by_price_parser = argparse.ArgumentParser()
    trading_list_order_by_price_parser.add_argument('trd_id', type=str)
    trading_list_order_by_price_parser.add_argument('side', type=str,
                                                    choices=order_side_choices)
    trading_list_order_by_price_parser.add_argument('price', type=str)
    trading_list_order_by_price_parser.add_argument('offset', type=int)
    trading_list_order_by_price_parser.add_argument('limit', type=int)

    @cmd2.with_category(CMD_CAT_TRADING_INQUIRY)
    @cmd2.with_argparser(trading_list_order_by_price_parser)
    def do_trading_list_order_by_price(self, args):
        trd_id = args.trd_id
        price = args.price
        limit = args.limit
        offset = args.offset
        side = map_order_side(args.side)
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_list_order_by_price(
                trd_id, side, price, offset, limit)))

    # trading_count_order_by_price(trd_id, order_side, price)
    trading_count_order_by_price_parser = argparse.ArgumentParser()
    trading_count_order_by_price_parser.add_argument('trd_id', type=str)
    trading_count_order_by_price_parser.add_argument('side', type=str,
                                                     choices=order_side_choices)
    trading_count_order_by_price_parser.add_argument('price', type=int)

    @cmd2.with_category(CMD_CAT_TRADING_INQUIRY)
    @cmd2.with_argparser(trading_count_order_by_price_parser)
    def do_trading_count_order_by_price(self, args):
        trd_id = args.trd_id
        price = args.price
        side = map_order_side(args.side)
        self.poutput(self.aio_loop.run_until_complete(
            self.cmd_client.trading_count_order_by_price(
                trd_id, side, price)))

    #
    helper_nowdelta_utctimestamp_parser = argparse.ArgumentParser()
    helper_nowdelta_utctimestamp_parser.add_argument('iso8601_duration', type=str,
                                                     help='ex: P2DT3H or P12148DT4H20M39.47017S')

    @cmd2.with_category(CMD_CAT_HELPERS)
    @cmd2.with_argparser(helper_nowdelta_utctimestamp_parser)
    def do_helper_nowdelta_utctimestamp(self, args):
        td = isodate.parse_duration(args.iso8601_duration)
        cprint(f'Time-delta: {td}', color='green')
        utcnow = datetime.utcnow()
        ts_now = to_timestamp_secs(utcnow)
        utcnew = utcnow + td
        ts_new = to_timestamp_secs(utcnew)
        cprint(f'Now(UTC): {utcnow} == {ts_now}', color='green')
        cprint(f'New(UTC): {utcnew} == {ts_new}', color='green')

    #
    helper_parse_utctimestamp_parser = argparse.ArgumentParser()
    helper_parse_utctimestamp_parser.add_argument('timestamp', type=int)

    @cmd2.with_category(CMD_CAT_HELPERS)
    @cmd2.with_argparser(helper_parse_utctimestamp_parser)
    def do_helper_parse_utctimestamp(self, args):
        """
        td = isodate.parse_duration(args.iso8601_duration)
        cprint(f'Time-delta: {td}', color='green')
        utcnow = datetime.utcnow()
        ts_now = to_timestamp_secs(utcnow)
        utcnew = utcnow + td
        ts_new = to_timestamp_secs(utcnew)
        cprint(f'Now(UTC): {utcnow} == {ts_now}', color='green')
        cprint(f'New(UTC): {utcnew} == {ts_new}', color='green')
        """
        utc_dt = datetime.fromtimestamp(args.timestamp)
        cprint(f'{args.timestamp} == {utc_dt}, (in UTC)', color='green')

    #
    helper_utctimestamp_parser = argparse.ArgumentParser()
    helper_utctimestamp_parser.add_argument('date', type=str,
                                            help='ex: 2020-10-13')
    helper_utctimestamp_parser.add_argument('time', type=str,
                                            help='ex: 23:59:32')

    @cmd2.with_category(CMD_CAT_HELPERS)
    @cmd2.with_argparser(helper_utctimestamp_parser)
    def do_helper_utctimestamp(self, args):
        arr_date = args.date.split('-')
        arr_time = args.time.split(':')
        pos_args = [int(i) for i in arr_date + arr_time]
        dt = datetime(*pos_args, tzinfo=timezone.utc)
        ts = to_timestamp_secs(dt)
        cprint(f'{dt} == {ts}', color='green')


if __name__ == '__main__':
    config_logger()

    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', type=str)
    args = parser.parse_args()

    config_fn = args.config_file

    config = Config()

    logger.info("LOADING CONFIG FROM: %s", config_fn)
    config.read_file(config_fn)
    logger.info("LOADED CONFIG: %s", config.dump())

    sys.exit(CmdShellApp(config, config_fn).cmdloop())
