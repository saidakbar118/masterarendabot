import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/rental_bot")
DB_POOL_MIN  = int(os.getenv("DB_POOL_MIN", "3"))
DB_POOL_MAX  = int(os.getenv("DB_POOL_MAX", "15"))
