"""
main.py — Точка входа для отчётов Twitter Analytics.

Используется из GitHub Actions (или локально для тестирования):
    python main.py             # обычный еженедельный запуск
    python main.py --test      # тест без реального scraping (синтетические данные)
    python main.py --dry       # scraping без отправки в Telegram
    python main.py --monthly   # ежемесячный отчёт из архива
    python main.py --monthly --dry  # превью ежемесячного отчёта
"""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

import scraper as scraper_module
import storage
import analyzer as analyzer_module
import telegram_sender


def get_env(key: str, required: bool = True) -> str:
    value = os.environ.get(key, "")
    if required and not value:
        raise EnvironmentError(
            f"Переменная окружения {key} не задана. "
            f"Убедись, что она добавлена в GitHub Secrets."
        )
    return value


async def run(test_mode: bool = False, dry_run: bool = False):
    print(f"[Main] Запуск Twitter Analytics — {datetime.now(timezone.utc).isoformat()}")

    bot_token = get_env("TELEGRAM_BOT_TOKEN")
    channel_id = get_env("TELEGRAM_CHANNEL_ID")
    cookies_json = get_env("TWITTER_COOKIES", required=not test_mode)

    # ── 1. Scraping ────────────────────────────────────────────────────────
    if test_mode:
        print("[Main] ТЕСТОВЫЙ РЕЖИМ — используются синтетические данные")
        current_tweets = _generate_test_tweets()
    else:
        print("[Main] Запускаю scraper...")
        try:
            current_tweets = await scraper_module.scrape_analytics(cookies_json)
            print(f"[Main] Получено {len(current_tweets)} твитов")
            await _check_cookie_age(bot_token, channel_id)
        except RuntimeError as e:
            error_msg = str(e)
            print(f"[Main] ОШИБКА: {error_msg}")
            if not dry_run:
                await telegram_sender.send_error_notification(bot_token, channel_id, error_msg)
            sys.exit(1)

    if not current_tweets:
        error_msg = (
            "Не удалось найти твиты за последние 7 дней. "
            "Возможно, ты не публиковал(а) ничего на этой неделе, "
            "или analytics.twitter.com изменил структуру страницы."
        )
        print(f"[Main] ПРЕДУПРЕЖДЕНИЕ: {error_msg}")
        if not dry_run:
            await telegram_sender.send_error_notification(bot_token, channel_id, error_msg)
        return

    # ── 2. Сохранение данных ───────────────────────────────────────────────
    storage.save_current_week(current_tweets)

    # ── 3. Загрузка прошлой недели ─────────────────────────────────────────
    previous_tweets = storage.load_previous_week()

    # ── 4. Анализ ──────────────────────────────────────────────────────────
    print("[Main] Анализирую данные...")
    report = analyzer_module.build_report(current_tweets, previous_tweets)

    # ── 5. Форматирование отчёта ────────────────────────────────────────────
    messages = telegram_sender.format_report(report)

    # ── 6. Отправка в Telegram ─────────────────────────────────────────────
    if dry_run:
        print("[Main] DRY RUN — не отправляю в Telegram. Содержимое отчёта:")
        for i, msg in enumerate(messages, 1):
            print(f"\n{'='*60}\nСООБЩЕНИЕ {i}:\n{'='*60}")
            print(msg)
    else:
        print("[Main] Отправляю отчёт в Telegram...")
        await telegram_sender.send_report_async(bot_token, channel_id, messages)

    # ── 6.5. Зал Славы ─────────────────────────────────────────────────────
    hall_of_fame = storage.load_hall_of_fame()
    updated_hof, new_hof_entries = analyzer_module.check_and_update_hall_of_fame(
        current_tweets, hall_of_fame, report.period_label
    )
    if new_hof_entries:
        storage.save_hall_of_fame(updated_hof)
        hof_msg = telegram_sender.format_hall_of_fame_message(new_hof_entries, updated_hof)
        if dry_run:
            print(f"\n{'='*60}\nЗАЛ СЛАВЫ:\n{'='*60}")
            print(hof_msg)
        else:
            print(f"[Main] {len(new_hof_entries)} новых записей в Зале Славы. Отправляю поздравление...")
            await telegram_sender.send_report_async(bot_token, channel_id, [hof_msg])
    else:
        print("[Main] Нет новых записей в Зале Славы на этой неделе.")

    # ── 7. Архивирование недели (для ежемесячного отчёта) ─────────────────
    storage.archive_weekly_data(current_tweets, report.period_label, report.current)

    # ── 8. Ротация данных (current → previous) ─────────────────────────────
    storage.rotate_weeks()

    print("[Main] Готово!")


async def run_monthly(dry_run: bool = False):
    """Генерирует и отправляет ежемесячный отчёт на основе архива недель."""
    print(f"[Main] Ежемесячный отчёт — {datetime.now(timezone.utc).isoformat()}")

    bot_token = get_env("TELEGRAM_BOT_TOKEN")
    channel_id = get_env("TELEGRAM_CHANNEL_ID")

    # Берём последние 4 недели из архива
    weeks = storage.load_weekly_archive(n=4)

    if not weeks:
        msg = (
            "📅 *Ежемесячный отчёт*\n\n"
            "Недостаточно данных для отчёта — архив недель пуст.\n"
            "Данные накопятся после нескольких еженедельных запусков."
        )
        if dry_run:
            print("[Main] DRY RUN — Monthly report (нет данных):")
            print(msg)
        else:
            await telegram_sender.send_report_async(bot_token, channel_id, [msg])
        return

    print(f"[Main] Загружено {len(weeks)} недель из архива.")

    report = analyzer_module.build_monthly_report(weeks)
    if not report:
        print("[Main] Не удалось построить ежемесячный отчёт.")
        return

    messages = telegram_sender.format_monthly_report(report)

    if dry_run:
        print("[Main] DRY RUN — Monthly report:")
        for i, msg in enumerate(messages, 1):
            print(f"\n{'='*60}\nМЕСЯЧНЫЙ ОТЧЁТ {i}:\n{'='*60}")
            print(msg)
    else:
        print("[Main] Отправляю ежемесячный отчёт в Telegram...")
        await telegram_sender.send_report_async(bot_token, channel_id, messages)

    print("[Main] Ежемесячный отчёт готов!")


async def _check_cookie_age(bot_token: str, channel_id: str):
    """
    Проверяет возраст TWITTER_COOKIES и отправляет предупреждение
    если cookies старше 75 дней.
    """
    updated_at_str = os.environ.get("COOKIES_UPDATED_AT", "")
    if not updated_at_str:
        print("[Main] COOKIES_UPDATED_AT не задан — пропускаю проверку возраста cookies.")
        return

    try:
        updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
    except Exception as e:
        print(f"[Main] Не удалось разобрать COOKIES_UPDATED_AT='{updated_at_str}': {e}")
        return

    age_days = (datetime.now(timezone.utc) - updated_at).days
    print(f"[Main] Возраст cookies: {age_days} дней (обновлены {updated_at.strftime('%d.%m.%Y')})")

    if age_days >= 75:
        remaining = 90 - age_days
        if remaining <= 0:
            msg = (
                "⚠️ *ВНИМАНИЕ: cookies Twitter устарели!*\n\n"
                f"Последнее обновление: *{updated_at.strftime('%d.%m.%Y')}* ({age_days} дней назад)\n\n"
                "Cookies истекли или вот-вот истекут. Скрапинг может сломаться в любой момент.\n\n"
                "👉 Обнови секрет *TWITTER_COOKIES* в GitHub через Cookie-Editor."
            )
        else:
            msg = (
                f"⚠️ *Cookies Twitter скоро истекут*\n\n"
                f"Последнее обновление: *{updated_at.strftime('%d.%m.%Y')}* ({age_days} дней назад)\n"
                f"Осталось примерно *{remaining} дней* до истечения срока действия.\n\n"
                "👉 Обнови секрет *TWITTER_COOKIES* в GitHub через Cookie-Editor."
            )
        await telegram_sender.send_report_async(bot_token, channel_id, [msg])
        print(f"[Main] Отправлено предупреждение о cookies (age={age_days}d, remaining≈{remaining}d).")


def _generate_test_tweets() -> list:
    """Генерирует тестовые данные для проверки без реального Twitter."""
    from scraper import TweetData

    now = datetime.now(timezone.utc)
    tweets = [
        TweetData(
            tweet_id=f"test_{i}",
            text=f"Тестовый твит #{i}: {'Отличный контент о Python!' if i % 3 == 0 else 'Размышления о продуктивности' if i % 3 == 1 else 'Случайная мысль вслух'}",
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
