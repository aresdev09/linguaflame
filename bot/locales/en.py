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
    # Common
    "common.friend": "friend",
    "common.error": "Something went wrong. Please try again in a moment.",
    "common.language_not_supported": "This language is not supported, pick one of the options.",
    "common.timezone_invalid": "Could not recognise the timezone, pick one of the options.",
    "common.ai_unavailable": "The AI server is unavailable right now. Please try later.",
    "common.ai_bad_answer": "The AI answered in an unexpected way. Please try again.",
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