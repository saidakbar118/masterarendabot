# Rental Bot — O'rnatish

## Talab qilinadigan dasturlar
- Python 3.11+
- PostgreSQL (istalgan versiya)

## O'rnatish

```bash
# 1. Kutubxonalarni o'rnating
pip install -r requirements.txt

# 2. .env fayl yarating
copy .env.example .env      # Windows
cp .env.example .env        # Linux/Mac

# 3. .env faylni tahrirlang — faqat 3 ta narsa kerak:
BOT_TOKEN=your_bot_token
SUPER_ADMIN_ID=your_telegram_id
DATABASE_URL=postgresql://user:password@localhost:5432/rental_bot

# 4. PostgreSQL da database yarating
createdb rental_bot
# yoki pgAdmin orqali "rental_bot" nomli database yarating

# 5. Botni ishga tushiring
python main.py
```

## Shundan boshqa hech narsa kerak emas.
Jadvallar birinchi ishga tushirganda avtomatik yaratiladi.
