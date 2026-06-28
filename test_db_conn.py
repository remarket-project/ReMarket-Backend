import asyncio
import logging

logging.disable()
from sqlmodel import text

from app.db.session import AsyncSessionLocal


async def t():
    async with AsyncSessionLocal() as s:
        r = await s.exec(text('SELECT 1 as v'))
        print('remarket connected:', r.first().v)

asyncio.run(t())
