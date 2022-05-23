import logging
import asyncio
from pytest import mark, fixture  # type:ignore
from . import is_system_test_disabled
from test.testsup.retries import RetryFail, async_retry


logger = logging.getLogger('test.system_tests.startup_test')


@mark.skipif(is_system_test_disabled(), reason='system test')
def test_start_and_shutdown(
        oev8_sh_cmd,
        oev8_sys_test_fixture,
        # cmd_client
        tcp_cmd_client,
        # asyncio
        asyncio_loop_and_runner,
        # fs paths
        test_config_path
):
    async def tbody():
        # start process.
        cfg_fn = str(test_config_path.resolve())
        proc = await asyncio.create_subprocess_exec(
            *(oev8_sh_cmd + [cfg_fn]))

        logger.debug('PID(%s) Running?(%s)',
                     proc.pid, proc.returncode is None)

        # request 'PING' cmd.
        async def connect_and_ping():
            logger.info('TCP Client CONNECTING...')
            await tcp_cmd_client.client.connect()
            logger.info('TCP Client CONNECTED..')

            logger.info('PONG? %s', await tcp_cmd_client.ping())

            # NOTE: 클라이언트측에서 종료 없어도 서버측에서 강제로 모든 커넥션 종료하기.
            # await tcp_cmd_client.client.disconnect()

        await async_retry(connect_and_ping, max_retries=10, delay_secs=1)

        # kill gracefully: by SIGTERM.
        proc.terminate()
        retcode = await proc.wait()
        logger.info('Terminated with: %s', retcode)

    # ...
    with asyncio_loop_and_runner as lnr:
        lnr[1](tbody())
