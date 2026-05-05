"""
telegram_sender.py — Formats and sends weekly/monthly reports to Telegram.

Supports EN and RU via the strings module.
Telegram message limit: 4096 chars — long reports are split automatically.
"""

import asyncio
import os
from typing import Optional

from analyzer import WeeklyReport, MonthlyReport, compute_delta
from strings import s, STRINGS

EMOJI_NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
HOF_MEDALS = ["🥇", "🥈", "🥉"]


# ─── Weekly report ──────────────────────────────────────────────────────────

def format_report(report: WeeklyReport, lang: str = "en") -> list[str]:
    parts = [
        _part_overview(report, lang),
        _part_top_bottom(report, lang),
        _part_timing_and_recs(report, lang),
    ]
    return [p for p in parts if p.strip()]


def _part_overview(report: WeeklyReport, lang: str) -> str:
    cur = report.current
    prev = report.previous
    total_eng = cur.total_likes + cur.total_retweets + cur.total_replies

    lines = [
        s(lang, "weekly_header", period=report.period_label),
        "",
        s(lang, "posts_count", count=cur.tweet_count),
        s(lang, "impressions", val=cur.total_impressions),
        s(lang, "engagement", val=total_eng),
        s(lang, "avg_er", val=cur.avg_engagement_rate),
        s(lang, "likes_rt_replies",
          likes=cur.total_likes, rt=cur.total_retweets, rp=cur.total_replies),
    ]

    if prev:
        prev_eng = prev.total_likes + prev.total_retweets + prev.total_replies
        lines += [
            "",
            s(lang, "comparison_header"),
            s(lang, "cmp_impressions",
              prev=prev.total_impressions, cur=cur.total_impressions,
              delta=compute_delta(cur.total_impressions, prev.total_impressions)),
            s(lang, "cmp_engagement",
              prev=prev_eng, cur=total_eng,
              delta=compute_delta(total_eng, prev_eng)),
            s(lang, "cmp_er",
              prev=prev.avg_engagement_rate, cur=cur.avg_engagement_rate,
              delta=compute_delta(cur.avg_engagement_rate, prev.avg_engagement_rate)),
            s(lang, "cmp_likes",
              prev=prev.total_likes, cur=cur.total_likes,
              delta=compute_delta(cur.total_likes, prev.total_likes)),
            s(lang, "cmp_retweets", prev=prev.total_retweets, cur=cur.total_retweets),
        ]
    else:
        lines += ["", s(lang, "no_comparison")]

    return "\n".join(lines)


def _part_top_bottom(report: WeeklyReport, lang: str) -> str:
    lines = []

    if report.top_tweets:
        lines.append(s(lang, "top_header"))
        for i, tweet in enumerate(report.top_tweets):
            emoji = EMOJI_NUMS[i] if i < len(EMOJI_NUMS) else f"{i+1}."
            preview = _tweet_preview(tweet.text)
            date_str = tweet.posted_at.strftime("%d %b, %H:%M UTC")
            eng = tweet.likes + tweet.retweets + tweet.replies

            lines.append(f"\n{emoji} *«{_escape_md(preview)}»*")
            lines.append(f"_{date_str}_")
            lines.append(
                s(lang, "interactions_n", n=eng) + " " +
                s(lang, "interactions_detail",
                  likes=tweet.likes, replies=tweet.replies, rt=tweet.retweets)
            )
            lines.append(s(lang, "views_n", n=tweet.impressions, er=tweet.engagement_rate))
            lines.append(f"🔗 https://x.com/i/web/status/{tweet.tweet_id}")

            why = report.ai_top_why[i] if i < len(report.ai_top_why) else ""
            if why:
                lines.append(s(lang, "why_worked", why=why))

    lines += ["", s(lang, "hof_separator"), ""]

    if report.bottom_tweets:
        lines.append(s(lang, "bottom_header"))
        for i, tweet in enumerate(report.bottom_tweets):
            emoji = EMOJI_NUMS[i] if i < len(EMOJI_NUMS) else f"{i+1}."
            preview = _tweet_preview(tweet.text)
            date_str = tweet.posted_at.strftime("%d %b, %H:%M UTC")
            eng = tweet.likes + tweet.retweets + tweet.replies

            lines.append(f"\n{emoji} *«{_escape_md(preview)}»*")
            lines.append(f"_{date_str}_")
            lines.append(s(lang, "interactions_short",
                           n=eng, imp=tweet.impressions, er=tweet.engagement_rate))
            lines.append(f"🔗 https://x.com/i/web/status/{tweet.tweet_id}")

            why = report.ai_bottom_why[i] if i < len(report.ai_bottom_why) else ""
            if why:
                lines.append(s(lang, "why_flopped", why=why))

    if report.top_tweets and report.bottom_tweets:
        best = report.top_tweets[0]
        worst = report.bottom_tweets[0]
        lines += [
            "",
            s(lang, "er_analysis_header"),
            s(lang, "er_best", er=best.engagement_rate, preview=_tweet_preview(best.text)),
            s(lang, "er_worst", er=worst.engagement_rate, preview=_tweet_preview(worst.text)),
        ]

    return "\n".join(lines)


def _part_timing_and_recs(report: WeeklyReport, lang: str) -> str:
    lines = []

    if report.best_hours:
        lines.append(s(lang, "timing_header"))
        lines.append(s(lang, "top_hours_label"))
        for hour, avg_er in report.best_hours:
            lines.append(s(lang, "hour_line", h=hour, er=avg_er))

    if report.best_days:
        top_days = report.best_days[:3]
        days_str = ", ".join(f"{d} ({er:.1f}%)" for d, er in top_days)
        lines.append(s(lang, "best_days_line", days=days_str))
        worst_day = report.best_days[-1]
        lines.append(s(lang, "avoid_day_line", day=worst_day[0], er=worst_day[1]))

    if report.ai_recommendations:
        lines += ["", s(lang, "recs_header")]
        recs = report.ai_recommendations
        for emoji in ["2️⃣", "3️⃣", "4️⃣", "5️⃣"]:
            recs = recs.replace(emoji, f"\n{emoji}")
        lines.append(recs)

    return "\n".join(lines)


# ─── Hall of Fame ────────────────────────────────────────────────────────────

def format_hall_of_fame_message(
    new_entries: list,
    hall_of_fame: list[dict],
    lang: str = "en",
) -> str:
    lines = [s(lang, "hof_header"), ""]

    if len(new_entries) == 1:
        lines.append(s(lang, "hof_one"))
    else:
        lines.append(s(lang, "hof_many", n=len(new_entries)))
    lines.append("")

    for tweet in new_entries:
        preview = _tweet_preview(tweet.text, max_len=60)
        date_str = tweet.posted_at.strftime("%d %b %Y")
        lines.append(f"✨ *«{_escape_md(preview)}»*")
        lines.append(
            f"_{date_str}_ · ER: *{tweet.engagement_rate:.1f}%*"
            f" · 👁 {tweet.impressions:,} · ❤️ {tweet.likes}"
        )
        lines.append(f"🔗 https://x.com/i/web/status/{tweet.tweet_id}")
        lines.append("")

    lines += [s(lang, "hof_separator"), "", s(lang, "hof_top3_header"), ""]

    for i, entry in enumerate(hall_of_fame[:3]):
        medal = HOF_MEDALS[i] if i < len(HOF_MEDALS) else f"{i+1}."
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


# ─── Monthly report ──────────────────────────────────────────────────────────

def format_monthly_report(report: MonthlyReport, lang: str = "en") -> list[str]:
    lines = [
        s(lang, "monthly_header", month=report.month_label.upper()),
        f"_{report.period_label}_",
        "",
        s(lang, "monthly_totals_header"),
        s(lang, "monthly_posts", n=report.total_tweets),
        s(lang, "monthly_impressions", n=report.total_impressions),
        s(lang, "monthly_avg_er", n=report.avg_er),
        s(lang, "monthly_trend", trend=report.trend),
        "",
        s(lang, "monthly_weeks_header"),
    ]

    for i, week in enumerate(report.weeks, 1):
        st = week["stats"]
        lines.append(s(lang, "monthly_week_line",
                       i=i,
                       label=_escape_md(week.get("period_label", f"Week {i}")),
                       posts=st.get("tweet_count", 0),
                       imp=st.get("total_impressions", 0),
                       er=st.get("avg_engagement_rate", 0.0)))

    best_er = report.best_week["stats"].get("avg_engagement_rate", 0.0)
    worst_er = report.worst_week["stats"].get("avg_engagement_rate", 0.0)
    lines += [
        "",
        s(lang, "monthly_best_week",
          label=_escape_md(report.best_week.get("period_label", "")), er=best_er),
        s(lang, "monthly_worst_week",
          label=_escape_md(report.worst_week.get("period_label", "")), er=worst_er),
    ]

    if report.top_tweet:
        t = report.top_tweet
        preview = _tweet_preview(t.get("text", ""), max_len=50)
        lines += [
            "",
            s(lang, "monthly_top_tweet_header"),
            f"*«{_escape_md(preview)}»*",
            f"ER: *{t.get('engagement_rate', 0):.1f}%*"
            f" · 👁 {t.get('impressions', 0):,} · ❤️ {t.get('likes', 0)}",
            f"🔗 https://x.com/i/web/status/{t.get('tweet_id', '')}",
        ]

    if report.ai_summary:
        lines += [
            "",
            s(lang, "ai_analysis_header"),
            _escape_md(report.ai_summary),
        ]

    return ["\n".join(lines)]


# ─── Language selection (first-run inline keyboard) ──────────────────────────

async def send_language_selection(bot_token: str, channel_id: str) -> Optional[str]:
    """
    Sends an inline keyboard asking the user to pick EN or RU.
    Polls for up to 90 seconds. Returns "en" or "ru", or None on timeout.
    """
    try:
        from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
        from telegram.constants import ParseMode
    except ImportError:
        print("[Lang] python-telegram-bot not available — defaulting to 'en'")
        return None

    bot = Bot(token=bot_token)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        ]
    ])

    await bot.send_message(
        chat_id=channel_id,
        text="🌍 *Choose your report language / Выберите язык отчётов:*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )
    print("[Lang] Language selection sent. Waiting up to 90 seconds...")

    # Poll getUpdates for callback
    offset = None
    for _ in range(18):  # 18 × 5 s = 90 s
        updates = await bot.get_updates(offset=offset, timeout=5, allowed_updates=["callback_query"])
        for upd in updates:
            offset = upd.update_id + 1
            cb = upd.callback_query
            if cb and cb.data in ("lang_en", "lang_ru"):
                chosen = cb.data.split("_")[1]  # "en" or "ru"
                await cb.answer()
                confirm = s(chosen, "lang_saved")
                await bot.send_message(
                    chat_id=channel_id,
                    text=confirm,
                    parse_mode=ParseMode.MARKDOWN,
                )
                print(f"[Lang] User selected: {chosen}")
                return chosen
        await asyncio.sleep(5)

    print("[Lang] No response — defaulting to 'en'")
    return None


# ─── Sending ─────────────────────────────────────────────────────────────────

async def send_report_async(
    bot_token: str,
    channel_id: str,
    messages: list[str],
):
    try:
        from telegram import Bot
        from telegram.constants import ParseMode

        bot = Bot(token=bot_token)
        for text in messages:
            if not text.strip():
                continue
            for chunk in _split_message(text):
                await bot.send_message(
                    chat_id=channel_id,
                    text=chunk,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )
                await asyncio.sleep(0.5)

        print(f"[Telegram] Sent {len(messages)} message(s) to {channel_id}")

    except ImportError:
        await _send_via_requests(bot_token, channel_id, messages)
    except Exception as e:
        print(f"[Telegram] Send error: {e}")
        raise


async def _send_via_requests(bot_token: str, channel_id: str, messages: list[str]):
    import urllib.request
    import urllib.parse

    base_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    for text in messages:
        if not text.strip():
            continue
        for chunk in _split_message(text):
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
                    print(f"[Telegram] API error: {result[:200]}")
            await asyncio.sleep(0.5)


async def send_error_notification(
    bot_token: str,
    channel_id: str,
    error_message: str,
    lang: str = "en",
):
    text = (
        f"{s(lang, 'error_header') if 'error_header' in STRINGS.get(lang, {}) else '⚠️ *Twitter Analytics — Error*'}\n\n"
        f"{error_message}\n\n"
        f"{s(lang, 'cookies_expired_hint')}"
    )
    await _send_via_requests(bot_token, channel_id, [text])


def send_report(bot_token: str, channel_id: str, messages: list[str]):
    asyncio.run(send_report_async(bot_token, channel_id, messages))


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _tweet_preview(text: str, max_len: int = 40) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > max_len // 2:
        truncated = truncated[:last_space]
    return truncated + "…"


def _escape_md(text: str) -> str:
    """Escapes Telegram Markdown V1 special chars."""
    return (text
            .replace("*", "\\*")
            .replace("_", "\\_")
            .replace("`", "\\`")
            .replace("[", "\\["))


def _split_message(text: str, max_len: int = 4096) -> list[str]:
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
