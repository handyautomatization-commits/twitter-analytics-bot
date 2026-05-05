"""
scraper.py — Scraper для x.com аналитики

Перехватывает ответ ContentPostListQuery GraphQL API
на странице x.com/i/account_analytics (вкладка Content).
Не требует платного Twitter API.
"""

import json
import asyncio
import random
import re
import base64
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

from playwright.async_api import async_playwright, Page, Response

try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False


# ─── Модель данных ──────────────────────────────────────────────────────────

class TweetData:
    def __init__(
        self,
        tweet_id: str,
        text: str,
        posted_at: datetime,
        impressions: int,
        likes: int,
        retweets: int,
        replies: int,
        link_clicks: int,
        profile_clicks: int,
        engagements: int,
    ):
        self.tweet_id = tweet_id
        self.text = text
        self.posted_at = posted_at
        self.impressions = impressions
        self.likes = likes
        self.retweets = retweets
        self.replies = replies
        self.link_clicks = link_clicks
        self.profile_clicks = profile_clicks
        self.engagements = engagements

    @property
    def engagement_rate(self) -> float:
        if self.impressions == 0:
            return 0.0
        return round(self.engagements / self.impressions * 100, 2)

    def to_dict(self) -> dict:
        return {
            "tweet_id": self.tweet_id,
            "text": self.text,
            "posted_at": self.posted_at.isoformat(),
            "impressions": self.impressions,
            "likes": self.likes,
            "retweets": self.retweets,
            "replies": self.replies,
            "link_clicks": self.link_clicks,
            "profile_clicks": self.profile_clicks,
            "engagements": self.engagements,
            "engagement_rate": self.engagement_rate,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TweetData":
        return cls(
            tweet_id=d["tweet_id"],
            text=d["text"],
            posted_at=datetime.fromisoformat(d["posted_at"]),
            impressions=d.get("impressions", 0),
            likes=d.get("likes", 0),
            retweets=d.get("retweets", 0),
            replies=d.get("replies", 0),
            link_clicks=d.get("link_clicks", 0),
            profile_clicks=d.get("profile_clicks", 0),
            engagements=d.get("engagements", 0),
        )


# ─── Основной скрапер ───────────────────────────────────────────────────────

async def scrape_analytics(cookies_json: str) -> list[TweetData]:
    """
    Главная функция: загружает x.com/i/account_analytics с cookies,
    перехватывает ContentPostListQuery и возвращает твиты за 7 дней.
    """
    cookies = json.loads(cookies_json)
    post_list_responses: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
            ],
        )

        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )

        await context.add_cookies(_normalize_cookies(cookies))

        page = await context.new_page()

        if HAS_STEALTH:
            await stealth_async(page)

        # Перехватываем все graphql-запросы для диагностики
        async def handle_response(response: Response):
            url = response.url
            # Логируем ВСЕ graphql-запросы чтобы видеть что реально происходит
            if "/i/api/graphql/" in url or "/graphql/" in url:
                endpoint = url.split("/")[-1].split("?")[0]
                print(f"[Scraper] GraphQL: {endpoint} (status={response.status})")
            if "contentpostlistquery" not in url.lower():
                return
            try:
                content_type = response.headers.get("content-type", "")
            except Exception:
                content_type = ""
            if "json" not in content_type:
                return
            try:
                body = await response.json()
                print(f"[Scraper] Перехвачен ContentPostListQuery (status={response.status})")
                post_list_responses.append(body)
            except Exception as e:
                print(f"[Scraper] Ошибка чтения ContentPostListQuery: {e}")

        page.on("response", handle_response)

        # 1. Открываем страницу аналитики
        await page.goto("https://x.com/i/account_analytics", wait_until="domcontentloaded")
        await _human_delay(2, 4)

        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        current_url = page.url
        print(f"[Scraper] URL: {current_url}")
        print(f"[Scraper] Заголовок: {await page.title()}")

        if _is_login_page(current_url):
            await browser.close()
            raise RuntimeError(
                "COOKIES_EXPIRED: Не удалось войти в Analytics. "
                "Обнови cookies: экспортируй через Cookie-Editor и обнови секрет TWITTER_COOKIES."
            )

        # 2. Нажимаем вкладку "Content" — она триггерит ContentPostListQuery
        clicked = False
        try:
            # Пробуем найти по роли tab
            tab = page.get_by_role("tab", name=re.compile(r"Content", re.IGNORECASE))
            if await tab.count() > 0:
                await tab.first.click()
                clicked = True
                print("[Scraper] Нажата вкладка Content (role=tab)")
        except Exception:
            pass

        if not clicked:
            try:
                # Пробуем найти по тексту ссылки/кнопки
                link = page.get_by_role("link", name=re.compile(r"^Content$", re.IGNORECASE))
                if await link.count() > 0:
                    await link.first.click()
                    clicked = True
                    print("[Scraper] Нажата ссылка Content (role=link)")
            except Exception:
                pass

        if not clicked:
            try:
                # Последний вариант — любой элемент с текстом "Content"
                el = page.locator("text=Content").first
                await el.click()
                clicked = True
                print("[Scraper] Нажат элемент Content (text locator)")
            except Exception:
                print("[Scraper] Не удалось нажать вкладку Content — возможно уже активна")

        await _human_delay(2, 4)

        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # Скриншот для диагностики — сохраняем в data/debug_screenshot.png
        try:
            import os
            os.makedirs("data", exist_ok=True)
            await page.screenshot(path="data/debug_screenshot.png", full_page=False)
            print("[Scraper] Скриншот сохранён: data/debug_screenshot.png")
        except Exception as e:
            print(f"[Scraper] Скриншот не удался: {e}")

        # Логируем текущий URL после клика (мог поменяться)
        print(f"[Scraper] URL после клика: {page.url}")

        # 3. Ждём ещё немного — страница может догружать данные
        await _human_delay(5, 7)

        await browser.close()

    # 4. Парсим перехваченные данные
    if post_list_responses:
        tweets = _parse_content_post_list_query(post_list_responses[0])
        print(f"[Scraper] Распознано твитов (без реплаев): {len(tweets)}")
        filtered = _filter_last_7_days(tweets)
        if filtered:
            oldest = min(t.posted_at for t in filtered)
            newest = max(t.posted_at for t in filtered)
            print(f"[Scraper] Период после фильтрации: {oldest.date()} — {newest.date()}")
        print(f"[Scraper] После фильтра 7 дней: {len(filtered)} твитов")
        return filtered

    raise RuntimeError(
        "ContentPostListQuery не был перехвачен. "
        "Возможно, страница не загрузила вкладку Content. "
        "Попробуй обновить cookies или повтори запуск."
    )


# ─── Парсинг ContentPostListQuery ───────────────────────────────────────────

def _parse_content_post_list_query(body: dict) -> list[TweetData]:
    """
    Парсит ответ ContentPostListQuery.

    Структура:
      data.viewer_v2.user_results.result.tweets_results[].result:
        legacy.created_at        — дата ("Sat Jan 10 09:57:16 +0000 2026")
        legacy.full_text         — полный текст (с @mention для реплаев)
        legacy.display_text_range — [start, end] видимого текста
        organic_metrics_total[]  — [{metric_type, metric_value}, ...]
    """
    tweets = []
    try:
        user_result = (
            body
            .get("data", {})
            .get("viewer_v2", {})
            .get("user_results", {})
            .get("result", {})
        )
        tweets_results = user_result.get("tweets_results", [])
        print(f"[Scraper] Найдено элементов в tweets_results: {len(tweets_results)}")

        for item in tweets_results:
            result = item.get("result", {})
            if result.get("__typename") != "Tweet":
                continue

            legacy = result.get("legacy", {})

            # Пропускаем реплаи — проверяем двумя способами:
            # 1. Поле in_reply_to_status_id_str содержит ID оригинального поста
            if legacy.get("in_reply_to_status_id_str") or legacy.get("in_reply_to_screen_name"):
                continue
            # 2. display_text_range[0] > 0 → в начале скрытый @mention (признак реплая)
            display_range_check = legacy.get("display_text_range", [0])
            if display_range_check and display_range_check[0] > 0:
                continue

            # ID твита
            tweet_id = result.get("rest_id", "")
            if not tweet_id:
                # Декодируем base64 id: "VHdlZXQ6MTIz..." → "Tweet:123..." → "123..."
                raw_id = result.get("id", item.get("id", ""))
                try:
                    decoded = base64.b64decode(raw_id + "==").decode("utf-8", errors="ignore")
                    tweet_id = decoded.split(":")[-1]
                except Exception:
                    tweet_id = raw_id

            if not tweet_id:
                tweet_id = str(abs(hash(legacy.get("full_text", "") + legacy.get("created_at", ""))))

            # Текст — используем display_text_range чтобы убрать @mention из реплаев
            full_text = legacy.get("full_text", "")
            display_range = legacy.get("display_text_range", [])
            if len(display_range) == 2:
                text = full_text[display_range[0]:display_range[1]]
            else:
                text = full_text

            # Дата — Twitter format: "Sat Jan 10 09:57:16 +0000 2026"
            created_at_str = legacy.get("created_at", "")
            try:
                posted_at = datetime.strptime(created_at_str, "%a %b %d %H:%M:%S %z %Y")
            except Exception:
                try:
                    posted_at = parsedate_to_datetime(created_at_str)
                except Exception:
                    posted_at = datetime.now(timezone.utc)

            # Метрики из organic_metrics_total: [{metric_type: "Impressions", metric_value: 11}, ...]
            metrics: dict[str, int] = {}
            for m in result.get("organic_metrics_total", []):
                mtype = m.get("metric_type", "")
                mval = _safe_int(m.get("metric_value", 0))
                metrics[mtype] = mval

            impressions = metrics.get("Impressions", 0)
            likes = metrics.get("Likes", 0)
            retweets = metrics.get("Retweets", 0)
            replies = metrics.get("Replies", 0)
            link_clicks = metrics.get("UrlClicks", 0)
            profile_clicks = metrics.get("ProfileVisits", 0)
            engagements = metrics.get("Engagements", 0)

            if engagements == 0:
                engagements = likes + retweets + replies + link_clicks + profile_clicks

            tweets.append(TweetData(
                tweet_id=tweet_id,
                text=text[:280],
                posted_at=posted_at,
                impressions=impressions,
                likes=likes,
                retweets=retweets,
                replies=replies,
                link_clicks=link_clicks,
                profile_clicks=profile_clicks,
                engagements=engagements,
            ))

    except Exception as e:
        print(f"[Scraper] Ошибка парсинга: {e}")

    return tweets


# ─── Вспомогательные функции ────────────────────────────────────────────────

def _filter_last_7_days(tweets: list[TweetData]) -> list[TweetData]:
    """Оставляет только твиты за последние 7 дней."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    result = []
    for t in tweets:
        posted = t.posted_at
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        if posted >= cutoff:
            result.append(t)
    return result


async def _human_delay(min_sec: float, max_sec: float):
    """Случайная задержка для имитации человека."""
    await asyncio.sleep(random.uniform(min_sec, max_sec))


def _normalize_cookies(cookies: list[dict]) -> list[dict]:
    """
    Конвертирует cookies из формата Cookie-Editor/Chrome в формат Playwright.
    """
    SAME_SITE_MAP = {
        "no_restriction": "None",
        "lax": "Lax",
        "strict": "Strict",
        "unspecified": "Lax",
        "": "Lax",
    }
    ALLOWED_FIELDS = {"name", "value", "domain", "path", "expires", "httpOnly", "secure", "sameSite"}

    normalized = []
    for cookie in cookies:
        c: dict = {}
        for field in ALLOWED_FIELDS:
            if field in cookie:
                c[field] = cookie[field]

        raw_ss = str(cookie.get("sameSite", "")).lower()
        c["sameSite"] = SAME_SITE_MAP.get(raw_ss, "Lax")

        if "expirationDate" in cookie and "expires" not in c:
            c["expires"] = cookie["expirationDate"]

        normalized.append(c)
    return normalized


def _is_login_page(url: str) -> bool:
    return any(kw in url.lower() for kw in ["login", "signin", "sign_in", "auth"])


def _safe_int(value) -> int:
    try:
        return int(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return 0
