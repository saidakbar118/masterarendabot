import asyncpg
from database import get_db


async def get_tools(user_id: int, offset: int = 0, limit: int = 10):
    async with get_db() as conn:
        rows  = await conn.fetch(
            "SELECT * FROM tools WHERE user_id=$1 ORDER BY name LIMIT $2 OFFSET $3",
            user_id, limit, offset
        )
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM tools WHERE user_id=$1", user_id
        )
        return rows, count


async def get_all_tools(user_id: int):
    async with get_db() as conn:
        return await conn.fetch(
            "SELECT * FROM tools WHERE user_id=$1 ORDER BY name", user_id
        )


async def search_tools(user_id: int, query: str):
    async with get_db() as conn:
        return await conn.fetch(
            "SELECT * FROM tools WHERE user_id=$1 AND name ILIKE $2",
            user_id, f"%{query}%"
        )


async def get_tool_by_id(tool_id: int):
    async with get_db() as conn:
        return await conn.fetchrow("SELECT * FROM tools WHERE id=$1", tool_id)


async def create_tool(user_id: int, name: str, quantity: int, daily_price: float) -> bool:
    try:
        async with get_db() as conn:
            await conn.execute(
                "INSERT INTO tools (user_id, name, quantity, daily_price) VALUES ($1,$2,$3,$4)",
                user_id, name, quantity, daily_price
            )
        return True
    except asyncpg.UniqueViolationError:
        return False


async def update_tool_name(tool_id: int, name: str, user_id: int) -> bool:
    try:
        async with get_db() as conn:
            await conn.execute(
                "UPDATE tools SET name=$1 WHERE id=$2 AND user_id=$3",
                name, tool_id, user_id
            )
        return True
    except asyncpg.UniqueViolationError:
        return False


async def update_tool_qty(tool_id: int, quantity: int):
    async with get_db() as conn:
        await conn.execute(
            "UPDATE tools SET quantity=$1 WHERE id=$2", quantity, tool_id
        )


async def update_tool_price(tool_id: int, price: float):
    async with get_db() as conn:
        await conn.execute(
            "UPDATE tools SET daily_price=$1 WHERE id=$2", price, tool_id
        )


async def delete_tool(tool_id: int) -> bool:
    async with get_db() as conn:
        in_use = await conn.fetchval(
            """SELECT COUNT(*) FROM rental_items ri
               JOIN rentals r ON r.id = ri.rental_id
               WHERE ri.tool_id=$1 AND r.status='active'
               AND (ri.quantity - ri.returned_quantity) > 0""",
            tool_id
        )
        if in_use:
            return False
        await conn.execute("DELETE FROM tools WHERE id=$1", tool_id)
    return True


async def decrease_tool_stock(conn: asyncpg.Connection, tool_id: int, amount: int) -> bool:
    """Atomically decrease stock. Uses FOR UPDATE to prevent race conditions."""
    row = await conn.fetchrow(
        "SELECT quantity FROM tools WHERE id=$1 FOR UPDATE", tool_id
    )
    if not row or row["quantity"] < amount:
        return False
    await conn.execute(
        "UPDATE tools SET quantity = quantity - $1 WHERE id=$2", amount, tool_id
    )
    return True


async def increase_tool_stock(conn: asyncpg.Connection, tool_id: int, amount: int):
    await conn.execute(
        "UPDATE tools SET quantity = quantity + $1 WHERE id=$2", amount, tool_id
    )
