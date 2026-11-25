# FOX REPORTER

A Telegram bot for receiving text reports and forwarding them to the configured owner.

## Requirements

- Python 3.12
- A Telegram bot token from BotFather
- The numeric Telegram user ID of the bot owner

## Environment variables

Set these in your hosting provider's environment/secrets settings:

- `BOT_TOKEN`: Telegram bot token
- `OWNER_ID`: numeric Telegram user ID that receives new reports

Do not upload real credentials or a `.env` file to a public repository.

## Run locally

```bash
python -m pip install -r requirements.txt
python bot.py
```

## Hosting

The included `Procfile` starts the bot as a worker with `python bot.py`.
Configure `BOT_TOKEN` and `OWNER_ID` in the host's environment variables before deploying.

Reports are stored in the SQLite database file `fox_reporter.db`. Keep persistent storage enabled on the host if report history must survive restarts or redeployments.

## Bot commands

- `/start` — show the main menu
- `/report` — submit a text report
- `/help` — show usage and safety guidance

Only submit information you have the right to share. Do not submit passwords, login codes, phone numbers belonging to others, or Telegram session data.
