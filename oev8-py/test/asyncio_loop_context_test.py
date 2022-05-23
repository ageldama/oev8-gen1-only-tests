from unittest.mock import AsyncMock
from pytest import mark, raises  # type:ignore
from oev8.excs import FatalError


@mark.int
def test_asyncio_loop_context_simple(asyncio_loop_and_runner):
    fn = AsyncMock(return_value=42)

    with asyncio_loop_and_runner as lnr:
        ret = lnr[1](fn())
        assert 42 == ret


@mark.int
def test_asyncio_loop_context_error(asyncio_loop_and_runner):
    fn = AsyncMock(side_effect=FatalError)

    with raises(FatalError):
        with asyncio_loop_and_runner as lnr:
            ret = lnr[1](fn())
