
# Referral System Telegram Bot

This is a Telegram referral system bot written in Python using pyTelegramBotAPI. It supports:
- Referral tracking
- Ranking system
- Admin dashboard (upcoming)
- Captcha verification (can be added)
- PostgreSQL DB

## Deployment

Use [Render.com](https://render.com) and add:

- `API_TOKEN`
- `CHANNEL_USERNAME`
- `OWNER_ID`
- `DATABASE_URL`

## Run Locally

```bash
pip install -r requirements.txt
python bot.py
```

## Referral Link

Users can get their referral link via `/link`
