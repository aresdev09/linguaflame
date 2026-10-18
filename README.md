# AI English Bot (LinguaFlame)

Telegram-бот для изучения английского с ИИ: квиз, слова дня, пошаговые уроки
грамматики, проверка эссе по IELTS, тест уровня, свободный чат и «огонёк»
с ежедневными напоминаниями. Бот подстраивается под уровень (A1–C2) и родной
язык пользователя.

## Стек

- Python 3.12, aiogram 3, asyncio
- PostgreSQL (SQLite для локальной разработки), SQLAlchemy 2 async, Alembic
- Redis для FSM и задач планировщика
- APScheduler для напоминаний
- ИИ через OpenRouter (OpenAI-совместимый API)

## Быстрый старт (локально)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # заполните BOT_TOKEN и AI_API_KEY
alembic upgrade head               # схема БД
python -m scripts.load_level_questions   # банк вопросов для /level_detector
python -m bot.main                 # long polling
```

Проверка:

```bash
pytest -q
pytest -q --cov=bot --cov-report=term-missing   # покрытие ключевой логики
```

## Переменные окружения

| Переменная | Обязательна | По умолчанию | Назначение |
|---|---|---|---|
| `BOT_TOKEN` | да | — | токен от @BotFather |
| `DATABASE_URL` | нет | `sqlite+aiosqlite:///./linguflame.db` | PostgreSQL: `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | нет | `redis://localhost:6379/0` | FSM и jobstore планировщика |
| `AI_SERVER_URL` | нет | `https://openrouter.ai/api/v1` | адрес OpenAI-совместимого API |
| `AI_API_KEY` | для ИИ | пусто | ключ OpenRouter |
| `AI_MODEL` | нет | `nvidia/nemotron-3.5-super-vl:free` | модель |
| `AI_DAILY_LIMIT` | нет | `100` | логических запросов к ИИ на пользователя в день (`0` — без лимита) |
| `LOG_LEVEL` | нет | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `LOG_JSON` | нет | `false` | `true` — структурные JSON-логи для продакшена |
| `REMINDER_HOUR_OFFSET` | нет | `0` | сдвиг часов планировщика для ручной проверки |
| `BOT_MODE` | нет | `polling` | `polling` или `webhook` |
| `WEBHOOK_BASE_URL` | для webhook | пусто | публичный HTTPS-адрес, например `https://bot.example.com` |
| `WEBHOOK_PATH` | нет | `/telegram/webhook` | путь эндпоинта |
| `WEBHOOK_SECRET` | нет | пусто | секрет Telegram для проверки запросов |
| `WEBHOOK_HOST` / `WEBHOOK_PORT` | нет | `0.0.0.0` / `8080` | адрес локального HTTP-сервера |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | для compose | `linguflame` | доступы к контейнеру PostgreSQL |

Секреты храните только в `.env` (он в `.gitignore`) или в переменных окружения.

## Docker Compose

`docker compose up` поднимает PostgreSQL, Redis и бота, применяет миграции
и загружает банк вопросов — всё с нуля, повторные запуски не создают дублей.

```bash
cp .env.example .env          # BOT_TOKEN, AI_API_KEY, при необходимости POSTGRES_PASSWORD
docker compose up -d --build
docker compose ps
docker compose logs -f bot
```

Остановка и удаление данных:

```bash
docker compose down           # контейнеры останавливаются, данные сохраняются
docker compose down -v        # ВНИМАНИЕ: удаляет тома PostgreSQL и Redis
```

`docker compose up -d` читает `.env` из корня проекта для подстановки
переменных. Внутри контейнера `DATABASE_URL` указывает на сервис `db`,
`REDIS_URL` — на `redis`. База и Redis хранятся в томах `pgdata` и `redisdata`.
Изменить схему или код: `docker compose up -d --build` — миграции применятся
при старте контейнера.

## Режимы работы: polling или webhook

Выбран **polling по умолчанию**: ему не нужен домен, HTTPS и открытый порт,
бот сам держит исходящее соединение с Telegram. Этого достаточно для одного
экземпляра на VPS.

`webhook` нужен, если хостинг блокирует long polling или требует входящий
HTTPS-эндпоинт:

1. Поставьте `BOT_MODE=webhook`, `WEBHOOK_BASE_URL=https://bot.example.com`,
   задайте `WEBHOOK_SECRET`.
2. В `docker-compose.yml` раскомментируйте `ports` у сервиса `bot`.
3. Поставьте reverse proxy с TLS, например nginx:

```nginx
server {
    listen 443 ssl;
    server_name bot.example.com;

    location /telegram/webhook {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

При старте бот вызывает `set_webhook`, при остановке — `delete_webhook`.
Не запускайте polling и webhook одновременно на одном токене.

## Обновление схемы БД

Каждое изменение моделей сопровождается миграцией Alembic:

```bash
alembic revision --autogenerate -m "что изменилось"
alembic upgrade head
alembic downgrade -1          # откат последней
```

В Docker миграции применяются автоматически командой в `docker-compose.yml`.

## Ручная проверка

Проверяйте на тестовом аккаунте Telegram. Для каждого пункта смотрите ответ
бота и отсутствие ошибок в `docker compose logs` / консоли.

- `/start` — выбор языка и часового пояса; повторный запуск показывает профиль.
- `/quiz` — вопрос A/B/C, верно/неверно с правильным вариантом, кнопка
  «Закончить», в итоге строка серии.
- `/daily_vocabulary` — 20 слов с транскрипцией и переводом.
- `/daily_grammar` — шаги урока, упражнение текстом, вопрос по уроку и возврат к
  плану, мини-тест из 5 вопросов.
- `/essay_checker` — эссе 80–500 слов; короче/длиннее — отказ без вызова ИИ;
  в разборе балл, критерии, слабые места, оговорка.
- `/level_detector` — 50 вопросов, после завершения уровень меняется; до
  завершения `users.level` не трогается.
- `/free_chat` — диалог, `/close_free_chat` очищает историю; команда другого
  режима закрывает чат.
- `/stats` — серия, рекорд, действия за неделю.

Пропуск дня и серия. В SQLite (локально):

```sql
-- «вчера было действие, сегодня нет»
UPDATE streaks SET last_activity_date = date('now', '-2 day'),
                   reminders_date = NULL, reminders_count = 0
WHERE user_id = <id>;
```

В PostgreSQL (`docker compose exec db psql -U linguflame -d linguflame`):

```sql
UPDATE streaks SET last_activity_date = CURRENT_DATE - INTERVAL '2 day',
                   reminders_date = NULL, reminders_count = 0
WHERE user_id = <id>;
```

Затем:

```bash
python -m scripts.run_reminders --offset <часы>   # один проход сразу
```

Сдвиг добавляется к текущему времени: если сейчас 12:00, `--offset 8` даёт
20:00 — вечернее напоминание; `--offset -3` даёт 09:00 — утреннее.
Проверьте: «Где ты?» после пропуска, сообщение о потерянной серии, отсутствие
больше двух сообщений в сутки, отсутствие дублей при повторном запуске.

Смена часового пояса:

```sql
UPDATE users SET timezone = 'Asia/Samarkand' WHERE id = <id>;
```

После этого запустите `scripts.run_reminders.py` с offset, при котором у
пользователя наступает 09:00/20:00, и убедитесь, что время считается по
новому поясу.

Лимит ИИ проверяется так: поставьте `AI_DAILY_LIMIT=1`, вызовите две
ИИ-команды — вторая ответит «лимит запросов к ИИ исчерпан».

## Деплой на сервер

Пошагово для Ubuntu 22.04/24.04 (действия выполняются вами на сервере).

1. Подготовьте сервер:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y ca-certificates curl git ufw
curl -fsSL https://get.docker.com | sudo sh
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"   # перелогиньтесь
sudo ufw allow 22/tcp && sudo ufw allow 443/tcp && sudo ufw enable
```

2. Скопируйте проект и настройте секреты:

```bash
git clone <repo-url> /opt/linguflame
cd /opt/linguflame
cp .env.example .env
nano .env      # BOT_TOKEN, AI_API_KEY, POSTGRES_PASSWORD, LOG_JSON=true, LOG_LEVEL=INFO
chmod 600 .env
```

3. Запустите (миграции и банк вопросов применятся автоматически):

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 bot
```

4. Автоперезапуск и старт после ребута обеспечивают `restart: unless-stopped`
   у контейнеров и включённый `docker` в systemd. Проверка:

```bash
sudo reboot
# после загрузки:
cd /opt/linguflame && docker compose ps
```

Обновление версии:

```bash
cd /opt/linguflame
git pull
docker compose up -d --build     # миграции применятся при старте
```

5. Резервное копирование PostgreSQL. Создайте `/opt/linguflame/backup.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /opt/linguflame
BACKUP_DIR="${BACKUP_DIR:-/var/backups/linguflame}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%F_%H%M)"
docker compose exec -T db pg_dump -U "${POSTGRES_USER:-linguflame}" \
  -d "${POSTGRES_DB:-linguflame}" | gzip > "$BACKUP_DIR/linguflame_$STAMP.sql.gz"
find "$BACKUP_DIR" -name 'linguflame_*.sql.gz' -mtime +14 -delete
```

```bash
sudo mkdir -p /var/backups/linguflame
sudo crontab -e
# каждый день в 03:30:
30 3 * * * BACKUP_DIR=/var/backups/linguflame /opt/linguflame/backup.sh >> /var/log/linguflame-backup.log 2>&1
```

Проверка восстановления (на тестовой БД, не на продакшене):

```bash
gunzip -c /var/backups/linguflame/linguflame_ДАТА.sql.gz \
  | docker compose exec -T db psql -U linguflame -d linguflame_test
```

Копируйте бэкапы за пределы сервера (`rsync`/S3) — локальный диск не защищает
от потери машины.

## Мониторинг и оповещения

- Логи: `LOG_JSON=true` даёт строки с полями `ts`, `level`, `logger`,
  `message`, `exception`; смотрите `docker compose logs -f --since=1h bot`.
  Ротация уже настроена (`10 MB × 5` на контейнер).
- Ошибки: `docker compose logs --since=10m bot | grep '"level": "ERROR"'`.
  Для оповещений подключите внешний сервис (Uptime Kuma, Better Stack, Sentry
  или собственный cron, который проверяет ERROR-строки и шлёт сообщение в
  Telegram).
- Доступность: контейнеры `db`/`redis` имеют healthcheck; проверяйте
  `docker compose ps` и `docker inspect --format '{{.State.Status}}' <container>`.
  Для polling-бота нет HTTP-порта, поэтому мониторьте процесс контейнера
  (Uptime Kuma push-монитор из cron) и получайте уведомление, если контейнер
  перезапускается.
- Диск и память: `df -h`, `docker system df`; старые образы чистите
  `docker image prune -f`.
- При инциденте: `docker compose logs --tail=200 bot`, проверьте `.env`,
  доступность OpenRouter и Telegram, затем `docker compose restart bot`.
  Логи не содержат текстов эссе и чатов целиком.

## Структура проекта

```
bot/
  main.py          # запуск, роутеры, middleware, планировщик
  scheduler.py     # APScheduler и рассылка напоминаний
  webhook.py       # режим webhook (aiohttp)
  routers/         # по роутеру на команду
  services/        # бизнес-логика без aiogram
  repositories/    # доступ к БД
  prompts/         # промпты для ИИ
  locales/         # тексты ru/en
migrations/        # Alembic
scripts/           # загрузка вопросов, ручной запуск напоминаний
tests/             # pytest + pytest-asyncio
```
