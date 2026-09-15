# Telegram bot — aiogram 3

```text
Telegram → aiogram → Django REST API → PostgreSQL
```

The bot holds **no database credentials and no business logic**. It renders what
the API returns, so permissions and aggregations can only be computed in one
place. See the [root README](../README.md) for the whole-project picture.

## Run

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # BOT_TOKEN, BOT_SERVICE_TOKEN, BACKEND_API_URL
python main.py
```

The backend must be running and `BOT_SERVICE_TOKEN` must match its value.

## Layout

```text
bot/
├── handlers/     start + linking, attendance, children, notifications, fallback
├── keyboards/    reply menu + inline keyboards
├── middlewares/  API-error → friendly reply, structured logging
├── services/     api.py (the only I/O), formatting.py (message rendering)
├── states/       FSM for the linking flow
└── config.py     environment-driven configuration
main.py           entry point: dispatcher, middlewares, routers, commands
```

## Commands

| Command | Button | What |
|---|---|---|
| `/start` | — | start / link the account |
| `/menu` | — | main menu |
| `/bugun` | 📊 Bugungi davomat | today |
| `/hafta` | 📅 Haftalik davomat | this week |
| `/oy` | 📈 Oylik davomat | this month |
| `/yil` | 📆 Yillik davomat | the academic year |
| `/farzandlar` | 👦 Farzandlarim | pick the active child |
| `/bildirishnomalar` | 🔔 Bildirishnomalar | latest notifications |
| `/sozlamalar` | ⚙️ Sozlamalar | mute notifications, unlink |
| `/help` | — | help |

## Linking and security

The bot authenticates to the API with a single shared secret
(`X-Bot-Token: BOT_SERVICE_TOKEN`) — never a user JWT. A Telegram id alone is
never treated as proof of identity: the backend only trusts it after a one-time
token, issued from the authenticated web cabinet, has been redeemed. Tokens are
stored hashed, are single-use and expire after 15 minutes.

Outbound notifications are pushed by the backend (Celery → Telegram Bot API),
not by this process, so the bot stays a read-only presentation layer.

## Notes

- Set `REDIS_URL` to share FSM state across replicas; without it the bot uses
  in-memory storage and must run as a single instance.
- Long polling is used by default. For several replicas behind a load balancer,
  switch to a webhook.
- Messages are never logged — a linking message contains a one-time code, so the
  logging middleware records metadata only.
