import json
from pathlib import Path
from datetime import datetime

_BASE = Path(__file__).parent.parent
_COMPANY_CACHE_FILE = _BASE / "data" / "company_cache.json"
_COMPANY_WATCHLIST_FILE = _BASE / "data" / "company_watchlist.json"


def _ensure_dir():
    """data 디렉토리 생성."""
    _BASE.joinpath("data").mkdir(parents=True, exist_ok=True)


def load_company_cache() -> dict:
    """기업 분석 캐시 로드. {ticker: {...company_data...}}"""
    _ensure_dir()
    if _COMPANY_CACHE_FILE.exists():
        try:
            return json.loads(_COMPANY_CACHE_FILE.read_text(encoding="utf-8"))
        except:
            return {}
    return {}


def save_company_cache(ticker: str, company_data: dict) -> None:
    """기업 분석 결과를 캐시에 저장."""
    _ensure_dir()
    cache = load_company_cache()
    cache[ticker] = company_data
    _COMPANY_CACHE_FILE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def delete_company_cache(ticker: str) -> None:
    """특정 기업 캐시 삭제."""
    cache = load_company_cache()
    if ticker in cache:
        del cache[ticker]
        _COMPANY_CACHE_FILE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def get_cached_company(ticker: str) -> dict | None:
    """캐시에서 기업 정보 조회."""
    cache = load_company_cache()
    return cache.get(ticker)


def load_company_watchlist() -> list[dict]:
    """
    기업 리포트 메일 대상 목록 로드.

    반환값: [
        {"name": "기업명", "ticker": "티커", "added_at": "YYYY-MM-DD"},
        ...
    ]
    """
    _ensure_dir()
    if _COMPANY_WATCHLIST_FILE.exists():
        try:
            data = json.loads(_COMPANY_WATCHLIST_FILE.read_text(encoding="utf-8"))
            return data.get("companies", [])
        except:
            return []
    return []


def save_company_watchlist(companies: list[dict]) -> None:
    """기업 리포트 메일 대상 목록 저장."""
    _ensure_dir()
    data = {"companies": companies, "updated_at": datetime.now().strftime("%Y-%m-%d")}
    _COMPANY_WATCHLIST_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_company_to_watchlist(name: str, ticker: str) -> None:
    """기업을 리포트 메일 대상에 추가."""
    companies = load_company_watchlist()
    if not any(c["ticker"].upper() == ticker.upper() for c in companies):
        companies.append({
            "name": name,
            "ticker": ticker.upper(),
            "added_at": datetime.now().strftime("%Y-%m-%d"),
        })
    save_company_watchlist(companies)


def remove_company_from_watchlist(ticker: str) -> None:
    """기업을 리포트 메일 대상에서 제거."""
    companies = load_company_watchlist()
    companies = [c for c in companies if c["ticker"].upper() != ticker.upper()]
    save_company_watchlist(companies)


def load_company_report_config() -> dict:
    """
    기업 리포트 메일 설정 로드.

    반환값: {
        "enabled": bool,
        "send_on_1st": bool,
        "send_on_15th": bool,
        "recipient_emails": list[str]
    }
    """
    from src.storage import load_daily_config
    config = load_daily_config()
    return config.get("company_report_config", {
        "enabled": False,
        "send_on_1st": True,
        "send_on_15th": True,
        "recipient_emails": []
    })


def save_company_report_config(config: dict) -> None:
    """기업 리포트 메일 설정 저장."""
    from src.storage import load_daily_config, save_daily_config
    daily_config = load_daily_config()
    daily_config["company_report_config"] = config
    save_daily_config(
        daily_config.get("topics", []),
        daily_config.get("emails", []),
        daily_config.get("custom_topic_ids", [])
    )
    # company_report_config도 함께 저장하기 위해 직접 저장
    from pathlib import Path
    _BASE = Path(__file__).parent.parent
    config_file = _BASE / "data" / "daily_config.json"
    current = json.loads(config_file.read_text(encoding="utf-8"))
    current["company_report_config"] = config
    config_file.write_text(
        json.dumps(current, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_detailed_report(ticker: str, detailed_report: dict) -> None:
    """상세 보고서를 기업 캐시에 저장."""
    _ensure_dir()
    cache = load_company_cache()
    if ticker in cache:
        cache[ticker]["detailed_report"] = detailed_report
        cache[ticker]["detailed_report_generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _COMPANY_CACHE_FILE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def load_detailed_report(ticker: str) -> dict | None:
    """캐시에서 상세 보고서 로드."""
    cache = load_company_cache()
    if ticker in cache and "detailed_report" in cache[ticker]:
        return cache[ticker]["detailed_report"]
    return None


def delete_detailed_report(ticker: str) -> None:
    """캐시에서 상세 보고서 삭제."""
    _ensure_dir()
    cache = load_company_cache()
    if ticker in cache and "detailed_report" in cache[ticker]:
        del cache[ticker]["detailed_report"]
        if "detailed_report_generated_at" in cache[ticker]:
            del cache[ticker]["detailed_report_generated_at"]
        _COMPANY_CACHE_FILE.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
