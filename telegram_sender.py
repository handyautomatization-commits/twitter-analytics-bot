"""
telegram_sender.py — Отправка еженедельного отчёта в Telegram-канал.

Telegram ограничивает сообщения 4096 символами.
Отчёт автоматически разбивается на части.
"""

import os
import asyncio
from typing import Optional

from analyzer import WeeklyReport, compute_delta

# Эмодзи-цифры для нумерации
EMOJI_NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
HOF_MEDALS = ["🥇", "🥈", "🥉"]


# ─── Форматирование отчёта ──────────────────────────────────────────────────

def format_report(report: WeeklyReport) -> list[str]:
    """
    Форматирует WeeklyReport в список Telegram-сообщений.
    Каждое сообщение ≤ 4096 символов (лимит Telegram).
    """
    parts: list[str] = []
    parts.append(_part_overview(report))
    parts.append(_part_top_bottom(report))
    parts.append(_part_timing_and_recs(report))
    return [p for p in parts if p.strip()]


def format_hall_of_fame_message(
    new_entries: list,
    hall_of_fame: list[dict],
) -> str:
    """Поздравительное сообщение о новых записях в Зале Славы."""
    lines = ["🏆 *ЗАЛ СЛАВЫ — НОВЫЕ РЕКОРДСМЕНЫ!*", ""]

    if len(new_entries) == 1:
        lines.append("🎉 Один твит на этой неделе вошёл в топ\\-10 всех времён!")
    else:
        lines.append(f"🎉 {len(new_entries)} твита этой недели вошли в топ\\-10 всех времён!")
    lines.append("")

    for tweet in new_entries:
        preview = _tweet_preview(tweet.text, max_len=60)
        date_str = tweet.posted_at.strftime("%d %b %Y")
        lines.append(f"✨ *«{_escape_md(preview)}»*")
        lines.append(f"_{date_str}_ · ER: *{tweet.engagement_rate:.1f}%* · 👁 {tweet.impressions:,} · ❤️ {tweet.likes}")
        lines.append(f"🔗 https://x.com/i/web/status/{tweet.tweet_id}")
        lines.append("")

    lines.append("〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️")
    lines.append("")
    lines.append("👑 *ТОП\\-3 ВСЕХ ВРЕМЁН*")
    lines.append("")

    for i, entry in enumerate(hall_of_fame[:3]):
        medal = HOF_MEDALS[i] if i < len(HOF_MEDALS) else f"{i + 1}."
        preview = _tweet_preview(entry["text"], max_len=50)
        wl = entry.get("week_label", "")
        lines.append(f"{medal} *«{_escape_md(preview)}»*")
        lines.append(
            f"_{wl}_ · ER: *{entry['engagement_rate']:.1f}%*"
            f" · 👁 {entry.get('impressions', 0):,} · ❤️ {entry.get('likes', 0)}"
        )
        lines.append(f"🔗 https://x.com/i/web/status/{entry['tweet_id']}")
        lines.append("")

    return "\n".join(lines)


def format_monthly_report(report) -> list[str]:
    """
    Форматирует MonthlyReport в список Telegram-сообщений.
    """
    lines = [
        f"📅 *ЕЖЕМЕСЯЧНЫЙ ОТЧЁТ — {_escape_md(report.month_label.upper())}*",
        f"_{report.period_label}_",
        "",
        "📊 *ИТОГИ МЕСЯЦА*",
        f"📌 Постов: *{report.total_tweets}*",
        f"👁 Просмотры: *{report.total_impressions:,}*",
        f"📈 Средний ER: *{report.avg_er:.1f}%*",
        f"Тренд: {report.trend}",
        "",
        "📆 *НЕДЕЛЯ ЗА НЕДЕЛЕЙ*",
    ]

    for i, week in enumerate(report.weeks, 1):
        stats = week["stats"]
        er = stats.get("avg_engagement_rate", 0.0)
        imp = stats.get("total_impressions", 0)
        n = stats.get("tweet_count", 0)
        label = week.get("period_label", f"Неделя {i}")
        lines.append(f"{i}. _{_escape_md(label)}_: {n} постов · 👁 {imp:,} · ER {er:.1f}%")

    best_er = report.best_week["stats"].get("avg_engagement_rate", 0.0)
    worst_er = report.worst_week["stats"].get("avg_engagement_rate", 0.0)
    lines += [
        "",
        f"🏆 *Лучшая неделя:* _{_escape_md(report.best_week.get('period_label', ''))}_  (ER {best_er:.1f}%)",
        f"📉 *Слабейшая неделя:* _{_escape_md(report.worst_week.get('period_label', ''))}_  (ER {worst_er:.1f}%)",
    ]

    if report.top_tweet:
        t = report.top_tweet
        preview = _tweet_preview(t.get("text", ""), max_len=50)
        lines += [
            "",
            "⭐ *ТОП-ТВИТ МЕСЯЦА*",
            f"*«{_escape_md(preview)}»*",
            f"ER: *{t.get('engagement_rate', 0):.1f}%* · 👁 {t.get('impressions', 0):,} · ❤️ {t.get('likes', 0)}",
            f"🔗 https://x.com/i/web/status/{t.get('tweet_id', '')}",
        ]

    if report.ai_summary:
        lines += [
            "",
            "💡 *AI-АНАЛИЗ*",
            _escape_md(report.ai_summary),
        ]

    return ["\n".join(lines)]


def _part_overview(report: WeeklyReport) -> str:
    cur = report.current
    prev = report.previous

    total_eng = cur.total_likes + cur.total_retweets + cur.total_replies
    lines = [
        f"📊 *ОТЧЁТ ЗА НЕДЕЛЮ ({report.period_label})*",
        "",
        f"📌 Постов: *{cur.tweet_count}* (только оригинальные, без реплаев)",
        f"👁 Просмотры: *{cur.total_impressions:,}*",
        f"💬 Engagement: *{total_eng:,}* взаимодействий",
        f"📈 Средний ER: *{cur.avg_engagement_rate:.1f}%*",
        f"❤️ Лайки: *{cur.total_likes:,}* · 🔁 Ретвиты: *{cur.total_retweets:,}* · 💬 Ответы: *{cur.total_replies:,}*",
    ]

    if prev:
        prev_eng = prev.total_likes + prev.total_retweets + prev.total_replies
        lines += [
            "",
            "📊 *СРАВНЕНИЕ С ПРОШЛОЙ НЕДЕЛЕЙ*",
            f"Просмотры: {prev.total_impressions:,} → *{cur.total_impressions:,}* ({compute_delta(cur.total_impressions, prev.total_impressions)})",
            f"Engagement: {prev_eng:,} → *{total_eng:,}* ({compute_delta(total_eng, prev_eng)})",
            f"ER: {prev.avg_engagement_rate:.1f}% → *{cur.avg_engagement_rate:.1f}%* ({compute_delta(cur.avg_engagement_rate, prev.avg_engagement_rate)})",
            f"Лайки: {prev.total_likes:,} → *{cur.total_likes:,}* ({compute_delta(cur.total_likes, prev.total_likes)})",
            f"Ретвиты: {prev.total_retweets:,} → *{cur.total_retweets:,}*",
        ]
    else:
        lines += ["", "📊 _Сравнение будет доступно на следующей неделе._"]

    return "\n".join(lines)


def _part_top_bottom(report: WeeklyReport) -> str:
    lines = []

    # ── Топ-3 ─────────────────────────────────────────────────────────────
    if report.top_tweets:
        lines.append("🏆 *ТОП-3 ПОСТА ПО ENGAGEMENT*")
        for i, tweet in enumerate(report.top_tweets):
            emoji = EMOJI_NUMS[i] if i < len(EMOJI_NUMS) else f"{i+1}."
            preview = _tweet_preview(tweet.text)
            date_str = tweet.posted_at.strftime("%d %b, %H:%M UTC")
            eng = tweet.likes + tweet.retweets + tweet.replies

            lines.append(f"\n{emoji} *«{_escape_md(preview)}»*")
            lines.append(f"_{date_str}_")
            lines.append(
                f"💪 {eng} взаимодействий "
                f"({tweet.likes} лайков, {tweet.replies} реплаев, {tweet.retweets} ретвитов)"
            )
            lines.append(f"👁 {tweet.impressions:,} просмотров · ER: {tweet.engagement_rate:.1f}%")
            lines.append(f"🔗 https://x.com/i/web/status/{tweet.tweet_id}")

            why = report.ai_top_why[i] if i < len(report.ai_top_why) else ""
            if why:
                lines.append(f"✅ _Почему зашёл:_ {why}")

    # ── Разделитель ───────────────────────────────────────────────────────
    lines.append("")
    lines.append("〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️")
    lines.append("")

    # ── Худшие ────────────────────────────────────────────────────────────
    if report.bottom_tweets:
        lines.append("📉 *НЕ ЗАШЛО (ХУДШИЕ ПОСТЫ)*")
        for i, tweet in enumerate(report.bottom_tweets):
            emoji = EMOJI_NUMS[i] if i < len(EMOJI_NUMS) else f"{i+1}."
            preview = _tweet_preview(tweet.text)
            date_str = tweet.posted_at.strftime("%d %b, %H:%M UTC")
            eng = tweet.likes + tweet.retweets + tweet.replies

            lines.append(f"\n{emoji} *«{_escape_md(preview)}»*")
            lines.append(f"_{date_str}_")
            lines.append(
                f"👎 {eng} взаимодействий · "
                f"{tweet.impressions:,} просмотров · ER: {tweet.engagement_rate:.1f}%"
            )
            lines.append(f"🔗 https://x.com/i/web/status/{tweet.tweet_id}")

            why = report.ai_bottom_why[i] if i < len(report.ai_bottom_why) else ""
            if why:
                lines.append(f"❌ _Почему не зашёл:_ {why}")

    # ── ER сводка ─────────────────────────────────────────────────────────
    if report.top_tweets and report.bottom_tweets:
        best = report.top_tweets[0]
        worst = report.bottom_tweets[0]
        lines += [
            "",
            "📈 *ER АНАЛИЗ*",
            f"🎯 Лучший: {best.engagement_rate:.1f}% — «{_tweet_preview(best.text)}»",
            f"🎯 Худший: {worst.engagement_rate:.1f}% — «{_tweet_preview(worst.text)}»",
        ]

    return "\n".join(lines)


def _part_timing_and_recs(report: WeeklyReport) -> str:
    lines = []

    # ── Лучшее время ──────────────────────────────────────────────────────
    if report.best_hours:
        lines.append("⏰ *ЛУЧШЕЕ ВРЕМЯ ПУБЛИКАЦИИ*")
        lines.append("🔥 Топ-3 часа:")
        for hour, avg_er in report.best_hours:
            lines.append(f"• {hour:02d}:00 UTC — средний ER {avg_er:.1f}%")

    if report.best_days:
        top_days = report.best_days[:3]
        lines.append(
            "✅ Лучшие дни: " +
            ", ".join(f"{d} ({er:.1f}%)" for d, er in top_days)
        )
        if len(report.best_days) > 0:
            worst_day = report.best_days[-1]
            lines.append(f"⚠️ Избегай: {worst_day[0]} (ER {worst_day[1]:.1f}%)")

    # ── Рекомендации ──────────────────────────────────────────────────────
    if report.ai_recommendations:
        lines += ["", "💡 *РЕКОМЕНДАЦИИ*"]
        # Добавляем пустую строку перед каждым пунктом (1️⃣, 2️⃣ и т.д.)
        recs_formatted = report.ai_recommendations
        for emoji in ["2️⃣", "3️⃣", "4️⃣", "5️⃣"]:
            recs_formatted = recs_formatted.replace(emoji, f"\n{emoji}")
        lines.append(recs_formatted)

    return "\n".join(lines)


def _tweet_preview(text: str, max_len: int = 40) -> str:
    """Короткий превью текста твита."""
    text = text.strip()
    if len(text) <= max_len:
        return text
    # Обрезаем по слову
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > max_len // 2:
        truncated = truncated[:last_space]
    return truncated + "…"


def _escape_md(text: str) -> str:
    """Экранирует спецсимволы Telegram Markdown (V1)."""
    return text.replace("*", "\\*").replace("_", "\\_").replace("`", "\\`").replace("[", "\\[")


# ─── Отправка в Telegram ────────────────────────────────────────────────────

async def send_report_async(
    bot_token: str,
    channel_id: str,
    messages: list[str],
):
    """Отправляет список сообщений в Telegram-канал."""
    try:
        from telegram import Bot  # type: ignore
        from telegram.constants import ParseMode

        bot = Bot(token=bot_token)

        for text in messages:
            if not text.strip():
                continue
            for chunk in _split_message(text, max_len=4096):
                await bot.send_message(
                    chat_id=channel_id,
                    text=chunk,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )
                await asyncio.sleep(0.5)

        print(f"[Telegram] Отправлено {len(messages)} сообщений в {channel_id}")

    except ImportError:
        print("[Telegram] python-telegram-bot не установлен. Используем urllib.")
        await _send_via_requests(bot_token, channel_id, messages)
    except Exception as e:
        print(f"[Telegram] Ошибка отправки: {e}")
        raise


async def _send_via_requests(
    bot_token: str,
    channel_id: str,
    messages: list[str],
):
    """Fallback: отправка через urllib без python-telegram-bot."""
    import urllib.request
    import urllib.parse

    base_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    for text in messages:
        if not text.strip():
            continue
        for chunk in _split_message(text, 4096):
            data = urllib.parse.urlencode({
                "chat_id": channel_id,
                "text": chunk,
                "parse_mode": "Markdown",
                "disable_web_page_preview": "true",
            }).encode()
            req = urllib.request.Request(base_url, data=data, method="POST")
            with urllib.request.urlopen(req) as resp:
                result = resp.read().decode()
                if '"ok":false' in result:
                    print(f"[Telegram] Ошибка API: {result[:200]}")
            await asyncio.sleep(0.5)


async def send_error_notification(
    bot_token: str,
    channel_id: str,
    error_message: str,
):
    """Отправляет уведомление об ошибке."""
    text = (
        "⚠️ *Twitter Analytics — Ошибка*\n\n"
        f"{error_message}\n\n"
        "Если написано COOKIES\\_EXPIRED — экспортируй cookies через Cookie\\-Editor "
        "и обнови секрет TWITTER\\_COOKIES в GitHub."
    )
    await _send_via_requests(bot_token, channel_id, [text])


def _split_message(text: str, max_len: int = 4096) -> list[str]:
    """Разбивает длинное сообщение на части по max_len символов."""
    if len(text) <= max_len:
        return [text]

    parts = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        parts.append(text[:split_at])
        text = text[split_at:].lstrip("\n")

    return parts


def send_report(bot_token: str, channel_id: str, messages: list[str]):
    """Синхронная обёртка для send_report_async."""
    asyncio.run(send_report_async(bot_token, channel_id, messages))
