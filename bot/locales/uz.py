"""Bot matnlari o'zbek (lotin) tilida."""

TEXTS: dict[str, str] = {
    # Onboarding
    "start.greeting": "Salom, {name}! Men ingliz tilini o'rganishga yordam beradigan botman.",
    "start.choose_language": "Tushuntirishlar va so'z tarjimalari qaysi tilda bo'lsin?",
    "start.language_saved": "Ajoyib, tushuntirishlar tili: {language}.",
    "start.choose_timezone": "Endi vaqt mintaqangizni tanlang — shunga qarab darslarni eslataman.",
    "start.timezone_saved": "Vaqt mintaqasi saqlandi: {timezone}. O'qishni boshlashingiz mumkin!",
    "start.already_configured": (
        "Qaytib keldingiz, {name}! Tushuntirish tili: {language}, vaqt mintaqasi: {timezone}."
    ),
    "start.commands_hint": "Buyruqlar ro'yxati — kiritish maydoni yonidagi menyuda.",
    # Progress and streak
    "stats.title": "Progressingiz",
    "stats.current": "🔥 Joriy seriya: {days} kun",
    "stats.best": "🏆 Rekord: {days} kun",
    "stats.week": "📅 Haftalik amallar: {count}",
    "stats.hint": "Olovni yoqish uchun bitta vazifa bajaring.",
    # Words of the day
    "vocabulary.loading": (
        "⏳ Bugungi 20 so'zni tanlayapman… Odatda bu bir daqiqagacha vaqt oladi."
    ),
    "vocabulary.title": "📚 Bugungi so'zlar · daraja {level}",
    "vocabulary.reused": "Bugungi to'plam allaqachon saqlangan — mana u.",
    "vocabulary.default_level": (
        "Darajangiz hali aniqlanmagan, shuning uchun {level} daraja so'zlari. "
        "So'zlar darajangizga mos bo'lishi uchun /level_detector dan o'ting."
    ),
    "vocabulary.item": "{index}. {word} {transcription} — {translation}",
    # Quiz
    "quiz.loading": "⏳ Savol tanlayapman…",
    "quiz.question": "{number}-savol\n\n{text}",
    "quiz.correct": "✅ To'g'ri!",
    "quiz.wrong": "❌ Noto'g'ri.",
    "quiz.correct_answer": "To'g'ri javob: {option}) {answer}",
    "quiz.finish_button": "🏁 Yakunlash",
    "quiz.result": "🏁 Kviz yakunlandi\n\nTo'g'ri javoblar: {total} tadan {correct} tasi.",
    "quiz.result_empty": (
        "🏁 Kviz yakunlandi\n\nBirorta savolga javob bermadingiz. Yangidan boshlang: /quiz"
    ),
    "quiz.already_answered": "Bu savolga allaqachon javob berilgan.",
    "quiz.not_active": "Hozir kviz ketmayapti. Yangisini boshlang: /quiz",
    "quiz.invalid_option": "Javob variantini tushunmadim. Yana urinib ko'ring.",
    # Level test
    "level.loading": "⏳ Test tayyorlayapman…",
    "level.intro": "🎯 Daraja testi: 50 ta savol, o'z sur'atingizda javob bering.",
    "level.question": "{total} tadan {number}-savol\n\n{text}",
    "level.retake": (
        "Hozirgi darajangiz {level} (test sanasi {date}).\nTestni qayta topshirasizmi?"
    ),
    "level.start_button": "🎯 Testni topshirish",
    "level.canceled": "Mayli, test bekor qilindi. Qayta ishga tushirish: /level_detector",
    "level.already_running": "Test allaqachon ketmoqda — savolga javob bering.",
    "level.bank_empty": (
        "Test vaqtincha mavjud emas: savollar bazasi yuklanmagan. Keyinroq urinib ko'ring."
    ),
    "level.not_active": "Hozir daraja testi ketmayapti. Uni ishga tushiring: /level_detector",
    "level.already_answered": "Bu savolga javob qabul qilingan.",
    "level.invalid_option": "Javob variantini tushunmadim. Yana urinib ko'ring.",
    "level.answer_saved": "✅ Javob qabul qilindi. {total} tadan {number}-savol",
    "level.resume": "Test davom etmoqda: {total} tadan {number}-savol.",
    "level.result": (
        "🎯 Darajangiz: {level}\n\n"
        "To'g'ri javoblar: {total} tadan {correct} tasi ({accuracy:.0f}%)\n"
        "O'rtacha vaqt: {average:.1f} s\n\n"
        "Grammatika: {grammar:.0f}%\n"
        "Lug'at: {vocabulary:.0f}%"
    ),
    "level.result_balanced": "Grammatika va lug'at bir xil darajada.",
    "level.result_strength": "💪 Kuchli tomon: {topic}.",
    "level.result_weakness": "📌 Ko'proq mashq kerak: {topic}.",
    "level.topic.grammar": "grammatika",
    "level.topic.vocabulary": "lug'at",
    "level.result_done": (
        "Daraja yangilandi. /daily_grammar va /daily_vocabulary bilan davom eting."
    ),
    "level.reset_notice": (
        "⚠️ Daraja testida xatolik topdik: u darajangizni oshirib yuborgan bo'lishi mumkin.\n\n"
        "Adolatli natija bo'lishi uchun darajani qayta tikladik. "
        "Iltimos, testni qayta topshiring: /level_detector"
    ),
    # Grammar lesson
    "grammar.loading": "⏳ Dars tayyorlayapman… Odatda bu bir daqiqagacha vaqt oladi.",
    "grammar.default_level": (
        "Darajangiz hali aniqlanmagan, shuning uchun {level} daraja darsi. "
        "Darslar darajangizga mos bo'lishi uchun /level_detector dan o'ting."
    ),
    "grammar.step_header": "📘 {topic} · {total} tadan {number}-qadam",
    "grammar.exercise_header": (
        "✍️ {topic} · {total} tadan {number}-mashq\nJavobingizni xabar qilib yozing."
    ),
    "grammar.next_button": "▶️ Keyingisi",
    "grammar.continue_button": "▶️ Darsni davom ettirish",
    "grammar.continue_button_short": "▶️ Davom ettirish",
    "grammar.restart_button": "🔄 Boshidan boshlash",
    "grammar.continued": "«{topic}» darsi davom etmoqda.",
    "grammar.resume_prompt": (
        "Sizda tugallanmagan «{topic}» darsi bor. {progress}\n"
        "Davom ettirasizmi yoki boshidan boshlaysizmi?"
    ),
    "grammar.progress_step": "{total} tadan {number}-qadamda to'xtagansiz.",
    "grammar.progress_test": "Faqat yakuniy mini-test qoldi.",
    "grammar.exercise_correct": "✅ To'g'ri!",
    "grammar.exercise_wrong": "❌ Noto'g'ri. To'g'ri javob: {answer}",
    "grammar.question_return": "💬 Darsga qaytamiz.",
    "grammar.test_intro": "🏁 «{topic}» mavzusi bo'yicha mini-test. Tugmalar bilan javob bering.",
    "grammar.test_header": "🏁 Mini-test · {total} tadan {number}-savol",
    "grammar.test_correct": "✅ To'g'ri!",
    "grammar.test_wrong": "❌ Noto'g'ri. To'g'ri javob: {option}) {answer}",
    "grammar.test_result": "🏁 Mini-test: {total} tadan {correct} tasi",
    "grammar.test_mistakes_title": "Xatolarni tahlil qilamiz:",
    "grammar.test_mistake": "{number}. {question}\nTo'g'ri javob: {option}) {answer}",
    "grammar.test_perfect": "Barcha javoblar to'g'ri! Ajoyib ish.",
    "grammar.lesson_done": "«{topic}» darsi yakunlandi. Yangi dars: /daily_grammar",
    "grammar.test_use_buttons": "Savol ostidagi tugma bilan variantni tanlang.",
    "grammar.not_active": "Hozir dars ketmayapti. Yangisini boshlang: /daily_grammar",
    "grammar.already_answered": "Bu savolga allaqachon javob berilgan.",
    "grammar.stale_button": "Bu tugma endi joriy emas.",
    "grammar.invalid_option": "Javob variantini tushunmadim. Yana urinib ko'ring.",
    # Essay check
    "essay.prompt": (
        "📝 Ingliz tilida esse yuboring: {min_words} dan {max_words} so'zgacha.\n"
        "Birinchi qatorga mavzuni yozishingiz mumkin — mavzu qanchalik yoritilganini tekshiraman."
    ),
    "essay.loading": "⏳ Esseni tekshiryapman… Odatda bu bir daqiqagacha vaqt oladi.",
    "essay.too_short": (
        "Esse juda qisqa: {words} so'z. {min_words} dan {max_words} so'zgacha "
        "bo'lishi kerak. Matnni to'ldirib yana yuboring."
    ),
    "essay.too_long": (
        "Esse juda uzun: {words} so'z. {min_words} dan {max_words} so'zgacha "
        "bo'lishi kerak. Matnni qisqartirib yana yuboring."
    ),
    "essay.title": "📝 Baho: {band} / 9",
    "essay.criterion.task_response": "Task Response",
    "essay.criterion.coherence": "Coherence and Cohesion",
    "essay.criterion.lexical_resource": "Lexical Resource",
    "essay.criterion.grammar": "Grammatical Range and Accuracy",
    "essay.weak_title": "⚠️ Zaif tomonlar:",
    "essay.weak_item": "{index}. «{quote}»: {problem} → «{fix}»",
    "essay.no_weak": "✅ Zaif tomonlar topilmadi.",
    "essay.strengths": "✅ Kuchli tomonlar: {summary}",
    "essay.main_advice": ("🎯 Avval nimani yaxshilash kerak: {criterion} ({score} / 9) — {hint}"),
    "essay.hint.task_response": (
        "mavzu yoritilganiga va pozitsiyangiz dalillar bilan "
        "mustahkamlanganiga ishonch hosil qiling"
    ),
    "essay.hint.coherence": (
        "abzatslarning mantig'iga va fikrlar orasidagi bog'lovchilarga e'tibor bering"
    ),
    "essay.hint.lexical_resource": "lug'atingizni kengaytiring va takrorlardan qoching",
    "essay.hint.grammar": "kelishuv, zamonlar va so'z tartibini tekshiring",
    "essay.disclaimer": ("⚠️ Baho taxminiy va rasmiy IELTS imtihonini almashtirmaydi."),
    # Free conversation
    "chat.started": (
        "💬 Erkin suhbat ochildi. Istalgan tilda yozing — o'z tilingizda javob beraman, "
        "ingliz tilidagi xatolaringizni yumshoq tuzataman.\n\nSuhbatni yopish: /close_free_chat"
    ),
    "chat.closed": "👋 Erkin suhbat yopildi, tarix tozalandi. Qayta boshlash: /free_chat",
    "chat.not_active": "Hozir erkin suhbat ochiq emas. Boshlash: /free_chat",
    # Streak and reminders
    "streak.line": "🔥 Seriya: {days} kun",
    "reminder.morning.1": (
        "☀️ Xayrli tong! Bugun ingliz tilini o'rgandingizmi? Besh daqiqa — va olov yonib turadi."
    ),
    "reminder.morning.2": (
        "☀️ Tong ingliz tilidan boshlanadimi? Bitta qisqa vazifa — va kun hisobga olindi."
    ),
    "reminder.morning.3": (
        "☀️ Salom! Kun hali hisobga olinmadi: qisqa vazifa bajaring va olovni saqlang."
    ),
    "reminder.evening.1": (
        "🔥 {days} kun ketma-ket! Olovni yo'qotmang — yarim tungacha bitta vazifa."
    ),
    "reminder.evening.2": (
        "🔥 Seriya {days} kun. Uni uzaytirishga hali vaqt bor — 5 so'zdan boshlang."
    ),
    "reminder.evening.3": ("🔥 {days} kun ketma-ket — ajoyib natija. Bugun uni mustahkamlang."),
    "reminder.evening_cold.1": (
        "🌙 Kun deyarli tugadi, lekin olov hali yo'q. 5 so'zdan boshlaymizmi?"
    ),
    "reminder.evening_cold.2": (
        "🌙 Oqshom — ingliz tili uchun yaxshi vaqt. Bitta vazifa — va olov yonadi."
    ),
    "reminder.missed.1": (
        "👋 Qayerdasiz? {days} kunlik olov o'chdi, lekin uni 2 daqiqada qayta yoqish mumkin. "
        "5 so'zdan boshlaymizmi?"
    ),
    "reminder.missed.2": (
        "👋 Qayerdasiz? {days} kunlik seriya uzildi, xavotir olmang. "
        "Besh so'z — va olov yana yonadi."
    ),
    "reminder.missed.3": (
        "👋 Kecha yo'q edingiz, {days} kunlik olov o'chdi. Qaytamizmi? 5 so'zdan boshlaymiz."
    ),
    "reminder.missed_long.1": (
        "🕯️ {days} kundan beri ingliz tili yo'q — olov allaqachon o'chgan. 5 so'z bilan qaytamizmi?"
    ),
    "reminder.missed_long.2": (
        "🕯️ {days} kun jimlik. Yangidan boshlaymiz — 5 so'z olovni yoqishga yetadi."
    ),
    "reminder.button": "🔥 5 so'z",
    "reminder.quick_title": "🔥 Tez boshlash: {count} so'z",
    # Common
    "common.friend": "do'st",
    "common.cancel": "Bekor qilish",
    "common.error": "Nimadir xato ketdi. Birozdan keyin urinib ko'ring.",
    "common.language_not_supported": "Bu til qo'llab-quvvatlanmaydi, variantlardan birini tanlang.",
    "common.timezone_invalid": "Vaqt mintaqasini tanib bo'lmadi, variantlardan birini tanlang.",
    "common.ai_unavailable": "AI-server hozir mavjud emas. Birozdan keyin urinib ko'ring.",
    "common.ai_bad_answer": "AI kutilmagandek javob berdi. Yana urinib ko'ring.",
    "common.ai_limit": (
        "Bugungi AI so'rovlar limiti tugadi. Jarayon saqlandi — ertaga qaytib keling."
    ),
    # Language names
    "language.ru": "Русский",
    "language.en": "English",
    "language.uz": "O'zbekcha",
    # Timezones
    "timezone.utc": "UTC",
    "timezone.moscow": "Moskva",
    "timezone.london": "London",
    "timezone.berlin": "Berlin",
    "timezone.tashkent": "Toshkent",
    "timezone.samarkand": "Samarqand",
    "timezone.new_york": "Nyu-York",
    # Commands in the Telegram menu
    "commands.start": "Botni ishga tushirish",
    "commands.stats": "Seriya va rekord",
    "commands.quiz": "Savolli kviz",
    "commands.free_chat": "Erkin suhbat",
    "commands.close_free_chat": "Erkin suhbatni yopish",
    "commands.daily_vocabulary": "Kuniga 20 so'z",
    "commands.daily_grammar": "Grammatika darsi",
    "commands.essay_checker": "Esseni tekshirish",
    "commands.level_detector": "Darajani aniqlash",
}
