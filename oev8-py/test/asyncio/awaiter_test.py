from unittest.mock import AsyncMock
from pytest import mark, raises  # type:ignore
from oev8.asyncio import Awaiter


@mark.asyncio
async def test_awaiter__with_empty(event_loop):
    awaiter = Awaiter(event_loop)
    await awaiter.gather_queue()


@mark.asyncio
async def test_awaiter__with_one(event_loop):
    awaiter = Awaiter(event_loop)

    mock1 = AsyncMock(return_value=42)
    awaiter.add_awaitable(mock1())

    await awaiter.gather_queue()

    mock1.assert_awaited_once()


@mark.asyncio
async def test_awaiter__with_two(event_loop):
    awaiter = Awaiter(event_loop)

    mock1 = AsyncMock(return_value=42)
    awaiter.add_awaitable(mock1())
    mock1.assert_not_awaited()

    mock2 = AsyncMock(return_value='b')
    awaiter.add_awaitable(mock2())
    mock2.assert_not_awaited()

    await awaiter.gather_queue()

    mock1.assert_awaited_once()
    mock2.assert_awaited_once()


@mark.asyncio
async def test_awaiter__with_exception(event_loop):
    awaiter = Awaiter(event_loop)

    mock1 = AsyncMock(side_effect=Exception)
    awaiter.add_awaitable(mock1())

    with raises(Exception):
        await awaiter.gather_queue()
