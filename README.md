# LinguaFlame

Telegram bot for learning English with an AI backend. It runs quizzes, daily
vocabulary sets, step-by-step grammar lessons, IELTS essay checks, a level test,
and a free conversation mode, and keeps the learner consistent with a daily
streak plus reminders.

## Features

| Command | What it does |
|---|---|
| `/start` | Onboarding: pick native language and timezone; running it again shows the current profile. |
| `/quiz` | Multiple-choice questions (A/B/C) one at a time with feedback and a final score. |
| `/daily_vocabulary` | 20 words for the day with transcription and translation to the user's language; sets from the last 7 days are not repeated. |
| `/daily_grammar` | Step-by-step grammar lesson: explanation, examples, exercises, a mid-lesson question, and a 5-question mini-test at the end; unfinished lessons can be resumed. |
| `/level_detector` | 50 questions (grammar and vocabulary) that assign a CEFR level A1–C2; answer speed adds a bonus to the score. |
| `/essay_checker` | Essay check against IELTS Writing Task 2 criteria: overall band, criterion scores, and weak spots; texts of 80–500 words. |
| `/free_chat` | Open conversation with the bot; history is kept for the last 10 messages. `/close_free_chat` ends the mode and clears the history. |
| `/stats` | Current streak, personal best, and activity count for the last 7 days. |

Quiz questions come from a bundled question bank
(`bot/data/level_questions.json`, loaded into the database); when the bank has
no suitable question, one is generated through the AI backend.

## Streak and reminders

Every learning action (quiz, lesson, vocabulary, essay, chat, level test) calls
`register_activity`, which updates the daily streak:

- the streak counts calendar days in the user's timezone;
- the first action of a day adds +1, later actions the same day do not grow it;
- a missed day resets the streak to 1 on the next action;
- `best_streak` stores the record and never decreases.

An hourly APScheduler job sends reminders (times are local to the user):

- 09:00 morning reminder if there was no activity today;
- 20:00 evening reminder with the current streak, also only on an inactive day;
- 10:00 the day after a missed day ("where are you?" plus the lost streak);
- further gentle reminders after 3 and 7 days without activity;
- after 7 silent days, sending stops until the next activity;
- at most 2 scheduler messages per day, and rerunning the check in the same
  hour does not duplicate them.

Reminders have a quick-start button that returns 5 words and counts as a
learning action.

## Stack

- Python 3.12, asyncio, aiogram 3
- PostgreSQL (SQLite for local development), SQLAlchemy 2 async, Alembic
- Redis: FSM storage (falls back to in-process memory when Redis is
  unavailable) and the APScheduler job store
- APScheduler for reminders
- httpx against an OpenAI-compatible API (OpenRouter by default)
- pydantic-settings for configuration
- pytest + pytest-asyncio for tests

## Project structure

```
bot/
  main.py            entry point: polling, dispatcher, middlewares, menu commands
  webhook.py         webhook mode (aiohttp)
  config.py          settings loaded from environment / .env
  database.py        async engine and session factory
  logging_setup.py   text and JSON logging
  scheduler.py       APScheduler jobs and reminder sending
  models.py          SQLAlchemy models
  states.py          FSM state groups
  keyboards.py       inline keyboards and callback constants
  data/              bundled level question bank (JSON)
  locales/           user-facing texts (en, ru)
  middlewares/       db session, user, AI client, throttle, errors, chat exit
  prompts/           prompt templates for the AI backend
  repositories/      database access
  routers/           one router per command
  services/          business logic without aiogram
migrations/          Alembic migrations
scripts/             question bank loader, manual reminder run
tests/               pytest suite
```

## Quick start

```bash
git clone <repository-url>
cd linguflame

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt # tests and linting

cp .env.example .env               # then fill in the values

python -m bot.main                             # long polling
```

On startup the bot applies Alembic migrations (`alembic upgrade head`) and
loads the bundled question bank, both idempotently. This also makes panel
hosting work, where only `python main.py` is configured as the start command.
The same steps can still be run manually:

```bash
alembic upgrade head                    # apply the schema
python -m scripts.load_level_questions  # load the question bank
```

### Environment variables

All settings are read from the environment or from `.env`
(see `.env.example`; `.env` is git-ignored).

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `BOT_TOKEN` | yes | — | Telegram bot token from @BotFather |
| `DATABASE_URL` | no | `sqlite+aiosqlite:///./linguflame.db` | PostgreSQL: `postgresql+asyncpg://user:pass@host:5432/linguflame` |
| `REDIS_URL` | no | `redis://localhost:6379/0` | FSM storage and scheduler job store |
| `AI_SERVER_URL` | no | `https://openrouter.ai/api/v1` | Base URL of the OpenAI-compatible API |
| `AI_API_KEY` | for AI features | empty | API key for that service |
| `AI_MODEL` | no | `nvidia/nemotron-3.5-super-vl:free` | Model name |
| `AI_DAILY_LIMIT` | no | `100` | AI requests per user per day (`0` disables the limit) |
| `LOG_LEVEL` | no | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `LOG_JSON` | no | `false` | `true` — structured JSON logs |
| `REMINDER_HOUR_OFFSET` | no | `0` | Shifts scheduler time in hours for manual checks |
| `BOT_MODE` | no | `polling` | `polling` or `webhook` |
| `WEBHOOK_BASE_URL` | for webhook | empty | Public HTTPS base URL |
| `WEBHOOK_PATH` | no | `/telegram/webhook` | Webhook path |
| `WEBHOOK_SECRET` | no | empty | Telegram secret token for incoming updates |
| `WEBHOOK_HOST` / `WEBHOOK_PORT` | no | `0.0.0.0` / `8080` | Local webhook server bind address |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | for Docker | `linguflame` | Credentials for the bundled PostgreSQL container |

Keep real values only in `.env` or in the process environment.

## Docker

`Dockerfile` and `docker-compose.yml` are included. Compose starts PostgreSQL,
Redis, and the bot; the bot itself applies migrations and loads the question
bank before polling starts.

```bash
cp .env.example .env        # fill in BOT_TOKEN (and other values you need)
docker compose up -d --build
docker compose ps
docker compose logs -f bot
```

`docker compose down` stops the containers and keeps the data; `down -v`
removes the PostgreSQL and Redis volumes.

For webhook mode set `BOT_MODE=webhook` and `WEBHOOK_BASE_URL`, and publish the
port in `docker-compose.yml` (the `ports` section for the bot service is
included but commented out). A TLS reverse proxy in front of the bot is
required by Telegram.

## Tests

```bash
pytest -q
pytest --cov=bot --cov-report=term-missing   # with coverage (pytest-cov)
ruff check .                                 # linting
ruff format .                                # formatting
```

## License

MIT — see [LICENSE](LICENSE).
