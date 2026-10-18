"""Тексты бота на русском языке."""

TEXTS: dict[str, str] = {
    # Онбординг
    "start.greeting": "Привет, {name}! Я бот для изучения английского.",
    "start.choose_language": "На каком языке объяснять темы и переводить слова?",
    "start.language_saved": "Отлично, объяснения будут на языке: {language}.",
    "start.choose_timezone": "Теперь выбери часовой пояс — по нему я напомню о занятиях.",
    "start.timezone_saved": "Часовой пояс сохранён: {timezone}. Можно начинать заниматься!",
    "start.already_configured": (
        "С возвращением, {name}! Язык объяснений: {language}, часовой пояс: {timezone}."
    ),
    "start.commands_hint": "Список команд — в меню рядом с полем ввода.",
    # Общие
    "common.friend": "друг",
    "common.error": "Что-то пошло не так. Попробуй ещё раз чуть позже.",
    "common.language_not_supported": "Такой язык не поддерживается, выбери один из вариантов.",
    "common.timezone_invalid": "Не удалось распознать часовой пояс, выбери один из вариантов.",
    # Названия языков (одинаковые в обоих языках)
    "language.ru": "Русский",
    "language.en": "English",
    # Часовые пояса
    "timezone.utc": "UTC",
    "timezone.moscow": "Москва",
    "timezone.london": "Лондон",
    "timezone.berlin": "Берлин",
    "timezone.tashkent": "Ташкент",
    "timezone.samarkand": "Самарканд",
    "timezone.new_york": "Нью-Йорк",
    # Команды в меню Telegram
    "commands.start": "Запустить бота",
    "commands.quiz": "Квиз с вопросами",
    "commands.free_chat": "Свободный разговор",
    "commands.close_free_chat": "Закрыть свободный разговор",
    "commands.daily_vocabulary": "20 слов на день",
    "commands.daily_grammar": "Урок грамматики",
    "commands.essay_checker": "Проверить эссе",
    "commands.level_detector": "Определить уровень",
}