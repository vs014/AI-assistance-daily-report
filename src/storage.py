import json
from pathlib import Path
from datetime import date

_BASE = Path(__file__).parent.parent
_REPORTS_MD = _BASE / "reports" / "markdown"
_REPORTS_HTML = _BASE / "reports" / "html"
_CACHE_FILE = _BASE / "data" / "article_cache.json"
_MACRO_CACHE_FILE = _BASE / "data" / "macro_cache.json"
_NEWS_CACHE_FILE = _BASE / "data" / "news_cache.json"


def _today() -> str:
    return date.today().isoformat()


# ── 캐시 ──────────────────────────────────────────────────────────────────────

def load_cache() -> dict:
    if _CACHE_FILE.exists():
        with open(_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def get_cached_article(url: str) -> dict | None:
    return load_cache().get(url)


def set_cached_article(url: str, article: dict) -> None:
    cache = load_cache()
    cache[url] = article
    save_cache(cache)


# ── Macro 분석 캐시 ────────────────────────────────────────────────────────────

def _load_macro_cache() -> dict:
    if _MACRO_CACHE_FILE.exists():
        with open(_MACRO_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_macro_cache(key: str) -> str | None:
    return _load_macro_cache().get(key)


def set_macro_cache(key: str, result: str) -> None:
    cache = _load_macro_cache()
    cache[key] = result
    _MACRO_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_MACRO_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def delete_macro_cache(key: str) -> None:
    cache = _load_macro_cache()
    if key in cache:
        del cache[key]
        with open(_MACRO_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)


# ── 뉴스 검색 캐시 ─────────────────────────────────────────────────────────────

def _load_news_cache() -> dict:
    if _NEWS_CACHE_FILE.exists():
        with open(_NEWS_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_news_cache(key: str) -> dict | None:
    return _load_news_cache().get(key)


def set_news_cache(key: str, result: dict) -> None:
    cache = _load_news_cache()
    cache[key] = result
    _NEWS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_NEWS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def delete_news_cache(key: str) -> None:
    cache = _load_news_cache()
    if key in cache:
        del cache[key]
        with open(_NEWS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)


# ── 파일 저장 ──────────────────────────────────────────────────────────────────

def save_markdown(content: str, filename: str | None = None) -> Path:
    _REPORTS_MD.mkdir(parents=True, exist_ok=True)
    name = filename or f"{_today()}_report.md"
    path = _REPORTS_MD / name
    path.write_text(content, encoding="utf-8")
    return path


def save_html(content: str, filename: str | None = None) -> Path:
    _REPORTS_HTML.mkdir(parents=True, exist_ok=True)
    name = filename or f"{_today()}_report.html"
    path = _REPORTS_HTML / name
    path.write_text(content, encoding="utf-8")
    return path


def save_macro_report(content: str, fmt: str = "html", filename: str | None = None) -> Path:
    folder = _BASE / "reports" / ("macro_html" if fmt == "html" else "macro_markdown")
    folder.mkdir(parents=True, exist_ok=True)
    ext = "html" if fmt == "html" else "md"
    name = filename or f"{_today()}_macro_report.{ext}"
    path = folder / name
    path.write_text(content, encoding="utf-8")
    return path


def list_reports(fmt: str = "html") -> list[Path]:
    folder = _REPORTS_HTML if fmt == "html" else _REPORTS_MD
    if not folder.exists():
        return []
    return sorted(folder.glob(f"*.{fmt}"), reverse=True)


# ── 일일 뉴스 메일 설정 ────────────────────────────────────────────────────────────

_DAILY_CONFIG_FILE = _BASE / "data" / "daily_config.json"


def save_daily_config(topics: list[str], emails: list[str]) -> None:
    """일일 뉴스 메일 설정을 저장한다."""
    _DAILY_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    config = {
        "topics": topics,
        "emails": emails,
        "updated_at": date.today().isoformat(),
    }
    with open(_DAILY_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_daily_config() -> dict:
    """일일 뉴스 메일 설정을 로드한다."""
    if _DAILY_CONFIG_FILE.exists():
        with open(_DAILY_CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}
