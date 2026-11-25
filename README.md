# FOX REPORTER

Telegram bot for receiving text reports, storing them in SQLite, and forwarding them to the configured owner.

## Requirements
- Python 3.11 or newer
- Telegram bot token from BotFather
- Numeric Telegram user ID of the report recipient/owner

## Environment variables
Set these in the hosting provider's Environment/Secrets settings:

- `BOT_TOKEN`: Telegram bot token
- `OWNER_ID`: numeric Telegram user ID that receives reports

Do not commit real credentials or a `.env` file to a public repository.

## FadeHost / worker deployment
1. Upload the project files to the repository root.
2. Configure `BOT_TOKEN` and `OWNER_ID` in the app's Environment settings.
3. Install dependencies from `requirements.txt`.
4. Start the worker with `python bot.py` (the included `Procfile` uses this command).

This project uses polling and does not require a challenge server, `CHALLENGE_SHARED_SECRET`, a web server, or any Vynexa Stars/VPN environment variables.

## Local run
```bash
python -m pip install -r requirements.txt
python bot.py
```

Reports are stored in `fox_reporter.db` in the working directory. Keep persistent storage enabled on the host if reports must survive redeployments.
