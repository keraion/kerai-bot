import asyncio


async def scheduled_task(duration, func, *args, **kwargs):
    while True:
        await asyncio.gather(func(*args, **kwargs), asyncio.sleep(duration))
