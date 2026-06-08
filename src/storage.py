import json
import datetime
from pathlib import Path
from datetime import date

_BASE = Path(__file__).parent.parent
_REPORTS_MD = _BASE / "reports" / "markdown"
_REPORTS_HTML = _BASE / "reports" / "html"
_CACHE_FILE = _BASE / "data" / "article_cache.json"
_MACRO_CACHE_FILE = _BASE / "data" / "macro_cache.json"
_NEWS_CACHE_FILE = _BASE / "data" / "news_cache.json"
_CUSTOM_TOPICS_FILE = _BASE / "data" / "custom_topics.json"
_PREDEFINED_OVERRIDES_FILE = _BASE / "data" / "predefined_overrides.json"
_MONTHLY_ARCHIVE_DIR = _BASE / "data" / "monthly_archive"
_MONTHLY_CONTEXT_DIR = _BASE / "data" / "monthly_context"
_SELECTED_TOPICS_FILE = _BASE / "data" / "selected_topics.json"


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


def save_daily_config(
    topics: list[str],
    emails: list[str],
    custom_topic_ids: list[str] | None = None,
) -> None:
    """일일 뉴스 메일 설정을 저장한다."""
    _DAILY_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    config = {
        "topics": topics,
        "emails": emails,
        "custom_topic_ids": custom_topic_ids or [],
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


# ── 커스텀 카테고리 CRUD ───────────────────────────────────────────────────────

def load_custom_topics() -> list[dict]:
    """사용자가 추가한 커스텀 카테고리를 로드한다."""
    if _CUSTOM_TOPICS_FILE.exists():
        with open(_CUSTOM_TOPICS_FILE, encoding="utf-8") as f:
            return json.load(f).get("topics", [])
    return []


def save_custom_topics(topics: list[dict]) -> None:
    _CUSTOM_TOPICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_CUSTOM_TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump({"topics": topics}, f, ensure_ascii=False, indent=2)


def add_custom_topics(new_topics: list[dict]) -> None:
    """중복 없이 커스텀 카테고리를 추가한다."""
    existing = load_custom_topics()
    existing_labels = {t["label"] for t in existing}
    for t in new_topics:
        if t["label"] not in existing_labels:
            existing.append(t)
    save_custom_topics(existing)


def remove_custom_topic(label: str) -> None:
    """label에 해당하는 커스텀 카테고리를 삭제한다."""
    topics = [t for t in load_custom_topics() if t["label"] != label]
    save_custom_topics(topics)


# ── 기본 분야 표시 이름 오버라이드 + 숨김 ──────────────────────────────────────

def load_predefined_overrides() -> dict:
    """기본 분야 이름 오버라이드 {topic_id: display_label}."""
    if _PREDEFINED_OVERRIDES_FILE.exists():
        data = json.loads(_PREDEFINED_OVERRIDES_FILE.read_text(encoding="utf-8"))
        if "overrides" not in data:
            return data  # 구버전 flat 형식 호환
        return data.get("overrides", {})
    return {}


def load_hidden_predefined() -> list[str]:
    """숨긴 기본 분야 topic_id 목록."""
    if _PREDEFINED_OVERRIDES_FILE.exists():
        data = json.loads(_PREDEFINED_OVERRIDES_FILE.read_text(encoding="utf-8"))
        return data.get("hidden", [])
    return []


def _save_predefined_file(overrides: dict, hidden: list[str]) -> None:
    _PREDEFINED_OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PREDEFINED_OVERRIDES_FILE.write_text(
        json.dumps({"overrides": overrides, "hidden": hidden}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_predefined_override(topic_id: str, display_label: str) -> None:
    _save_predefined_file(
        {**load_predefined_overrides(), topic_id: display_label.strip()},
        load_hidden_predefined(),
    )


def delete_predefined_override(topic_id: str) -> None:
    overrides = load_predefined_overrides()
    overrides.pop(topic_id, None)
    _save_predefined_file(overrides, load_hidden_predefined())


def hide_predefined_topic(topic_id: str) -> None:
    hidden = load_hidden_predefined()
    if topic_id not in hidden:
        hidden.append(topic_id)
    _save_predefined_file(load_predefined_overrides(), hidden)


def unhide_predefined_topic(topic_id: str) -> None:
    hidden = [h for h in load_hidden_predefined() if h != topic_id]
    _save_predefined_file(load_predefined_overrides(), hidden)


def rename_custom_topic(old_label: str, new_label: str) -> None:
    """커스텀 카테고리 이름을 변경한다."""
    topics = load_custom_topics()
    for t in topics:
        if t["label"] == old_label:
            t["label"] = new_label.strip()
            t["id"] = f"custom_{new_label.strip().replace(' ', '_').replace('/', '_')}"
            break
    save_custom_topics(topics)


# ── 월간 아카이브 ──────────────────────────────────────────────────────────────

def save_to_monthly_archive(collected: dict[str, list[dict]]) -> None:
    """오늘 수집된 기사를 이번 달 아카이브에 누적 저장 (제목+요약+출처만)."""
    today = date.today().isoformat()
    month_key = today[:7]
    _MONTHLY_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    path = _MONTHLY_ARCHIVE_DIR / f"{month_key}.json"

    archive = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    archive[today] = {
        topic: [
            {
                "title": a.get("title", ""),
                "summary": a.get("summary", ""),
                "source": a.get("source", ""),
                "published_date": a.get("published_date", ""),
            }
            for a in articles
        ]
        for topic, articles in collected.items()
    }
    path.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")


def load_monthly_archive(year_month: str) -> dict:
    """YYYY-MM 형식으로 아카이브 로드."""
    path = _MONTHLY_ARCHIVE_DIR / f"{year_month}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


# ── 월간 컨텍스트 요약 ─────────────────────────────────────────────────────────

def save_monthly_context(year_month: str, summary: str) -> None:
    _MONTHLY_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    path = _MONTHLY_CONTEXT_DIR / f"{year_month}_summary.json"
    path.write_text(
        json.dumps({"month": year_month, "summary": summary}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_monthly_context(year_month: str) -> str:
    """지난달 요약 텍스트 반환. 없으면 빈 문자열."""
    path = _MONTHLY_CONTEXT_DIR / f"{year_month}_summary.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")).get("summary", "")
    return ""


def cleanup_old_monthly_data() -> None:
    """직전 달 아카이브만 유지하고 그 이전은 삭제한다."""
    today = date.today()
    keep_months = {
        today.strftime("%Y-%m"),
        (today.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m"),
    }
    if _MONTHLY_ARCHIVE_DIR.exists():
        for f in _MONTHLY_ARCHIVE_DIR.glob("*.json"):
            if f.stem not in keep_months:
                f.unlink()


def load_selected_topic_ids() -> list[str]:
    if _SELECTED_TOPICS_FILE.exists():
        return json.loads(_SELECTED_TOPICS_FILE.read_text(encoding="utf-8")).get("selected", [])
    return []


def save_selected_topic_ids(ids: list[str]) -> None:
    _SELECTED_TOPICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SELECTED_TOPICS_FILE.write_text(
        json.dumps({"selected": ids}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def push_config_to_github() -> bool:
    """daily_config.json을 GitHub에 자동으로 push한다."""
    import subprocess
    try:
        repo_path = _BASE
        # git add
        subprocess.run(
            ["git", "add", "data/daily_config.json"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        # git commit
        subprocess.run(
            ["git", "commit", "-m", "Update daily email configuration"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        # git push
        subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"GitHub push 실패: {e}")
        return False
    except Exception as e:
        print(f"예상치 못한 오류: {e}")
        return False
