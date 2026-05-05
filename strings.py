"""
strings.py — Localised UI strings for EN and RU.

Usage:
    from strings import s
    text = s("en", "weekly_header", period="01–07 May")
"""

STRINGS: dict[str, dict] = {
    "en": {
        # ── Weekly overview ───────────────────────────────────────────────
        "weekly_header":            "📊 *WEEKLY REPORT ({period})*",
        "posts_count":              "📌 Posts: *{count}* (originals only, no replies)",
        "impressions":              "👁 Impressions: *{val:,}*",
        "engagement":               "💬 Engagement: *{val:,}* interactions",
        "avg_er":                   "📈 Avg ER: *{val:.1f}%*",
        "likes_rt_replies":         "❤️ Likes: *{likes:,}* · 🔁 Retweets: *{rt:,}* · 💬 Replies: *{rp:,}*",

        # ── Week-over-week ─────────────────────────────────────────────────
        "comparison_header":        "📊 *WEEK-OVER-WEEK*",
        "cmp_impressions":          "Impressions: {prev:,} → *{cur:,}* ({delta})",
        "cmp_engagement":           "Engagement: {prev:,} → *{cur:,}* ({delta})",
        "cmp_er":                   "ER: {prev:.1f}% → *{cur:.1f}%* ({delta})",
        "cmp_likes":                "Likes: {prev:,} → *{cur:,}* ({delta})",
        "cmp_retweets":             "Retweets: {prev:,} → *{cur:,}*",
        "no_comparison":            "📊 _Comparison will be available next week._",

        # ── Top / bottom posts ─────────────────────────────────────────────
        "top_header":               "🏆 *TOP 3 POSTS BY ENGAGEMENT*",
        "interactions_n":           "{n} interactions",
        "interactions_detail":      "({likes} likes, {replies} replies, {rt} retweets)",
        "views_n":                  "{n:,} views · ER: {er:.1f}%",
        "why_worked":               "✅ _Why it worked:_ {why}",
        "bottom_header":            "📉 *WHAT FLOPPED*",
        "interactions_short":       "👎 {n} interactions · {imp:,} views · ER: {er:.1f}%",
        "why_flopped":              "❌ _Why it flopped:_ {why}",
        "er_analysis_header":       "📈 *ER BREAKDOWN*",
        "er_best":                  "🎯 Best: {er:.1f}% — «{preview}»",
        "er_worst":                 "🎯 Worst: {er:.1f}% — «{preview}»",

        # ── Timing ────────────────────────────────────────────────────────
        "timing_header":            "⏰ *BEST TIME TO POST*",
        "top_hours_label":          "🔥 Top 3 hours:",
        "hour_line":                "• {h:02d}:00 UTC — avg ER {er:.1f}%",
        "best_days_line":           "✅ Best days: {days}",
        "avoid_day_line":           "⚠️ Avoid: {day} (ER {er:.1f}%)",
        "day_names":                ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],

        # ── Recommendations ───────────────────────────────────────────────
        "recs_header":              "💡 *RECOMMENDATIONS*",

        # ── Hall of Fame ──────────────────────────────────────────────────
        "hof_header":               "🏆 *HALL OF FAME — NEW RECORD!*",
        "hof_one":                  "🎉 One tweet this week made the all-time top 10!",
        "hof_many":                 "🎉 {n} tweets this week made the all-time top 10!",
        "hof_separator":            "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️",
        "hof_top3_header":          "👑 *ALL-TIME TOP 3*",

        # ── Monthly ───────────────────────────────────────────────────────
        "monthly_header":           "📅 *MONTHLY REPORT — {month}*",
        "monthly_totals_header":    "📊 *MONTH OVERVIEW*",
        "monthly_posts":            "📌 Posts: *{n}*",
        "monthly_impressions":      "👁 Impressions: *{n:,}*",
        "monthly_avg_er":           "📈 Avg ER: *{n:.1f}%*",
        "monthly_trend":            "Trend: {trend}",
        "monthly_weeks_header":     "📆 *WEEK BY WEEK*",
        "monthly_week_line":        "{i}. _{label}_: {posts} posts · 👁 {imp:,} · ER {er:.1f}%",
        "monthly_best_week":        "🏆 *Best week:* _{label}_ (ER {er:.1f}%)",
        "monthly_worst_week":       "📉 *Weakest week:* _{label}_ (ER {er:.1f}%)",
        "monthly_top_tweet_header": "⭐ *TOP TWEET OF THE MONTH*",
        "ai_analysis_header":       "💡 *AI ANALYSIS*",
        "monthly_no_data": (
            "📅 *Monthly Report*\n\n"
            "Not enough data yet — the archive is empty.\n"
            "Data will accumulate after a few weekly runs."
        ),

        # ── Trends ────────────────────────────────────────────────────────
        "trend_up":                 "📈 Growing",
        "trend_down":               "📉 Declining",
        "trend_flat":               "➡️ Stable",
        "trend_no_data":            "➡️ Not enough data",

        # ── Month names (for monthly label) ───────────────────────────────
        "months": {
            "January": "January", "February": "February", "March": "March",
            "April": "April",     "May": "May",            "June": "June",
            "July": "July",       "August": "August",      "September": "September",
            "October": "October", "November": "November",  "December": "December",
        },

        # ── Language setup ────────────────────────────────────────────────
        "lang_prompt":              "🌍 *Choose your report language:*",
        "lang_saved":               "✅ Language set to *English*. Reports will be in English from now on.",

        # ── Error / cookie notifications ──────────────────────────────────
        "cookies_expired_hint": (
            "If it says COOKIES\\_EXPIRED — re-export cookies via Cookie\\-Editor "
            "and update the TWITTER\\_COOKIES secret in GitHub."
        ),
    },

    "ru": {
        # ── Обзор недели ──────────────────────────────────────────────────
        "weekly_header":            "📊 *ОТЧЁТ ЗА НЕДЕЛЮ ({period})*",
        "posts_count":              "📌 Постов: *{count}* (только оригинальные, без реплаев)",
        "impressions":              "👁 Просмотры: *{val:,}*",
        "engagement":               "💬 Engagement: *{val:,}* взаимодействий",
        "avg_er":                   "📈 Средний ER: *{val:.1f}%*",
        "likes_rt_replies":         "❤️ Лайки: *{likes:,}* · 🔁 Ретвиты: *{rt:,}* · 💬 Ответы: *{rp:,}*",

        # ── Сравнение ─────────────────────────────────────────────────────
        "comparison_header":        "📊 *СРАВНЕНИЕ С ПРОШЛОЙ НЕДЕЛЕЙ*",
        "cmp_impressions":          "Просмотры: {prev:,} → *{cur:,}* ({delta})",
        "cmp_engagement":           "Engagement: {prev:,} → *{cur:,}* ({delta})",
        "cmp_er":                   "ER: {prev:.1f}% → *{cur:.1f}%* ({delta})",
        "cmp_likes":                "Лайки: {prev:,} → *{cur:,}* ({delta})",
        "cmp_retweets":             "Ретвиты: {prev:,} → *{cur:,}*",
        "no_comparison":            "📊 _Сравнение будет доступно на следующей неделе._",

        # ── Топ / худшие ──────────────────────────────────────────────────
        "top_header":               "🏆 *ТОП-3 ПОСТА ПО ENGAGEMENT*",
        "interactions_n":           "{n} взаимодействий",
        "interactions_detail":      "({likes} лайков, {replies} реплаев, {rt} ретвитов)",
        "views_n":                  "{n:,} просмотров · ER: {er:.1f}%",
        "why_worked":               "✅ _Почему зашёл:_ {why}",
        "bottom_header":            "📉 *НЕ ЗАШЛО (ХУДШИЕ ПОСТЫ)*",
        "interactions_short":       "👎 {n} взаимодействий · {imp:,} просмотров · ER: {er:.1f}%",
        "why_flopped":              "❌ _Почему не зашёл:_ {why}",
        "er_analysis_header":       "📈 *ER АНАЛИЗ*",
        "er_best":                  "🎯 Лучший: {er:.1f}% — «{preview}»",
        "er_worst":                 "🎯 Худший: {er:.1f}% — «{preview}»",

        # ── Время ─────────────────────────────────────────────────────────
        "timing_header":            "⏰ *ЛУЧШЕЕ ВРЕМЯ ПУБЛИКАЦИИ*",
        "top_hours_label":          "🔥 Топ-3 часа:",
        "hour_line":                "• {h:02d}:00 UTC — средний ER {er:.1f}%",
        "best_days_line":           "✅ Лучшие дни: {days}",
        "avoid_day_line":           "⚠️ Избегай: {day} (ER {er:.1f}%)",
        "day_names":                ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],

        # ── Рекомендации ──────────────────────────────────────────────────
        "recs_header":              "💡 *РЕКОМЕНДАЦИИ*",

        # ── Зал Славы ─────────────────────────────────────────────────────
        "hof_header":               "🏆 *ЗАЛ СЛАВЫ — НОВЫЕ РЕКОРДСМЕНЫ!*",
        "hof_one":                  "🎉 Один твит на этой неделе вошёл в топ-10 всех времён!",
        "hof_many":                 "🎉 {n} твита этой недели вошли в топ-10 всех времён!",
        "hof_separator":            "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️",
        "hof_top3_header":          "👑 *ТОП-3 ВСЕХ ВРЕМЁН*",

        # ── Ежемесячный ───────────────────────────────────────────────────
        "monthly_header":           "📅 *ЕЖЕМЕСЯЧНЫЙ ОТЧЁТ — {month}*",
        "monthly_totals_header":    "📊 *ИТОГИ МЕСЯЦА*",
        "monthly_posts":            "📌 Постов: *{n}*",
        "monthly_impressions":      "👁 Просмотры: *{n:,}*",
        "monthly_avg_er":           "📈 Средний ER: *{n:.1f}%*",
        "monthly_trend":            "Тренд: {trend}",
        "monthly_weeks_header":     "📆 *НЕДЕЛЯ ЗА НЕДЕЛЕЙ*",
        "monthly_week_line":        "{i}. _{label}_: {posts} постов · 👁 {imp:,} · ER {er:.1f}%",
        "monthly_best_week":        "🏆 *Лучшая неделя:* _{label}_ (ER {er:.1f}%)",
        "monthly_worst_week":       "📉 *Слабейшая неделя:* _{label}_ (ER {er:.1f}%)",
        "monthly_top_tweet_header": "⭐ *ТОП-ТВИТ МЕСЯЦА*",
        "ai_analysis_header":       "💡 *AI-АНАЛИЗ*",
        "monthly_no_data": (
            "📅 *Ежемесячный отчёт*\n\n"
            "Недостаточно данных — архив пуст.\n"
            "Данные накопятся после нескольких еженедельных запусков."
        ),

        # ── Тренды ────────────────────────────────────────────────────────
        "trend_up":                 "📈 Рост",
        "trend_down":               "📉 Спад",
        "trend_flat":               "➡️ Стабильно",
        "trend_no_data":            "➡️ Недостаточно данных",

        # ── Названия месяцев ──────────────────────────────────────────────
        "months": {
            "January": "Январь",   "February": "Февраль", "March": "Март",
            "April": "Апрель",     "May": "Май",           "June": "Июнь",
            "July": "Июль",        "August": "Август",     "September": "Сентябрь",
            "October": "Октябрь",  "November": "Ноябрь",   "December": "Декабрь",
        },

        # ── Выбор языка ───────────────────────────────────────────────────
        "lang_prompt":              "🌍 *Выберите язык отчётов:*",
        "lang_saved":               "✅ Язык установлен: *Русский*. Все отчёты будут на русском.",

        # ── Ошибки / уведомления ──────────────────────────────────────────
        "cookies_expired_hint": (
            "Если написано COOKIES\\_EXPIRED — экспортируй cookies через Cookie\\-Editor "
            "и обнови секрет TWITTER\\_COOKIES в GitHub."
        ),
    },
}


def s(lang: str, key: str, **kwargs) -> str:
    """Return localised string, falling back to English."""
    lang = lang if lang in STRINGS else "en"
    bucket = STRINGS[lang]
    template = bucket.get(key) or STRINGS["en"].get(key, key)
    return template.format(**kwargs) if kwargs else template
