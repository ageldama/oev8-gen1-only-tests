import logging
import asyncio
from glob import glob
from pytest import mark, fixture  # type:ignore
from . import is_system_test_disabled
from test.testsup.retries import RetryFail, async_retry


logger = logging.getLogger('test.system_tests.graceful_shutdown_test')


@mark.skipif(is_system_test_disabled(), reason='system test')
def test_sigterm_produces_snapshot(
        oev8_sh_cmd,
        oev8_sys_test_fixture,
        # cmd_client
        tcp_cmd_client,
        # asyncio
        asyncio_loop_and_runner,
        # fs paths
        test_config_path
):
    'SIGTERM으로 종료시 스냅샷 생성하는지?'
    # local definitions:
    async def tbody():
        # start process.
        cfg_fn = str(test_config_path.resolve())
        proc = await asyncio.create_subprocess_exec(
            *(oev8_sh_cmd + [cfg_fn]))

        logger.debug('PID(%s) Running?(%s)',
                     proc.pid, proc.returncode is None)

        # try to connect...
        async def connect_and_ping():
            logger.info('TCP Client CONNECTING...')
            await tcp_cmd_client.client.connect()
            logger.info('TCP Client CONNECTED..')

            logger.info('PONG? %s', await tcp_cmd_client.ping())

        await async_retry(connect_and_ping, max_retries=10, delay_secs=1)

        # kill gracefully: by SIGTERM.
        proc.terminate()
        retcode = await proc.wait()
        logger.info('Terminated with: %s', retcode)

    # testing steps:
    # snapshot 디렉토리 목록 - 비어 있는지?
    snapshot_glob_path = \
        oev8_sys_test_fixture.snapshot_output_dir / "*"

    before_snapshot_glob = glob(str(snapshot_glob_path))
    assert len(before_snapshot_glob) == 0

    # 실행.
    with asyncio_loop_and_runner as lnr:
        lnr[1](tbody())

    # snapshot 디렉토리 목록 - 스냅샷 생성되었는지?
    after_snapshot_glob = glob(str(snapshot_glob_path))
    assert len(after_snapshot_glob) > 0


@mark.skipif(is_system_test_disabled(), reason='system test')
def test_save_quit_cmd_produces_snapshot(
        oev8_sh_cmd,
        oev8_sys_test_fixture,
        # cmd_client
        tcp_cmd_client,
        # asyncio
        asyncio_loop_and_runner,
        # fs paths
        test_config_path
):
    'SAVE_QUIT CMD으로 종료시 스냅샷 생성하는지.'
    # local definitions:
    async def tbody():
        # start process.
        cfg_fn = str(test_config_path.resolve())
        proc = await asyncio.create_subprocess_exec(
            *(oev8_sh_cmd + [cfg_fn]))

        logger.debug('PID(%s) Running?(%s)',
                     proc.pid, proc.returncode is None)

        # try to connect...
        async def connect_and_ping():
            logger.info('TCP Client CONNECTING...')
            await tcp_cmd_client.client.connect()
            logger.info('TCP Client CONNECTED..')

        await async_retry(connect_and_ping, max_retries=10, delay_secs=1)

        try:
            logger.info('SAVE_QUIT? %s', await tcp_cmd_client.save_quit())
        except:
            logger.debug("CAUGHT EXC on SAVE_QUIT (and it's okay)",
                         exc_info=True)

        # wait...
        retcode = await proc.wait()
        logger.info('Terminated with: %s', retcode)

    # testing steps:
    # snapshot 디렉토리 목록 - 비어 있는지?
    snapshot_glob_path = \
        oev8_sys_test_fixture.snapshot_output_dir / "*"

    before_snapshot_glob = glob(str(snapshot_glob_path))
    assert len(before_snapshot_glob) == 0

    # 실행.
    with asyncio_loop_and_runner as lnr:
        lnr[1](tbody())

    # snapshot 디렉토리 목록 - 스냅샷 생성되었는지?
    after_snapshot_glob = glob(str(snapshot_glob_path))
    assert len(after_snapshot_glob) > 0


@mark.skipif(is_system_test_disabled(), reason='system test')
def test_sigkill_does_not_produce_snapshot(
        oev8_sh_cmd,
        oev8_sys_test_fixture,
        # cmd_client
        tcp_cmd_client,
        # asyncio
        asyncio_loop_and_runner,
        # fs paths
        test_config_path
):
    'SIGKILL으로 강제 종료시 스냅샷 생성 안하는지?'
    # local definitions:
    async def tbody():
        # start process.
        cfg_fn = str(test_config_path.resolve())
        proc = await asyncio.create_subprocess_exec(
            *(oev8_sh_cmd + [cfg_fn]))

        logger.debug('PID(%s) Running?(%s)',
                     proc.pid, proc.returncode is None)

        # try to connect...
        async def connect_and_ping():
            logger.info('TCP Client CONNECTING...')
            await tcp_cmd_client.client.connect()
            logger.info('TCP Client CONNECTED..')

            logger.info('PONG? %s', await tcp_cmd_client.ping())

        await async_retry(connect_and_ping, max_retries=10, delay_secs=1)

        # kill immediately: by SIGKILL.
        proc.kill()
        retcode = await proc.wait()
        logger.info('Terminated with: %s', retcode)

    # testing steps:
    # snapshot 디렉토리 목록 - 비어 있는지?
    snapshot_glob_path = \
        oev8_sys_test_fixture.snapshot_output_dir / "*"

    before_snapshot_glob = glob(str(snapshot_glob_path))
    assert len(before_snapshot_glob) == 0

    # 실행.
    with asyncio_loop_and_runner as lnr:
        lnr[1](tbody())

    # snapshot 디렉토리 목록 - 스냅샷 생성되었는지?
    after_snapshot_glob = glob(str(snapshot_glob_path))
    assert len(after_snapshot_glob) == 0


@mark.skipif(is_system_test_disabled(), reason='system test')
def test_shutdown_cmd_does_not_produce_snapshot(
        oev8_sh_cmd,
        oev8_sys_test_fixture,
        # cmd_client
        tcp_cmd_client,
        # asyncio
        asyncio_loop_and_runner,
        # fs paths
        test_config_path
):
    'SHUTDOWN CMD으로 종료시 스냅샷 생성 안하는지?'
    # local definitions:
    async def tbody():
        # start process.
        cfg_fn = str(test_config_path.resolve())
        proc = await asyncio.create_subprocess_exec(
            *(oev8_sh_cmd + [cfg_fn]))

        logger.debug('PID(%s) Running?(%s)',
                     proc.pid, proc.returncode is None)

        # try to connect...
        async def connect_and_ping():
            logger.info('TCP Client CONNECTING...')
            await tcp_cmd_client.client.connect()
            logger.info('TCP Client CONNECTED..')

        await async_retry(connect_and_ping, max_retries=10, delay_secs=1)

        try:
            logger.info('SHUTDONW? %s', await tcp_cmd_client.shutdown())
        except:
            logger.debug("CAUGHT EXC on SHUTDOWN (and it's okay)",
                         exc_info=True)

        # wait...
        retcode = await proc.wait()
        logger.info('Terminated with: %s', retcode)

    # testing steps:
    # snapshot 디렉토리 목록 - 비어 있는지?
    snapshot_glob_path = \
        oev8_sys_test_fixture.snapshot_output_dir / "*"

    before_snapshot_glob = glob(str(snapshot_glob_path))
    assert len(before_snapshot_glob) == 0

    # 실행.
    with asyncio_loop_and_runner as lnr:
        lnr[1](tbody())

    # snapshot 디렉토리 목록 - 스냅샷 생성되었는지?
    after_snapshot_glob = glob(str(snapshot_glob_path))
    assert len(after_snapshot_glob) == 0
