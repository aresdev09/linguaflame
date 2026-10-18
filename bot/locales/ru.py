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
    # Прогресс и серия дней
    "stats.title": "Твой прогресс",
    "stats.current": "🔥 Текущая серия: {days} дн.",
    "stats.best": "🏆 Рекорд: {days} дн.",
    "stats.week": "📅 Действий за неделю: {count}",
    "stats.hint": "Сделай одно задание, чтобы зажечь огонёк.",
    # Слова дня
    "vocabulary.loading": (
        "⏳ Подбираю 20 слов на сегодня… Обычно это занимает до минуты."
    ),
    "vocabulary.title": "📚 Слова дня · уровень {level}",
    "vocabulary.reused": "Сегодняшний набор уже сохранён — вот он.",
    "vocabulary.default_level": (
        "Уровень пока не определён, поэтому слова уровня {level}. "
        "Пройди /level_detector, чтобы получать слова под свой уровень."
    ),
    "vocabulary.item": "{index}. {word} {transcription} — {translation}",
    # Квиз
    "quiz.loading": "⏳ Подбираю вопрос…",
    "quiz.question": "Вопрос {number}\n\n{text}",
    "quiz.correct": "✅ Верно!",
    "quiz.wrong": "❌ Неверно.",
    "quiz.correct_answer": "Правильный ответ: {option}) {answer}",
    "quiz.finish_button": "🏁 Закончить",
    "quiz.result": "🏁 Квиз завершён\n\nПравильных ответов: {correct} из {total}.",
    "quiz.result_empty": (
        "🏁 Квиз завершён\n\nТы не ответил ни на один вопрос. Начни новый: /quiz"
    ),
    "quiz.already_answered": "На этот вопрос уже ответили.",
    "quiz.not_active": "Квиз сейчас не идёт. Начни новый: /quiz",
    "quiz.invalid_option": "Не понял вариант ответа. Попробуй ещё раз.",
    # Общие
    "common.friend": "друг",
    "common.error": "Что-то пошло не так. Попробуй ещё раз чуть позже.",
    "common.language_not_supported": "Такой язык не поддерживается, выбери один из вариантов.",
    "common.timezone_invalid": "Не удалось распознать часовой пояс, выбери один из вариантов.",
    "common.ai_unavailable": "ИИ-сервер сейчас недоступен. Попробуй чуть позже.",
    "common.ai_bad_answer": "ИИ ответил не так, как ожидалось. Попробуй ещё раз.",
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
    "commands.stats": "Серия и рекорд",
    "commands.quiz": "Квиз с вопросами",
    "commands.free_chat": "Свободный разговор",
    "commands.close_free_chat": "Закрыть свободный разговор",
    "commands.daily_vocabulary": "20 слов на день",
    "commands.daily_grammar": "Урок грамматики",
    "commands.essay_checker": "Проверить эссе",
    "commands.level_detector": "Определить уровень",
}