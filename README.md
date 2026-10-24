# Vynexa Stars

Telegram Stars/Premium order bot for FadeHost. Uses Python 3.11+ and python-telegram-bot 22.x.

## FadeHost
- Repository: `https://github.com/ablfzlglstan-cell/VynexaStars`
- Runtime: Python
- Install command: `pip install -r requirements.txt`
- Start command: `python bot.py`
- Set environment variables from `.env.example`; never commit real bot tokens.
- `BOT_TOKEN` must be set. `ADMIN_IDS` must contain the numeric Telegram user ID of each admin, comma-separated.
- Set real card details and real prices before enabling sales. Prices are in the configured currency.
- Use persistent disk/storage for the SQLite database so settings, balances, and orders survive redeploys.

## Admin panel
Inside Telegram: edit prices, four links, and button emojis from the admin panel. These settings are saved in SQLite. Product recipient can be self or another username/numeric ID. Telegram Bot API cannot fetch arbitrary private account details from an ID; the bot records the supplied recipient identifier.

Orders and fulfillment are manually reviewed by admins. This bot does not automatically deliver Premium or Stars.
