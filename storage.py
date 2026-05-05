"""
storage.py — Хранение данных твитов между неделями.

Данные сохраняются в папку data/ в JSON-формате.
В GitHub Actions папка data/ коммитится обратно в репозиторий
чтобы сравнение с прошлой неделей работало между запусками.
"""

import json
from pathlib import Path
from datetime import datetime, timezone

from scraper import TweetData


DATA_DIR = Path("data")
CURRENT_WEEK_FILE = DATA_DIR / "current_week.json"
PREVIOUS_WEEK_FILE = DATA_DIR / "previous_week.json"
HALL_OF_FAME_FILE = DATA_DIR / "hall_of_fame.json"
WEEKLY_ARCHIVE_FILE = DATA_DIR / "weekly_archive.json"


def ensure_data_dir():
    DATA_DIR.mkdir(exist_ok=True)


def save_current_week(tweets: list[TweetData]):
    """Сохраняет данные текущей недели."""
    ensure_data_dir()

    payload = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "tweet_count": len(tweets),
        "tweets": [t.to_dict() for t in tweets],
    }

    CURRENT_WEEK_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[Storage] Сохранено {len(tweets)} твитов в {CURRENT_WEEK_FILE}")


def load_current_week() -> list[TweetData]:
    """Загружает данные текущей недели (если есть)."""
    if not CURRENT_WEEK_FILE.exists():
        return []

    try:
        data = json.loads(CURRENT_WEEK_FILE.read_text(encoding="utf-8"))
        return [TweetData.from_dict(t) for t in data.get("tweets", [])]
    except Exception as e:
        print(f"[Storage] Ошибка чтения current_week.json: {e}")
        return []


def load_previous_week() -> list[TweetData]:
    """Загружает данные прошлой недели для сравнения."""
    if not PREVIOUS_WEEK_FILE.exists():
        print("[Storage] Данных прошлой недели нет (первый запуск).")
        return []

    try:
        data = json.loads(PREVIOUS_WEEK_FILE.read_text(encoding="utf-8"))
        return [TweetData.from_dict(t) for t in data.get("tweets", [])]
    except Exception as e:
        print(f"[Storage] Ошибка чтения previous_week.json: {e}")
        return []


def rotate_weeks():
    """
    Переносит current_week.json → previous_week.json.
    Вызывается ПОСЛЕ отправки отчёта.
    """
    ensure_data_dir()

    if CURRENT_WEEK_FILE.exists():
        import shutil
        shutil.copy2(CURRENT_WEEK_FILE, PREVIOUS_WEEK_FILE)
        print(f"[Storage] {CURRENT_WEEK_FILE} → {PREVIOUS_WEEK_FILE}")
    else:
        print("[Storage] Нет current_week.json для ротации.")


def load_hall_of_fame() -> list[dict]:
    """Загружает Зал Славы. Возвращает список dict-записей (пустой если файла нет)."""
    if not HALL_OF_FAME_FILE.exists():
        return []
    try:
        data = json.loads(HALL_OF_FAME_FILE.read_text(encoding="utf-8"))
        return data.get("entries", [])
    except Exception as e:
        print(f"[Storage] Ошибка чтения hall_of_fame.json: {e}")
        return []


def save_hall_of_fame(entries: list[dict]):
    """Сохраняет обновлённый Зал Славы."""
    ensure_data_dir()
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "entries": entries,
    }
    HALL_OF_FAME_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[Storage] Зал Славы обновлён: {len(entries)} записей")


def archive_weekly_data(tweets: list[TweetData], period_label: str, stats):
    """
    Добавляет снимок текущей недели в архив для ежемесячного отчёта.
    Хранит до 52 недель (1 год).
    """
    ensure_data_dir()

    existing = load_weekly_archive()

    # Лучший твит недели (для топ-твита месяца)
    top_tweet = None
    eligible = [t for t in tweets if t.impressions > 0]
    if eligible:
        best = max(eligible, key=lambda t: t.engagement_rate)
        top_tweet = {
            "tweet_id": best.tweet_id,
            "text": best.text[:100],
            "engagement_rate": best.engagement_rate,
            "impressions": best.impressions,
            "likes": best.likes,
        }

    week_entry = {
        "period_label": period_label,
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats.to_dict(),
        "top_tweet": top_tweet,
    }

    existing.append(week_entry)
    existing = existing[-52:]  # не более года

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "weeks": existing,
    }
    WEEKLY_ARCHIVE_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[Storage] Неделя «{period_label}» добавлена в архив ({len(existing)} недель всего)")


def load_weekly_archive(n: int = 0) -> list[dict]:
    """
    Загружает архив недель.
    n=0 — все недели, n>0 — последние n недель.
    """
    if not WEEKLY_ARCHIVE_FILE.exists():
        return []
    try:
        data = json.loads(WEEKLY_ARCHIVE_FILE.read_text(encoding="utf-8"))
        weeks = data.get("weeks", [])
        return weeks[-n:] if n > 0 else weeks
    except Exception as e:
        print(f"[Storage] Ошибка чтения weekly_archive.json: {e}")
        return []


def get_meta() -> dict:
    """Возвращает метаданные о сохранённых данных."""
    meta = {}

    for label, path in [("current", CURRENT_WEEK_FILE), ("previous", PREVIOUS_WEEK_FILE)]:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                meta[label] = {
                    "scraped_at": data.get("scraped_at"),
                    "tweet_count": data.get("tweet_count", 0),
                }
            except Exception:
                meta[label] = None
        else:
            meta[label] = None

    return meta
