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
    # Тест уровня
    "level.loading": "⏳ Готовлю тест…",
    "level.intro": "🎯 Тест уровня: 50 вопросов, отвечай в своём темпе.",
    "level.question": "Вопрос {number} из {total}\n\n{text}",
    "level.retake": (
        "Сейчас у тебя уровень {level} (тест от {date}).\nПройти тест заново?"
    ),
    "level.start_button": "🎯 Пройти тест",
    "level.canceled": "Хорошо, тест отменён. Запустить снова: /level_detector",
    "level.already_running": "Тест уже идёт — отвечай на вопрос.",
    "level.bank_empty": (
        "Тест временно недоступен: банк вопросов не загружен. Попробуй позже."
    ),
    "level.not_active": "Тест уровня сейчас не идёт. Запусти его: /level_detector",
    "level.already_answered": "Ответ на этот вопрос уже принят.",
    "level.invalid_option": "Не понял вариант ответа. Попробуй ещё раз.",
    "level.answer_saved": "✅ Ответ принят. Вопрос {number} из {total}",
    "level.resume": "Продолжаю тест: вопрос {number} из {total}.",
    "level.result": (
        "🎯 Твой уровень: {level}\n\n"
        "Правильных ответов: {correct} из {total} ({accuracy:.0f}%)\n"
        "Среднее время: {average:.1f} с\n\n"
        "Грамматика: {grammar:.0f}%\n"
        "Словарь: {vocabulary:.0f}%"
    ),
    "level.result_balanced": "Грамматика и словарь — на одном уровне.",
    "level.result_strength": "💪 Сильная сторона: {topic}.",
    "level.result_weakness": "📌 Стоит подтянуть: {topic}.",
    "level.topic.grammar": "грамматика",
    "level.topic.vocabulary": "словарь",
    "level.result_done": (
        "Уровень обновлён. Продолжай заниматься: /daily_grammar и /daily_vocabulary."
    ),
    # Урок грамматики
    "grammar.loading": "⏳ Готовлю урок… Обычно это занимает до минуты.",
    "grammar.default_level": (
        "Уровень пока не определён, поэтому урок уровня {level}. "
        "Пройди /level_detector, чтобы уроки подходили под твой уровень."
    ),
    "grammar.step_header": "📘 {topic} · шаг {number} из {total}",
    "grammar.exercise_header": (
        "✍️ {topic} · упражнение {number} из {total}\nНапиши ответ сообщением."
    ),
    "grammar.next_button": "▶️ Дальше",
    "grammar.continue_button": "▶️ Продолжить урок",
    "grammar.continue_button_short": "▶️ Продолжить",
    "grammar.restart_button": "🔄 Начать заново",
    "grammar.continued": "Продолжаем урок «{topic}».",
    "grammar.resume_prompt": (
        "У тебя есть незавершённый урок «{topic}». {progress}\n"
        "Продолжить или начать заново?"
    ),
    "grammar.progress_step": "Остановились на шаге {number} из {total}.",
    "grammar.progress_test": "Остался финальный мини-тест.",
    "grammar.exercise_correct": "✅ Верно!",
    "grammar.exercise_wrong": "❌ Неверно. Правильный ответ: {answer}",
    "grammar.question_return": "💬 Возвращаемся к уроку.",
    "grammar.test_intro": "🏁 Мини-тест по теме «{topic}». Отвечай кнопками.",
    "grammar.test_header": "🏁 Мини-тест · вопрос {number} из {total}",
    "grammar.test_correct": "✅ Верно!",
    "grammar.test_wrong": "❌ Неверно. Правильный ответ: {option}) {answer}",
    "grammar.test_result": "🏁 Мини-тест: {correct} из {total}",
    "grammar.test_mistakes_title": "Разбор ошибок:",
    "grammar.test_mistake": "{number}. {question}\nПравильный ответ: {option}) {answer}",
    "grammar.test_perfect": "Все ответы верные! Отличная работа.",
    "grammar.lesson_done": "Урок «{topic}» завершён. Новый урок: /daily_grammar",
    "grammar.test_use_buttons": "Выбери вариант кнопкой под вопросом.",
    "grammar.not_active": "Урок сейчас не идёт. Начни новый: /daily_grammar",
    "grammar.already_answered": "На этот вопрос уже ответили.",
    "grammar.stale_button": "Эта кнопка уже неактуальна.",
    "grammar.invalid_option": "Не понял вариант ответа. Попробуй ещё раз.",
    # Проверка эссе
    "essay.prompt": (
        "📝 Пришли эссе на английском: от {min_words} до {max_words} слов.\n"
        "Можно первой строкой указать тему — проверю, насколько она раскрыта."
    ),
    "essay.loading": "⏳ Проверяю эссе… Обычно это занимает до минуты.",
    "essay.too_short": (
        "Эссе слишком короткое: {words} слов. Нужно от {min_words} до {max_words} слов. "
        "Допиши текст и пришли его снова."
    ),
    "essay.too_long": (
        "Эссе слишком длинное: {words} слов. Нужно от {min_words} до {max_words} слов. "
        "Сократи текст и пришли его снова."
    ),
    "essay.title": "📝 Оценка: {band} / 9",
    "essay.criterion.task_response": "Task Response",
    "essay.criterion.coherence": "Coherence and Cohesion",
    "essay.criterion.lexical_resource": "Lexical Resource",
    "essay.criterion.grammar": "Grammatical Range and Accuracy",
    "essay.weak_title": "⚠️ Слабые места:",
    "essay.weak_item": "{index}. «{quote}»: {problem} → «{fix}»",
    "essay.no_weak": "✅ Слабых мест не нашлось.",
    "essay.strengths": "✅ Сильные стороны: {summary}",
    "essay.main_advice": (
        "🎯 Что улучшить в первую очередь: {criterion} ({score} / 9) — {hint}"
    ),
    "essay.hint.task_response": "убедись, что тема раскрыта, а позиция подкреплена примерами",
    "essay.hint.coherence": "следи за логикой абзацев и связками между идеями",
    "essay.hint.lexical_resource": "расширяй словарь и избегай повторов",
    "essay.hint.grammar": "проверяй согласование, времена и порядок слов",
    "essay.disclaimer": (
        "⚠️ Оценка ориентировочная и не заменяет официальный экзамен IELTS."
    ),
    # Свободный разговор
    "chat.started": (
        "💬 Свободный разговор открыт. Пиши на любом языке — отвечу на твоём, "
        "а ошибки в английском мягко поправлю.\n\nЗакрыть разговор: /close_free_chat"
    ),
    "chat.closed": (
        "👋 Свободный разговор закрыт, история очищена. Начать снова: /free_chat"
    ),
    "chat.not_active": "Свободный разговор сейчас не идёт. Начать: /free_chat",
    # Общие
    "common.friend": "друг",
    "common.cancel": "Отмена",
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