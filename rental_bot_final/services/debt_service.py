from database import get_db
from utils import now_utc


async def add_debt(user_id: int, customer_name: str, customer_phone: str,
                   amount: float, rental_id: int = None):
    async with get_db() as conn:
        if rental_id is not None:
            existing = await conn.fetchrow(
                "SELECT id, amount FROM debts WHERE user_id=$1 AND rental_id=$2 AND amount > 0",
                user_id, rental_id
            )
            if existing:
                new_amount = round(float(existing["amount"]) + amount, 2)
                await conn.execute(
                    "UPDATE debts SET amount=$1, customer_name=$2, customer_phone=$3 WHERE id=$4",
                    new_amount, customer_name, customer_phone, existing["id"]
                )
                return

        await conn.execute(
            """INSERT INTO debts (user_id, customer_name, customer_phone, amount, rental_id)
               VALUES ($1,$2,$3,$4,$5)""",
            user_id, customer_name, customer_phone, round(amount, 2), rental_id
        )


async def get_debts(user_id: int, offset: int = 0, limit: int = 10):
    async with get_db() as conn:
        rows  = await conn.fetch(
            """SELECT * FROM debts WHERE user_id=$1 AND amount > 0
               ORDER BY created_at DESC LIMIT $2 OFFSET $3""",
            user_id, limit, offset
        )
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM debts WHERE user_id=$1 AND amount > 0", user_id
        )
        return rows, count


async def search_debts(user_id: int, query: str):
    async with get_db() as conn:
        q = f"%{query}%"
        return await conn.fetch(
            """SELECT * FROM debts WHERE user_id=$1 AND amount > 0
               AND (customer_name ILIKE $2 OR customer_phone ILIKE $3)""",
            user_id, q, q
        )


async def get_debt_by_id(debt_id: int):
    async with get_db() as conn:
        return await conn.fetchrow("SELECT * FROM debts WHERE id=$1", debt_id)


async def pay_debt(debt_id: int, amount: float) -> float:
    async with get_db() as conn:
        row = await conn.fetchrow(
            "SELECT amount FROM debts WHERE id=$1 FOR UPDATE", debt_id
        )
        if not row:
            return 0.0
        try:
            payment = float(amount)
        except (TypeError, ValueError):
            payment = 0.0

        remaining = round(max(float(row["amount"]) - payment, 0.0), 2)
        await conn.execute("UPDATE debts SET amount=$1 WHERE id=$2", remaining, debt_id)
        return remaining


async def get_total_debt(user_id: int) -> float:
    async with get_db() as conn:
        val = await conn.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM debts WHERE user_id=$1 AND amount > 0",
            user_id
        )
        return round(float(val or 0), 2)


async def record_payment(user_id: int, rental_id, amount: float):
    async with get_db() as conn:
        await conn.execute(
            "INSERT INTO payments (user_id, rental_id, amount) VALUES ($1,$2,$3)",
            user_id, rental_id, round(amount, 2)
        )
