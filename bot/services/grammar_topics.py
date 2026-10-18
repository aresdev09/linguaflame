"""Темы уроков грамматики по уровням.

Список нужен, чтобы темы не повторялись, пока пользователь не пройдёт
весь набор своего уровня.
"""

from typing import Final

from bot.config import LEVELS

GRAMMAR_TOPICS: Final[dict[str, tuple[str, ...]]] = {
    "A1": (
        "To be: am, is, are",
        "Personal pronouns",
        "Articles a / an",
        "Plural nouns",
        "Present Simple",
        "Have got",
        "There is / There are",
        "Can for ability",
        "Prepositions of place",
        "Present Continuous",
        "Possessive 's",
        "Some and any",
        "This, that, these, those",
        "Imperatives",
        "Question words",
    ),
    "A2": (
        "Past Simple",
        "Past Continuous",
        "Comparatives",
        "Superlatives",
        "Be going to",
        "Will for the future",
        "Present Perfect",
        "Must and have to",
        "Countable and uncountable nouns",
        "Much and many",
        "Adverbs of frequency",
        "First Conditional",
        "Prepositions of time",
        "Present Perfect vs Past Simple",
        "Like + ing",
    ),
    "B1": (
        "Present Perfect vs Past Simple",
        "Second Conditional",
        "Passive Voice",
        "Relative Clauses",
        "Reported Speech",
        "Modals of Deduction",
        "Gerund and Infinitive",
        "Used to",
        "Past Perfect",
        "Question Tags",
        "Quantifiers",
        "Future Forms",
        "Definite and Indefinite Articles",
        "Linking Words",
        "Indirect Questions",
    ),
    "B2": (
        "Third Conditional",
        "Mixed Conditionals",
        "Passive Voice (Advanced)",
        "Reported Speech (Advanced)",
        "Modal Perfects",
        "Non-defining Relative Clauses",
        "Future Continuous",
        "Future Perfect",
        "Participle Clauses",
        "Causative Have",
        "Wish and If only",
        "Gerund and Infinitive Patterns",
        "Articles (Advanced)",
        "Linking Words (Advanced)",
        "Question Forms in Formal English",
    ),
    "C1": (
        "Inversion",
        "Cleft Sentences",
        "Subjunctive",
        "Modal Perfects (Nuances)",
        "Mixed Conditionals (Advanced)",
        "Advanced Passive Structures",
        "Participle Clauses (Advanced)",
        "Nominalization",
        "Ellipsis",
        "Hedging Language",
        "Complex Relative Clauses",
        "Discourse Markers",
        "Emphatic Structures",
        "Formal vs Informal Style",
        "Cohesion in Writing",
    ),
    "C2": (
        "Advanced Inversion",
        "Subjunctive and Unreal Past",
        "Absolute Constructions",
        "Complex Ellipsis",
        "Stylistic Inversion",
        "Conditionals in Discourse",
        "Modal Nuance",
        "Nominalization and Style",
        "Advanced Coordination",
        "Academic Hedging",
        "Idiomatic Grammar",
        "Literary Structures",
        "Emphasis and Focus",
        "Register Shift",
        "Grammar of Cohesion",
    ),
}

# Уровень по умолчанию, если пользователь ещё не проходил /level_detector.
DEFAULT_LEVEL: Final[str] = "A2"

# Проверка, что список покрывает все уровни из конфига.
assert set(GRAMMAR_TOPICS) == set(LEVELS), "Для каждого уровня нужен список тем"
