"""Точка входа для запуска из корня: `python main.py`.

Нужна панелям, которые стартуют процесс как `python main.py`: корень в
sys.path, поэтому пакет `bot` импортируется, в отличие от `python bot/main.py`.
"""

from bot.main import run

if __name__ == "__main__":
    run()
