from database import get_db
from utils import now_utc, days_since
from services.tool_service import decrease_tool_stock, increase_tool_stock


async def create_rental(user_id: int, customer_name: str, customer_address: str,
                        customer_phone: str, items: list[dict]) -> int | None:
    try:
        async with get_db() as conn:
            rental_id = await conn.fetchval(
                """INSERT INTO rentals (user_id, customer_name, customer_address, customer_phone)
                   VALUES ($1,$2,$3,$4) RETURNING id""",
                user_id, customer_name, customer_address, customer_phone
            )
            for item in items:
                ok = await decrease_tool_stock(conn, item["tool_id"], item["quantity"])
                if not ok:
                    raise ValueError(f"Not enough stock for tool {item['tool_id']}")
                await conn.execute(
                    """INSERT INTO rental_items (rental_id, tool_id, quantity, daily_price)
                       VALUES ($1,$2,$3,$4)""",
                    rental_id, item["tool_id"], item["quantity"], item["daily_price"]
                )
        return rental_id
    except Exception:
        return None


async def get_active_rentals(user_id: int, offset: int = 0, limit: int = 10):
    async with get_db() as conn:
        rows  = await conn.fetch(
            """SELECT * FROM rentals WHERE user_id=$1 AND status='active'
               ORDER BY rental_date DESC LIMIT $2 OFFSET $3""",
            user_id, limit, offset
        )
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM rentals WHERE user_id=$1 AND status='active'", user_id
        )
        return rows, count


async def search_rentals(user_id: int, query: str):
    async with get_db() as conn:
        q = f"%{query}%"
        return await conn.fetch(
            """SELECT * FROM rentals WHERE user_id=$1 AND status='active'
               AND (customer_name ILIKE $2 OR customer_phone ILIKE $3)""",
            user_id, q, q
        )


async def get_rental_by_id(rental_id: int):
    async with get_db() as conn:
        return await conn.fetchrow("SELECT * FROM rentals WHERE id=$1", rental_id)


async def get_rental_items(rental_id: int):
    async with get_db() as conn:
        return await conn.fetch(
            """SELECT ri.*, t.name AS tool_name, t.quantity AS stock
               FROM rental_items ri JOIN tools t ON t.id = ri.tool_id
               WHERE ri.rental_id=$1""",
            rental_id
        )


async def calculate_rental_cost(rental_id: int) -> float:
    async with get_db() as conn:
        rental = await conn.fetchrow("SELECT rental_date FROM rentals WHERE id=$1", rental_id)
        if not rental:
            return 0.0
        days  = days_since(rental["rental_date"])
        items = await conn.fetch(
            "SELECT daily_price, quantity, returned_quantity FROM rental_items WHERE rental_id=$1",
            rental_id
        )
        total = sum(
            float(i["daily_price"]) * (i["quantity"] - i["returned_quantity"]) * days
            for i in items
        )
        return round(total, 2)


async def calculate_return_cost(rental_id: int, returns: list[dict]) -> float:
    """
    Fixed: was doing 1 DB query per item (N+1 problem).
    Now fetches all items in a single query using ANY($1).
    """
    if not returns:
        return 0.0
    async with get_db() as conn:
        rental = await conn.fetchrow("SELECT rental_date FROM rentals WHERE id=$1", rental_id)
        if not rental:
            return 0.0
        days = days_since(rental["rental_date"])

        # One query for all items instead of one per item
        item_ids = [ret["item_id"] for ret in returns]
        qty_map  = {ret["item_id"]: ret["quantity"] for ret in returns}
        rows = await conn.fetch(
            "SELECT id, daily_price FROM rental_items WHERE id = ANY($1::bigint[])",
            item_ids
        )
        total = sum(float(r["daily_price"]) * qty_map[r["id"]] * days for r in rows)
        return round(total, 2)


async def get_already_paid(rental_id: int) -> float:
    async with get_db() as conn:
        val = await conn.fetchval(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE rental_id=$1", rental_id
        )
        return round(float(val or 0), 2)


async def process_return(rental_id: int, returns: list[dict]) -> None:
    """
    Fixed: was doing 1 DB query per item to fetch before update (N+1 problem).
    Now locks all rows at once with ANY($1) FOR UPDATE, then updates each.
    """
    async with get_db() as conn:
        # Lock all rows in one query
        item_ids = [ret["item_id"] for ret in returns]
        items = await conn.fetch(
            "SELECT * FROM rental_items WHERE id = ANY($1::bigint[]) FOR UPDATE",
            item_ids
        )
        items_map = {item["id"]: item for item in items}

        for ret in returns:
            item = items_map.get(ret["item_id"])
            if not item:
                continue
            qty = min(ret["quantity"], item["quantity"] - item["returned_quantity"])
            if qty <= 0:
                continue
            await conn.execute(
                "UPDATE rental_items SET returned_quantity = returned_quantity + $1 WHERE id=$2",
                qty, ret["item_id"]
            )
            await increase_tool_stock(conn, ret["tool_id"], qty)

        remaining = await conn.fetchval(
            """SELECT COALESCE(SUM(quantity - returned_quantity), 0)
               FROM rental_items WHERE rental_id=$1""",
            rental_id
        )
        if (remaining or 0) <= 0:
            await conn.execute(
                "UPDATE rentals SET status='returned' WHERE id=$1", rental_id
            )


async def close_rental(rental_id: int):
    async with get_db() as conn:
        await conn.execute(
            "UPDATE rentals SET status='closed' WHERE id=$1", rental_id
        )


async def is_fully_returned(rental_id: int) -> bool:
    async with get_db() as conn:
        remaining = await conn.fetchval(
            """SELECT COALESCE(SUM(quantity - returned_quantity), 0)
               FROM rental_items WHERE rental_id=$1""",
            rental_id
        )
        return (remaining or 0) <= 0


async def get_unreturned_items(rental_id: int):
    async with get_db() as conn:
        return await conn.fetch(
            """SELECT ri.*, t.name AS tool_name
               FROM rental_items ri JOIN tools t ON t.id = ri.tool_id
               WHERE ri.rental_id=$1 AND (ri.quantity - ri.returned_quantity) > 0""",
            rental_id
        )
