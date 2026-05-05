"""
analyzer.py — Анализ метрик твитов и генерация AI-советов.

Вычисляет:
- Топ-3 и худшие-3 твиты по engagement rate
- Лучшее время для постинга
- Сравнение с прошлой неделей
- AI-анализ контента через Google Gemini (бесплатный tier)
"""

import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from scraper import TweetData


# ─── Структуры данных отчёта ────────────────────────────────────────────────

@dataclass
class WeekStats:
    tweet_count: int = 0
    total_impressions: int = 0
    total_engagements: int = 0
    total_likes: int = 0
    total_retweets: int = 0
    total_replies: int = 0
    avg_engagement_rate: float = 0.0

    def to_dict(self) -> dict:
        return self.__dict__


@dataclass
class WeeklyReport:
    period_label: str
    current: WeekStats
    previous: Optional[WeekStats]
    top_tweets: list[TweetData]
    bottom_tweets: list[TweetData]
    best_hours: list[tuple[int, float]]  # [(hour, avg_er), ...]
    best_days: list[tuple[str, float]]   # [(day_name, avg_er), ...]
    ai_analysis: str = ""               # fallback полный текст
    ai_top_why: list[str] = field(default_factory=list)     # почему зашёл (по 1 на твит)
    ai_bottom_why: list[str] = field(default_factory=list)  # почему не зашёл
    ai_recommendations: str = ""        # секция рекомендаций
    all_tweets: list[TweetData] = field(default_factory=list)


# ─── Вычисление метрик ──────────────────────────────────────────────────────

def compute_stats(tweets: list[TweetData]) -> WeekStats:
    if not tweets:
        return WeekStats()

    total_impressions = sum(t.impressions for t in tweets)
    total_engagements = sum(t.engagements for t in tweets)
    avg_er = (
        sum(t.engagement_rate for t in tweets) / len(tweets)
        if tweets else 0.0
    )

    return WeekStats(
        tweet_count=len(tweets),
        total_impressions=total_impressions,
        total_engagements=total_engagements,
        total_likes=sum(t.likes for t in tweets),
        total_retweets=sum(t.retweets for t in tweets),
        total_replies=sum(t.replies for t in tweets),
        avg_engagement_rate=round(avg_er, 2),
    )


def get_top_tweets(tweets: list[TweetData], n: int = 3) -> list[TweetData]:
    """Топ-N твитов по engagement rate."""
    eligible = [t for t in tweets if t.impressions > 0]
    if not eligible:
        return []
    sorted_tweets = sorted(eligible, key=lambda t: t.engagement_rate, reverse=True)
    # Берём топ-N, но следим чтобы топ и худшие не пересекались
    return sorted_tweets[:n]


def get_bottom_tweets(tweets: list[TweetData], n: int = 3) -> list[TweetData]:
    """Худшие N твитов по engagement rate (не пересекаются с топом)."""
    eligible = [t for t in tweets if t.impressions > 0]
    if not eligible:
        return []
    sorted_tweets = sorted(eligible, key=lambda t: t.engagement_rate)
    # Исключаем топ-N чтобы один твит не был и лучшим и худшим
    top_ids = {t.tweet_id for t in sorted_tweets[-n:]}
    bottom = [t for t in sorted_tweets if t.tweet_id not in top_ids]
    return bottom[:n]


def get_best_posting_hours(tweets: list[TweetData], top_n: int = 3) -> list[tuple[int, float]]:
    """
    Возвращает топ-N часов с лучшим средним engagement rate.
    Возвращает: [(hour, avg_er), ...]
    """
    hour_data: dict[int, list[float]] = defaultdict(list)

    for tweet in tweets:
        hour = tweet.posted_at.hour
        if tweet.impressions > 0:
            hour_data[hour].append(tweet.engagement_rate)

    if not hour_data:
        return []

    hour_avgs = [
        (hour, sum(ers) / len(ers))
        for hour, ers in hour_data.items()
    ]
    return sorted(hour_avgs, key=lambda x: x[1], reverse=True)[:top_n]


def get_best_posting_days(tweets: list[TweetData]) -> list[tuple[str, float]]:
    """Возвращает дни недели по убыванию среднего engagement rate."""
    day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    day_data: dict[int, list[float]] = defaultdict(list)

    for tweet in tweets:
        day = tweet.posted_at.weekday()
        if tweet.impressions > 0:
            day_data[day].append(tweet.engagement_rate)

    if not day_data:
        return []

    day_avgs = [
        (day_names[day], sum(ers) / len(ers))
        for day, ers in day_data.items()
    ]
    return sorted(day_avgs, key=lambda x: x[1], reverse=True)


def compute_delta(current: int | float, previous: int | float) -> str:
    """Форматирует изменение в виде '+12%' или '-5%'."""
    if previous == 0:
        return "новое"
    delta_pct = (current - previous) / previous * 100
    sign = "+" if delta_pct >= 0 else ""
    return f"{sign}{delta_pct:.0f}%"


# ─── AI-анализ через DeepSeek ───────────────────────────────────────────────

def generate_ai_analysis(
    tweets: list[TweetData],
    stats: WeekStats,
    prev_stats: Optional[WeekStats],
    top_tweets: list[TweetData],
    bottom_tweets: list[TweetData],
) -> dict:
    """
    Генерирует AI-анализ через DeepSeek API.
    Возвращает dict с ключами: top_why (list), bottom_why (list), recommendations (str).
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")

    if not api_key:
        return _fallback_analysis_dict(top_tweets, bottom_tweets, stats)

    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )

        prompt = _build_prompt(tweets, stats, prev_stats, top_tweets, bottom_tweets)
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )
        raw = response.choices[0].message.content.strip()
        return _parse_ai_response(raw, len(top_tweets), len(bottom_tweets))

    except ImportError:
        return _fallback_analysis_dict(top_tweets, bottom_tweets, stats)
    except Exception as e:
        print(f"[Analyzer] Ошибка DeepSeek API: {e}")
        return _fallback_analysis_dict(top_tweets, bottom_tweets, stats)


def _build_prompt(
    tweets: list[TweetData],
    stats: WeekStats,
    prev_stats: Optional[WeekStats],
    top_tweets: list[TweetData],
    bottom_tweets: list[TweetData],
) -> str:
    def fmt(t: TweetData) -> str:
        return (
            f"«{t.text[:120]}»\n"
            f"  {t.likes} лайков, {t.replies} реплаев, {t.impressions} просмотров, ER: {t.engagement_rate:.1f}%"
        )

    top_lines = "\n".join(f"Твит {i+1}: {fmt(t)}" for i, t in enumerate(top_tweets))
    bot_lines = "\n".join(f"Твит {i+1}: {fmt(t)}" for i, t in enumerate(bottom_tweets))

    comparison = ""
    if prev_stats:
        comparison = (
            f"Прошлая неделя: {prev_stats.total_impressions:,} просмотров, "
            f"ER {prev_stats.avg_engagement_rate:.1f}%\n"
        )

    n_top = len(top_tweets)
    n_bot = len(bottom_tweets)
    top_keys = "\n".join(f"TOP_WHY_{i+1}: [1-2 предложения]" for i in range(n_top))
    bot_keys = "\n".join(f"BOTTOM_WHY_{i+1}: [1-2 предложения]" for i in range(n_bot))

    return f"""Ты — аналитик Twitter-контента. Пиши на русском, кратко и конкретно.

СТАТИСТИКА НЕДЕЛИ:
Постов: {stats.tweet_count}, Просмотры: {stats.total_impressions:,}, ER: {stats.avg_engagement_rate:.1f}%
Лайки: {stats.total_likes:,}, Ретвиты: {stats.total_retweets:,}, Ответы: {stats.total_replies:,}
{comparison}
ЛУЧШИЕ ТВИТЫ:
{top_lines}

ХУДШИЕ ТВИТЫ:
{bot_lines}

Ответь СТРОГО в следующем формате (не добавляй ничего лишнего):

{top_keys}

{bot_keys}

RECOMMENDATIONS:
1️⃣ Продолжай:
• [пункт]
• [пункт]
2️⃣ Пересмотри:
• [пункт]
• [пункт]
3️⃣ Тайминг: [конкретные часы и дни]
4️⃣ Формат: [совет по подаче]
5️⃣ ЭКСПЕРИМЕНТ НА НЕДЕЛЮ: [конкретная идея с темой и форматом]"""


def _parse_ai_response(text: str, n_top: int, n_bot: int) -> dict:
    """Парсит структурированный ответ DeepSeek по маркерам TOP_WHY_N / BOTTOM_WHY_N."""
    top_why = []
    for i in range(1, n_top + 1):
        m = re.search(rf"TOP_WHY_{i}:\s*(.+?)(?=\nTOP_WHY_|\nBOTTOM_WHY_|\nRECOMMENDATIONS:|$)",
                      text, re.DOTALL)
        top_why.append(m.group(1).strip() if m else "")

    bottom_why = []
    for i in range(1, n_bot + 1):
        m = re.search(rf"BOTTOM_WHY_{i}:\s*(.+?)(?=\nBOTTOM_WHY_|\nRECOMMENDATIONS:|$)",
                      text, re.DOTALL)
        bottom_why.append(m.group(1).strip() if m else "")

    rec_m = re.search(r"RECOMMENDATIONS:\s*(.+)$", text, re.DOTALL)
    recommendations = rec_m.group(1).strip() if rec_m else ""

    return {"top_why": top_why, "bottom_why": bottom_why, "recommendations": recommendations}


def _fallback_analysis_dict(
    top_tweets: list[TweetData],
    bottom_tweets: list[TweetData],
    stats: WeekStats,
) -> dict:
    """Базовый анализ без AI."""
    top_why = [f"ER {t.engagement_rate:.1f}% — один из лучших результатов недели." for t in top_tweets]
    bottom_why = [f"ER {t.engagement_rate:.1f}% при {t.impressions} просмотрах — слабый отклик." for t in bottom_tweets]

    recs = "1️⃣ Продолжай: • Публикуй в стиле лучших постов недели\n"
    if stats.avg_engagement_rate > 3:
        recs += "2️⃣ Отличный engagement rate — продолжай в том же темпе!\n"
    else:
        recs += "2️⃣ Пересмотри: • Добавляй вопросы к аудитории для повышения ER\n"
    recs += "5️⃣ ЭКСПЕРИМЕНТ: Добавь DEEPSEEK_API_KEY для детального AI-анализа."

    return {"top_why": top_why, "bottom_why": bottom_why, "recommendations": recs}


def _fallback_analysis(tweets: list[TweetData], stats: WeekStats) -> str:
    """Базовый анализ без AI если Gemini недоступен."""
    if not tweets:
        return "Недостаточно данных для анализа."

    top = get_top_tweets(tweets, 3)
    bottom = get_bottom_tweets(tweets, 3)

    lines = []

    if top:
        lines.append("✅ ЧТО ЗАШЛО:")
        for t in top:
            lines.append(f"  • ER {t.engagement_rate:.1f}%: {t.text[:80]}...")

    if bottom:
        lines.append("\n❌ ЧТО НЕ ЗАШЛО:")
        for t in bottom:
            lines.append(f"  • ER {t.engagement_rate:.1f}%: {t.text[:80]}...")

    if stats.avg_engagement_rate > 3:
        lines.append("\n💡 Engagement rate выше среднего — продолжай в том же духе!")
    elif stats.avg_engagement_rate < 1:
        lines.append("\n💡 Низкий engagement. Попробуй задавать вопросы аудитории.")

    lines.append("\n📝 Добавь Gemini API ключ для детальных AI-советов.")

    return "\n".join(lines)


# ─── Зал Славы ───────────────────────────────────────────────────────────────

def compute_hof_score(tweet: TweetData) -> float:
    """
    Составной балл для Зала Славы.
    Учитывает ER, охват (impressions) и качество (лайки, ретвиты).
    Реплаи имеют меньший вес — они уже в ER, но лайки/ретвиты дают бонус.

    Примеры:
      6 просм,  0 лайков, 4 ответа  (ER 67%) → score ~38
      60 просм, 7 лайков, 5 ответов (ER 20%) → score ~58
      22 просм, 4 лайка,  5 ответов (ER 41%) → score ~68
    """
    if tweet.impressions == 0:
        return 0.0
    er = tweet.engagement_rate
    # log-шкала: 6 → 0.57, 30 → 1.0, 60 → 1.13, 100 → 1.26
    imp_factor = math.log2(tweet.impressions + 1) / math.log2(30)
    quality = 1.0 + (tweet.likes * 0.2) + (tweet.retweets * 0.4)
    return round(er * imp_factor * quality, 2)


def _hof_score_from_dict(entry: dict) -> float:
    """Возвращает hof_score из dict-записи (пересчитывает для старых записей без поля)."""
    if entry.get("hof_score") is not None:
        return entry["hof_score"]
    impressions = entry.get("impressions", 0)
    if impressions == 0:
        return 0.0
    er = entry.get("engagement_rate", 0.0)
    imp_factor = math.log2(impressions + 1) / math.log2(30)
    quality = 1.0 + (entry.get("likes", 0) * 0.2) + (entry.get("retweets", 0) * 0.4)
    return round(er * imp_factor * quality, 2)


def check_and_update_hall_of_fame(
    current_tweets: list[TweetData],
    hall_of_fame: list[dict],
    week_label: str,
    max_size: int = 10,
) -> tuple[list[dict], list[TweetData]]:
    """
    Проверяет твиты текущей недели на попадание в Зал Славы.
    Использует hof_score (составной балл), а не чистый ER.
    Возвращает: (обновлённый_зал, новые_записи)
    """
    hof = list(hall_of_fame)
    existing_ids = {entry["tweet_id"] for entry in hof}

    # Порог: минимальный hof_score в заполненном зале, иначе принимаем всех
    min_score = min((_hof_score_from_dict(e) for e in hof), default=-1.0) if len(hof) >= max_size else -1.0

    new_entries: list[TweetData] = []
    for tweet in current_tweets:
        if tweet.tweet_id in existing_ids:
            continue
        tweet_score = compute_hof_score(tweet)
        if tweet_score > min_score:
            entry = tweet.to_dict()
            entry["week_label"] = week_label
            entry["hof_score"] = tweet_score
            hof.append(entry)
            new_entries.append(tweet)
            existing_ids.add(tweet.tweet_id)

    # Сортируем по hof_score и обрезаем до max_size
    hof.sort(key=_hof_score_from_dict, reverse=True)
    hof = hof[:max_size]

    # Оставляем только тех new_entries, кто выжил после обрезки
    surviving_ids = {e["tweet_id"] for e in hof}
    new_entries = [t for t in new_entries if t.tweet_id in surviving_ids]

    return hof, new_entries


# ─── Ежемесячный отчёт ───────────────────────────────────────────────────────

@dataclass
class MonthlyReport:
    month_label: str           # "Апрель 2026"
    period_label: str          # "01 Apr – 30 Apr"
    weeks: list[dict]          # снимки недель из архива
    total_tweets: int
    total_impressions: int
    total_engagements: int
    avg_er: float
    best_week: dict
    worst_week: dict
    top_tweet: Optional[dict]  # лучший твит месяца
    trend: str                 # "📈 Рост" / "📉 Спад" / "➡️ Стабильно"
    ai_summary: str = ""


def build_monthly_report(weeks: list[dict]) -> Optional["MonthlyReport"]:
    """
    Собирает ежемесячный отчёт из снимков последних N недель.
    Возвращает None если недель нет.
    """
    if not weeks:
        return None

    total_tweets = sum(w["stats"].get("tweet_count", 0) for w in weeks)
    total_impressions = sum(w["stats"].get("total_impressions", 0) for w in weeks)
    total_engagements = sum(w["stats"].get("total_engagements", 0) for w in weeks)
    ers = [w["stats"].get("avg_engagement_rate", 0.0) for w in weeks]
    avg_er = round(sum(ers) / len(ers), 2) if ers else 0.0

    best_week = max(weeks, key=lambda w: w["stats"].get("avg_engagement_rate", 0.0))
    worst_week = min(weeks, key=lambda w: w["stats"].get("avg_engagement_rate", 0.0))

    # Лучший твит месяца из top_tweet каждой недели
    top_tweets = [w["top_tweet"] for w in weeks if w.get("top_tweet")]
    top_tweet = max(top_tweets, key=lambda t: t.get("engagement_rate", 0.0)) if top_tweets else None

    trend = _compute_monthly_trend(weeks)

    # Метки
    now = datetime.now()
    ru_months = {
        "January": "Январь", "February": "Февраль", "March": "Март",
        "April": "Апрель", "May": "Май", "June": "Июнь",
        "July": "Июль", "August": "Август", "September": "Сентябрь",
        "October": "Октябрь", "November": "Ноябрь", "December": "Декабрь",
    }
    month_label = now.strftime("%B %Y")
    for en, ru in ru_months.items():
        month_label = month_label.replace(en, ru)

    # Период: от начала первой недели до конца последней
    first = weeks[0].get("period_label", "")
    last = weeks[-1].get("period_label", "")
    if first and last and "–" in first and "–" in last:
        period_label = f"{first.split('–')[0].strip()} – {last.split('–')[-1].strip()}"
    elif first:
        period_label = first
    else:
        period_label = month_label

    ai_summary = _generate_monthly_ai_summary(weeks, total_tweets, total_impressions, avg_er, trend)

    return MonthlyReport(
        month_label=month_label,
        period_label=period_label,
        weeks=weeks,
        total_tweets=total_tweets,
        total_impressions=total_impressions,
        total_engagements=total_engagements,
        avg_er=avg_er,
        best_week=best_week,
        worst_week=worst_week,
        top_tweet=top_tweet,
        trend=trend,
        ai_summary=ai_summary,
    )


def _compute_monthly_trend(weeks: list[dict]) -> str:
    """Сравнивает первую и вторую половины месяца."""
    if len(weeks) < 2:
        return "➡️ Недостаточно данных"
    half = len(weeks) // 2
    first_er = sum(w["stats"].get("avg_engagement_rate", 0.0) for w in weeks[:half]) / half
    second_er = sum(w["stats"].get("avg_engagement_rate", 0.0) for w in weeks[half:]) / max(len(weeks) - half, 1)
    delta = second_er - first_er
    if delta > 0.5:
        return "📈 Рост"
    elif delta < -0.5:
        return "📉 Спад"
    else:
        return "➡️ Стабильно"


def _generate_monthly_ai_summary(
    weeks: list[dict],
    total_tweets: int,
    total_impressions: int,
    avg_er: float,
    trend: str,
) -> str:
    """AI-резюме месяца через DeepSeek."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return ""
    try:
        from openai import OpenAI  # type: ignore
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

        weeks_lines = "\n".join(
            f"  {w['period_label']}: {w['stats']['tweet_count']} постов, "
            f"{w['stats']['total_impressions']:,} просмотров, ER {w['stats']['avg_engagement_rate']:.1f}%"
            for w in weeks
        )
        prompt = f"""Ты — аналитик Twitter-контента. Пиши на русском, кратко и конкретно.

МЕСЯЧНАЯ СВОДКА:
Постов: {total_tweets}, Просмотры: {total_impressions:,}, Средний ER: {avg_er:.1f}%, Тренд: {trend}

ПО НЕДЕЛЯМ:
{weeks_lines}

Дай краткое резюме месяца (2-3 предложения) и 2 конкретных совета на следующий месяц.
Формат:
РЕЗЮМЕ: [текст]
СОВЕТ_1: [текст]
СОВЕТ_2: [текст]"""

        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Analyzer] Ошибка AI-анализа месяца: {e}")
        return ""


# ─── Главная функция ─────────────────────────────────────────────────────────

def build_report(
    current_tweets: list[TweetData],
    previous_tweets: list[TweetData],
) -> WeeklyReport:
    """Собирает полный еженедельный отчёт."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=6)).strftime("%d %b")
    week_end = now.strftime("%d %b")
    period_label = f"{week_start} – {week_end}"

    current_stats = compute_stats(current_tweets)
    previous_stats = compute_stats(previous_tweets) if previous_tweets else None

    top_tweets = get_top_tweets(current_tweets, 3)
    bottom_tweets = get_bottom_tweets(current_tweets, 3)
    best_hours = get_best_posting_hours(current_tweets, 3)
    best_days = get_best_posting_days(current_tweets)

    print("[Analyzer] Запускаю AI-анализ...")
    ai = generate_ai_analysis(current_tweets, current_stats, previous_stats, top_tweets, bottom_tweets)

    return WeeklyReport(
        period_label=period_label,
        current=current_stats,
        previous=previous_stats,
        top_tweets=top_tweets,
        bottom_tweets=bottom_tweets,
        best_hours=best_hours,
        best_days=best_days,
        ai_analysis=ai.get("recommendations", ""),  # fallback
        ai_top_why=ai.get("top_why", []),
        ai_bottom_why=ai.get("bottom_why", []),
        ai_recommendations=ai.get("recommendations", ""),
        all_tweets=current_tweets,
    )
