FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Непривилегированный пользователь: боту не нужен root внутри контейнера.
RUN groupadd --system bot && useradd --system --gid bot --create-home bot

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY bot ./bot
COPY migrations ./migrations
COPY scripts ./scripts

USER bot

# Бот применяет миграции и загружает банк вопросов при старте.
CMD ["python", "-m", "bot.main"]
