from database import get_db


async def get_user_by_telegram_id(telegram_id: int):
    async with get_db() as conn:
        return await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1", telegram_id
        )


async def get_user_by_id(user_id: int):
    async with get_db() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)


async def create_user(full_name: str, shop_name: str, address: str,
                      phone: str, telegram_id: int) -> bool:
    try:
        async with get_db() as conn:
            await conn.execute(
                """INSERT INTO users (full_name, shop_name, address, phone, telegram_id)
                   VALUES ($1, $2, $3, $4, $5)""",
                full_name, shop_name, address, phone, telegram_id
            )
        return True
    except Exception:
        return False


async def get_all_users(offset: int = 0, limit: int = 10):
    async with get_db() as conn:
        rows  = await conn.fetch(
            "SELECT * FROM users ORDER BY id DESC LIMIT $1 OFFSET $2", limit, offset
        )
        count = await conn.fetchval("SELECT COUNT(*) FROM users")
        return rows, count


async def search_users(query: str):
    async with get_db() as conn:
        q = f"%{query}%"
        return await conn.fetch(
            "SELECT * FROM users WHERE full_name ILIKE $1 OR phone ILIKE $2", q, q
        )


async def activate_user(user_id: int):
    async with get_db() as conn:
        await conn.execute("UPDATE users SET is_active = TRUE  WHERE id = $1", user_id)


async def deactivate_user(user_id: int):
    async with get_db() as conn:
        await conn.execute("UPDATE users SET is_active = FALSE WHERE id = $1", user_id)


async def delete_user(user_id: int):
    async with get_db() as conn:
        await conn.execute("DELETE FROM users WHERE id = $1", user_id)


async def update_user(user_id: int, full_name: str, shop_name: str,
                      address: str, phone: str):
    async with get_db() as conn:
        await conn.execute(
            "UPDATE users SET full_name=$1, shop_name=$2, address=$3, phone=$4 WHERE id=$5",
            full_name, shop_name, address, phone, user_id
        )
