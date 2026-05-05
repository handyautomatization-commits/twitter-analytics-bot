"""
main.py — Entry point for Twitter Analytics reports.

Usage:
    python main.py              # weekly report (normal)
    python main.py --test       # test mode with synthetic data, no scraping
    python main.py --dry        # scrape but don't send to Telegram
    python main.py --monthly    # monthly report from archive
    python main.py --monthly --dry
"""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

import scraper as scraper_module
import storage
import analyzer as analyzer_module
import telegram_sender
from strings import s


def get_env(key: str, required: bool = True) -> str:
    value = os.environ.get(key, "")
    if required and not value:
        raise EnvironmentError(
            f"Environment variable {key} is not set. "
            f"Make sure it is added to GitHub Secrets."
        )
    return value


def get_language() -> str:
    """
    Resolves the report language.
    Priority: REPORT_LANGUAGE env var > data/config.json > 'en' default.
    """
    env_lang = os.environ.get("REPORT_LANGUAGE", "").lower().strip()
    if env_lang in ("en", "ru"):
        return env_lang

    config = storage.load_config()
    stored = config.get("language", "").lower().strip()
    if stored in ("en", "ru"):
        return stored

    return "en"


async def _maybe_setup_language(bot_token: str, channel_id: str) -> str:
    """
    On first run (no config.json, no REPORT_LANGUAGE env):
    sends an inline keyboard so the user can choose EN or RU.
    Returns the chosen or default language.
    """
    env_lang = os.environ.get("REPORT_LANGUAGE", "").lower().strip()
    if env_lang in ("en", "ru"):
        return env_lang

    config = storage.load_config()
    if "language" in config:
        return config["language"]

    # First run — ask the user
    print("[Main] First run detected — sending language selection to Telegram...")
    chosen = await telegram_sender.send_language_selection(bot_token, channel_id)
    lang = chosen or "en"

    storage.save_config({"language": lang})
    print(f"[Main] Language saved: {lang}")
    return lang


async def run(test_mode: bool = False, dry_run: bool = False):
    print(f"[Main] Twitter Analytics started — {datetime.now(timezone.utc).isoformat()}")

    bot_token = get_env("TELEGRAM_BOT_TOKEN")
    channel_id = get_env("TELEGRAM_CHANNEL_ID")
    cookies_json = get_env("TWITTER_COOKIES", required=not test_mode)

    # ── 0. Language ────────────────────────────────────────────────────────
    if dry_run or test_mode:
        lang = get_language()
    else:
        lang = await _maybe_setup_language(bot_token, channel_id)
    print(f"[Main] Report language: {lang}")

    # ── 1. Scraping ────────────────────────────────────────────────────────
    if test_mode:
        print("[Main] TEST MODE — using synthetic data")
        current_tweets = _generate_test_tweets()
    else:
        print("[Main] Starting scraper...")
        try:
            current_tweets = await scraper_module.scrape_analytics(cookies_json)
            print(f"[Main] Got {len(current_tweets)} tweets")
            await _check_cookie_age(bot_token, channel_id, lang)
        except RuntimeError as e:
            error_msg = str(e)
            print(f"[Main] ERROR: {error_msg}")
            if not dry_run:
                await telegram_sender.send_error_notification(bot_token, channel_id, error_msg, lang)
            sys.exit(1)

    if not current_tweets:
        error_msg = (
            "No tweets found for the last 7 days. "
            "Either nothing was posted this week, "
            "or x.com/i/account_analytics changed its structure."
            if lang == "en" else
            "Не удалось найти твиты за последние 7 дней. "
            "Возможно, ты не публиковал(а) ничего на этой неделе, "
            "или analytics.twitter.com изменил структуру страницы."
        )
        print(f"[Main] WARNING: {error_msg}")
        if not dry_run:
            await telegram_sender.send_error_notification(bot_token, channel_id, error_msg, lang)
        return

    # ── 2. Save current week ───────────────────────────────────────────────
    storage.save_current_week(current_tweets)

    # ── 3. Load previous week ──────────────────────────────────────────────
    previous_tweets = storage.load_previous_week()

    # ── 4. Analyse ─────────────────────────────────────────────────────────
    print("[Main] Analysing...")
    report = analyzer_module.build_report(current_tweets, previous_tweets, lang)

    # ── 5. Format ──────────────────────────────────────────────────────────
    messages = telegram_sender.format_report(report, lang)

    # ── 6. Send weekly report ──────────────────────────────────────────────
    if dry_run:
        print("[Main] DRY RUN — not sending to Telegram. Report preview:")
        for i, msg in enumerate(messages, 1):
            print(f"\n{'='*60}\nMESSAGE {i}:\n{'='*60}")
            print(msg)
    else:
        print("[Main] Sending report to Telegram...")
        await telegram_sender.send_report_async(bot_token, channel_id, messages)

    # ── 6.5. Hall of Fame ──────────────────────────────────────────────────
    hall_of_fame = storage.load_hall_of_fame()
    updated_hof, new_hof_entries = analyzer_module.check_and_update_hall_of_fame(
        current_tweets, hall_of_fame, report.period_label
    )
    if new_hof_entries:
        storage.save_hall_of_fame(updated_hof)
        hof_msg = telegram_sender.format_hall_of_fame_message(new_hof_entries, updated_hof, lang)
        if dry_run:
            print(f"\n{'='*60}\nHALL OF FAME:\n{'='*60}")
            print(hof_msg)
        else:
            print(f"[Main] {len(new_hof_entries)} new Hall of Fame entries. Sending...")
            await telegram_sender.send_report_async(bot_token, channel_id, [hof_msg])
    else:
        print("[Main] No new Hall of Fame entries this week.")

    # ── 7. Archive week ────────────────────────────────────────────────────
    storage.archive_weekly_data(current_tweets, report.period_label, report.current)

    # ── 8. Rotate data (current → previous) ───────────────────────────────
    storage.rotate_weeks()

    print("[Main] Done!")


async def run_monthly(dry_run: bool = False):
    """Generates and sends the monthly report from the weekly archive."""
    print(f"[Main] Monthly report — {datetime.now(timezone.utc).isoformat()}")

    bot_token = get_env("TELEGRAM_BOT_TOKEN")
    channel_id = get_env("TELEGRAM_CHANNEL_ID")
    lang = get_language()
    print(f"[Main] Report language: {lang}")

    weeks = storage.load_weekly_archive(n=4)

    if not weeks:
        msg = s(lang, "monthly_no_data")
        if dry_run:
            print("[Main] DRY RUN — Monthly report (no data):")
            print(msg)
        else:
            await telegram_sender.send_report_async(bot_token, channel_id, [msg])
        return

    print(f"[Main] Loaded {len(weeks)} weeks from archive.")

    report = analyzer_module.build_monthly_report(weeks, lang)
    if not report:
        print("[Main] Could not build monthly report.")
        return

    messages = telegram_sender.format_monthly_report(report, lang)

    if dry_run:
        print("[Main] DRY RUN — Monthly report:")
        for i, msg in enumerate(messages, 1):
            print(f"\n{'='*60}\nMONTHLY REPORT {i}:\n{'='*60}")
            print(msg)
    else:
        print("[Main] Sending monthly report to Telegram...")
        await telegram_sender.send_report_async(bot_token, channel_id, messages)

    print("[Main] Monthly report done!")


async def _check_cookie_age(bot_token: str, channel_id: str, lang: str = "en"):
    """Warns in Telegram if TWITTER_COOKIES are older than 75 days."""
    updated_at_str = os.environ.get("COOKIES_UPDATED_AT", "")
    if not updated_at_str:
        print("[Main] COOKIES_UPDATED_AT not set — skipping cookie age check.")
        return

    try:
        updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
    except Exception as e:
        print(f"[Main] Could not parse COOKIES_UPDATED_AT='{updated_at_str}': {e}")
        return

    age_days = (datetime.now(timezone.utc) - updated_at).days
    print(f"[Main] Cookie age: {age_days} days (updated {updated_at.strftime('%d.%m.%Y')})")

    if age_days >= 75:
        remaining = 90 - age_days
        date_str = updated_at.strftime("%d.%m.%Y")
        if lang == "ru":
            if remaining <= 0:
                msg = (
                    "⚠️ *ВНИМАНИЕ: cookies Twitter устарели!*\n\n"
                    f"Последнее обновление: *{date_str}* ({age_days} дней назад)\n\n"
                    "Cookies истекли или вот-вот истекут. Скрапинг может сломаться в любой момент.\n\n"
                    "👉 Обнови секрет *TWITTER_COOKIES* в GitHub через Cookie-Editor."
                )
            else:
                msg = (
                    f"⚠️ *Cookies Twitter скоро истекут*\n\n"
                    f"Последнее обновление: *{date_str}* ({age_days} дней назад)\n"
                    f"Осталось примерно *{remaining} дней*.\n\n"
                    "👉 Обнови секрет *TWITTER_COOKIES* в GitHub через Cookie-Editor."
                )
        else:
            if remaining <= 0:
                msg = (
                    "⚠️ *Twitter cookies have expired!*\n\n"
                    f"Last updated: *{date_str}* ({age_days} days ago)\n\n"
                    "Scraping may break at any moment.\n\n"
                    "👉 Re-export via Cookie-Editor and update the *TWITTER_COOKIES* secret in GitHub."
                )
            else:
                msg = (
                    f"⚠️ *Twitter cookies expiring soon*\n\n"
                    f"Last updated: *{date_str}* ({age_days} days ago)\n"
                    f"Approximately *{remaining} days* remaining.\n\n"
                    "👉 Re-export via Cookie-Editor and update the *TWITTER_COOKIES* secret in GitHub."
                )
        await telegram_sender.send_report_async(bot_token, channel_id, [msg])
        print(f"[Main] Cookie age warning sent (age={age_days}d, remaining≈{remaining}d).")


def _generate_test_tweets() -> list:
    """Generates synthetic tweets for testing without real Twitter."""
    from scraper import TweetData

    now = datetime.now(timezone.utc)
    tweets = [
        TweetData(
            tweet_id=f"test_{i}",
            text=f"Test tweet #{i}: {'Great Python content!' if i % 3 == 0 else 'Thoughts on productivity' if i % 3 == 1 else 'Random thought out loud'}",
            posted_at=now - timedelta(days=i % 7, hours=i * 3 % 24),
            impressions=1000 * (10 - i) + 500,
            likes=50 + i * 10,
            retweets=5 + i,
            replies=3 + i,
            link_clicks=10 + i * 2,
            profile_clicks=20 + i,
            engagements=80 + i * 15,
        )
        for i in range(1, 10)
    ]
    return tweets


if __name__ == "__main__":
    test_mode = "--test" in sys.argv
    dry_run = "--dry" in sys.argv
    monthly = "--monthly" in sys.argv

    if monthly:
        asyncio.run(run_monthly(dry_run=dry_run))
    else:
        asyncio.run(run(test_mode=test_mode, dry_run=dry_run))
