import sys, asyncio; sys.path.insert(0, '.')
import aiosqlite
from db import SCHEMA
from repositories.interest_repo import InterestRepository
from keyboards.interest_kb import interest_kb

async def main():
    conn = await aiosqlite.connect(':memory:'); conn.row_factory = aiosqlite.Row
    await conn.executescript(SCHEMA); await conn.commit()
    ir = InterestRepository(conn)
    owner = 111
    assert await ir.add(owner, 222) is True
    assert await ir.add(owner, 222) is False
    assert await ir.add(owner, 333) is True
    assert await ir.count(owner) == 2
    print("dedupe+count OK")
    kb = interest_kb(owner, 2)
    assert kb is not None and "(2)" in kb.inline_keyboard[0][0].text
    assert interest_kb(-5, 0) is None
    assert "(" not in interest_kb(owner, 0).inline_keyboard[0][0].text
    print("keyboard OK:", kb.inline_keyboard[0][0].text)
    print("ALL PASS")

asyncio.run(main())
