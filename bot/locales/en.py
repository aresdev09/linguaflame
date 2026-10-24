"""Text messages of the bot in English."""

TEXTS: dict[str, str] = {
    # Onboarding
    "start.greeting": "Hi, {name}! I am a bot for learning English.",
    "start.choose_language": "Which language should I use for explanations and translations?",
    "start.language_saved": "Great, explanations will be in: {language}.",
    "start.choose_timezone": "Now pick your timezone — I will remind you about lessons.",
    "start.timezone_saved": "Timezone saved: {timezone}. You can start learning!",
    "start.already_configured": (
        "Welcome back, {name}! Explanations: {language}, timezone: {timezone}."
    ),
    "start.commands_hint": "The command list is in the menu next to the input field.",
    # Progress and streak
    "stats.title": "Your progress",
    "stats.current": "🔥 Current streak: {days} days",
    "stats.best": "🏆 Best streak: {days} days",
    "stats.week": "📅 Actions this week: {count}",
    "stats.hint": "Complete one task to light the flame.",
    # Words of the day
    "vocabulary.loading": (
        "⏳ Putting together your 20 words for today… It usually takes up to a minute."
    ),
    "vocabulary.title": "📚 Words of the day · level {level}",
    "vocabulary.reused": "Today's set is already saved — here it is.",
    "vocabulary.default_level": (
        "Your level is not set yet, so these are level {level} words. "
        "Take /level_detector to get words that match your level."
    ),
    "vocabulary.item": "{index}. {word} {transcription} — {translation}",
    # Quiz
    "quiz.loading": "⏳ Picking a question…",
    "quiz.question": "Question {number}\n\n{text}",
    "quiz.correct": "✅ Correct!",
    "quiz.wrong": "❌ Not quite.",
    "quiz.correct_answer": "Correct answer: {option}) {answer}",
    "quiz.finish_button": "🏁 Finish",
    "quiz.result": "🏁 Quiz finished\n\nCorrect answers: {correct} out of {total}.",
    "quiz.result_empty": (
        "🏁 Quiz finished\n\nYou haven't answered any questions. Start a new one: /quiz"
    ),
    "quiz.already_answered": "This question has already been answered.",
    "quiz.not_active": "No quiz is running. Start a new one: /quiz",
    "quiz.invalid_option": "I couldn't read that answer option. Please try again.",
    # Level test
    "level.loading": "⏳ Preparing your test…",
    "level.intro": "🎯 Level test: 50 questions, take your time.",
    "level.question": "Question {number} of {total}\n\n{text}",
    "level.retake": ("Your current level is {level} (test taken on {date}).\nTake the test again?"),
    "level.start_button": "🎯 Take the test",
    "level.canceled": "Okay, the test is cancelled. Start again: /level_detector",
    "level.already_running": "A test is already running — answer the question.",
    "level.bank_empty": (
        "The test is temporarily unavailable: the question bank is not loaded. Try later."
    ),
    "level.not_active": "No level test is running. Start it: /level_detector",
    "level.already_answered": "This question has already been answered.",
    "level.invalid_option": "I couldn't read that answer option. Please try again.",
    "level.answer_saved": "✅ Answer accepted. Question {number} of {total}",
    "level.resume": "Resuming the test: question {number} of {total}.",
    "level.result": (
        "🎯 Your level: {level}\n\n"
        "Correct answers: {correct} out of {total} ({accuracy:.0f}%)\n"
        "Average time: {average:.1f} s\n\n"
        "Grammar: {grammar:.0f}%\n"
        "Vocabulary: {vocabulary:.0f}%"
    ),
    "level.result_balanced": "Grammar and vocabulary are on the same level.",
    "level.result_strength": "💪 Strength: {topic}.",
    "level.result_weakness": "📌 Needs work: {topic}.",
    "level.topic.grammar": "grammar",
    "level.topic.vocabulary": "vocabulary",
    "level.result_done": (
        "Your level has been updated. Keep going: /daily_grammar and /daily_vocabulary."
    ),
    "level.reset_notice": (
        "⚠️ We found an issue in the level test: it could set your level too high.\n\n"
        "We have reset your level. Please take the test again: /level_detector"
    ),
    # Grammar lesson
    "grammar.loading": "⏳ Preparing your lesson… It usually takes up to a minute.",
    "grammar.default_level": (
        "Your level is not set yet, so this is a level {level} lesson. "
        "Take /level_detector to get lessons that match your level."
    ),
    "grammar.step_header": "📘 {topic} · step {number} of {total}",
    "grammar.exercise_header": (
        "✍️ {topic} · exercise {number} of {total}\nWrite your answer as a message."
    ),
    "grammar.next_button": "▶️ Next",
    "grammar.continue_button": "▶️ Continue lesson",
    "grammar.continue_button_short": "▶️ Continue",
    "grammar.restart_button": "🔄 Start over",
    "grammar.continued": "Continuing the lesson “{topic}”.",
    "grammar.resume_prompt": (
        "You have an unfinished lesson “{topic}”. {progress}\nContinue or start over?"
    ),
    "grammar.progress_step": "You stopped at step {number} of {total}.",
    "grammar.progress_test": "Only the final mini-test is left.",
    "grammar.exercise_correct": "✅ Correct!",
    "grammar.exercise_wrong": "❌ Not quite. Correct answer: {answer}",
    "grammar.question_return": "💬 Back to the lesson.",
    "grammar.test_intro": "🏁 Mini-test on “{topic}”. Answer with the buttons.",
    "grammar.test_header": "🏁 Mini-test · question {number} of {total}",
    "grammar.test_correct": "✅ Correct!",
    "grammar.test_wrong": "❌ Not quite. Correct answer: {option}) {answer}",
    "grammar.test_result": "🏁 Mini-test: {correct} out of {total}",
    "grammar.test_mistakes_title": "Mistakes to review:",
    "grammar.test_mistake": "{number}. {question}\nCorrect answer: {option}) {answer}",
    "grammar.test_perfect": "All answers are correct! Great job.",
    "grammar.lesson_done": "Lesson “{topic}” is finished. New lesson: /daily_grammar",
    "grammar.test_use_buttons": "Pick an option with the button under the question.",
    "grammar.not_active": "No lesson is running. Start a new one: /daily_grammar",
    "grammar.already_answered": "This question has already been answered.",
    "grammar.stale_button": "This button is no longer relevant.",
    "grammar.invalid_option": "I couldn't read that answer option. Please try again.",
    # Essay check
    "essay.prompt": (
        "📝 Send me an essay in English: {min_words} to {max_words} words.\n"
        "You can put the topic on the first line — I will check how well it is covered."
    ),
    "essay.loading": "⏳ Checking your essay… It usually takes up to a minute.",
    "essay.too_short": (
        "The essay is too short: {words} words. It must be {min_words} to {max_words} "
        "words. Add more text and send it again."
    ),
    "essay.too_long": (
        "The essay is too long: {words} words. It must be {min_words} to {max_words} "
        "words. Shorten it and send it again."
    ),
    "essay.title": "📝 Score: {band} / 9",
    "essay.criterion.task_response": "Task Response",
    "essay.criterion.coherence": "Coherence and Cohesion",
    "essay.criterion.lexical_resource": "Lexical Resource",
    "essay.criterion.grammar": "Grammatical Range and Accuracy",
    "essay.weak_title": "⚠️ Weak spots:",
    "essay.weak_item": "{index}. “{quote}”: {problem} → “{fix}”",
    "essay.no_weak": "✅ No weak spots found.",
    "essay.strengths": "✅ Strengths: {summary}",
    "essay.main_advice": "🎯 Improve first: {criterion} ({score} / 9) — {hint}",
    "essay.hint.task_response": "make sure the topic is covered and the position is supported",
    "essay.hint.coherence": "watch the logic of paragraphs and the links between ideas",
    "essay.hint.lexical_resource": "widen your vocabulary and avoid repetitions",
    "essay.hint.grammar": "check agreement, tenses and word order",
    "essay.disclaimer": (
        "⚠️ This score is approximate and does not replace the official IELTS exam."
    ),
    # Free conversation
    "chat.started": (
        "💬 Free conversation is open. Write in any language — I will answer "
        "in yours and gently correct mistakes in English.\n\n"
        "Close the chat: /close_free_chat"
    ),
    "chat.closed": ("👋 The free conversation is closed, history cleared. Start again: /free_chat"),
    "chat.not_active": "The free conversation is not open. Start it: /free_chat",
    # Streak and reminders
    "streak.line": "🔥 Streak: {days} days",
    "reminder.morning.1": (
        "☀️ Good morning! Have you practised English today? Five minutes and the flame stays on."
    ),
    "reminder.morning.2": ("☀️ Start the morning with English? One short task and today counts."),
    "reminder.morning.3": ("☀️ Hi! Today is not counted yet: do a short task and keep your flame."),
    "reminder.evening.1": (
        "🔥 {days} days in a row! Don't lose the flame — one task before midnight."
    ),
    "reminder.evening.2": (
        "🔥 Your streak is {days} days. There is still time to extend it — start with 5 words."
    ),
    "reminder.evening.3": ("🔥 {days} days in a row is a great result. Keep it going today."),
    "reminder.evening_cold.1": (
        "🌙 The day is almost over and there is no flame yet. Shall we start with 5 words?"
    ),
    "reminder.evening_cold.2": (
        "🌙 Evening is a good time for English. One task and the flame is lit."
    ),
    "reminder.missed.1": (
        "👋 Where are you? Your {days}-day flame went out, but you can light it again "
        "in 2 minutes. Start with 5 words?"
    ),
    "reminder.missed.2": (
        "👋 Where are you? Your {days}-day streak broke, but that is fine. "
        "Five words and the flame is back."
    ),
    "reminder.missed.3": (
        "👋 You were away yesterday and your {days}-day flame went out. "
        "Shall we return? Start with 5 words."
    ),
    "reminder.missed_long.1": (
        "🕯️ {days} days without English — the flame went out long ago. "
        "Shall we come back with 5 words?"
    ),
    "reminder.missed_long.2": (
        "🕯️ {days} days of silence. Let's start again — 5 words are enough to light the flame."
    ),
    "reminder.button": "🔥 5 words",
    "reminder.quick_title": "🔥 Quick start: {count} words",
    # Common
    "common.friend": "friend",
    "common.cancel": "Cancel",
    "common.error": "Something went wrong. Please try again in a moment.",
    "common.language_not_supported": "This language is not supported, pick one of the options.",
    "common.timezone_invalid": "Could not recognise the timezone, pick one of the options.",
    "common.ai_unavailable": "The AI server is unavailable right now. Please try later.",
    "common.ai_bad_answer": "The AI answered in an unexpected way. Please try again.",
    "common.ai_limit": (
        "Today's AI request limit is reached. Your progress is saved — come back tomorrow."
    ),
    # Language names (same in both languages)
    "language.ru": "Русский",
    "language.en": "English",
    # Timezones
    "timezone.utc": "UTC",
    "timezone.moscow": "Moscow",
    "timezone.london": "London",
    "timezone.berlin": "Berlin",
    "timezone.tashkent": "Tashkent",
    "timezone.samarkand": "Samarkand",
    "timezone.new_york": "New York",
    # Commands in the Telegram menu
    "commands.start": "Start the bot",
    "commands.stats": "Streak and record",
    "commands.quiz": "Quiz with questions",
    "commands.free_chat": "Free conversation",
    "commands.close_free_chat": "Close free conversation",
    "commands.daily_vocabulary": "20 words a day",
    "commands.daily_grammar": "Grammar lesson",
    "commands.essay_checker": "Check my essay",
    "commands.level_detector": "Detect my level",
}
