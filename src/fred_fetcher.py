import os
import requests

_FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

# 지표 ID → (FRED series_id, transform)
# transform: yoy_monthly | level | level_daily | level_weekly | mom_abs_k | mom_pct | direct
_SERIES_MAP = {
    "cpi":                 ("CPIAUCSL",        "yoy_monthly"),
    "core_cpi":            ("CPILFESL",        "yoy_monthly"),
    "ppi":                 ("PPIFIS",          "yoy_monthly"),
    "pce":                 ("PCEPI",           "yoy_monthly"),
    "core_pce":            ("PCEPILFE",        "yoy_monthly"),
    "fed_rate":            ("FEDFUNDS",        "level"),
    "us_2y":               ("DGS2",            "level_daily"),
    "us_10y":              ("DGS10",           "level_daily"),
    "nonfarm_payrolls":    ("PAYEMS",          "mom_abs_k"),
    "unemployment":        ("UNRATE",          "level"),
    "avg_hourly_earnings": ("CES0500000003",   "yoy_monthly"),
    "jobless_claims":      ("ICSA",            "level_weekly"),
    "gdp":                 ("A191RL1Q225SBEA", "direct"),
    "retail_sales":        ("RSXFS",           "mom_pct"),
}


def _fetch_raw(series_id: str, limit: int) -> list[dict]:
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        return []
    try:
        r = requests.get(
            _FRED_BASE,
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit,
            },
            timeout=10,
        )
        r.raise_for_status()
        return [
            {"date": o["date"], "value": float(o["value"])}
            for o in r.json().get("observations", [])
            if o["value"] not in (".", "")
        ]
    except Exception:
        return []


def _yoy_monthly(series_id: str) -> tuple[str, str] | None:
    data = _fetch_raw(series_id, 14)
    if len(data) < 13:
        return None
    yoy = (data[0]["value"] - data[12]["value"]) / data[12]["value"] * 100
    return (data[0]["date"][:7], f"{yoy:+.2f}% (전년동월비)")


def _level(series_id: str) -> tuple[str, str] | None:
    data = _fetch_raw(series_id, 2)
    if not data:
        return None
    d = data[0]
    return (d["date"][:7], f"{d['value']:.2f}%")


def _level_daily(series_id: str) -> tuple[str, str] | None:
    data = _fetch_raw(series_id, 10)
    if not data:
        return None
    d = data[0]
    return (d["date"], f"{d['value']:.2f}%")


def _level_weekly(series_id: str) -> tuple[str, str] | None:
    data = _fetch_raw(series_id, 2)
    if not data:
        return None
    d = data[0]
    return (d["date"], f"{d['value']:,.0f}천건")


def _mom_abs_k(series_id: str) -> tuple[str, str] | None:
    data = _fetch_raw(series_id, 3)
    if len(data) < 2:
        return None
    change = data[0]["value"] - data[1]["value"]
    return (data[0]["date"][:7], f"{change:+,.0f}천명 (전월비)")


def _mom_pct(series_id: str) -> tuple[str, str] | None:
    data = _fetch_raw(series_id, 3)
    if len(data) < 2:
        return None
    if data[1]["value"] == 0:
        return None
    mom = (data[0]["value"] - data[1]["value"]) / data[1]["value"] * 100
    return (data[0]["date"][:7], f"{mom:+.2f}% (전월비)")


def _direct(series_id: str) -> tuple[str, str] | None:
    data = _fetch_raw(series_id, 2)
    if not data:
        return None
    d = data[0]
    return (d["date"][:7], f"{d['value']:+.1f}% (연율)")


def _level_pct_yoy(series_id: str) -> tuple[str, str] | None:
    """이미 YoY % 값인 시리즈 (한국 CPI 등)"""
    data = _fetch_raw(series_id, 2)
    if not data:
        return None
    d = data[0]
    return (d["date"][:7], f"{d['value']:+.2f}% (전년동월비)")


def _level_krw(series_id: str) -> tuple[str, str] | None:
    """원/달러 환율 (KRW per USD)"""
    data = _fetch_raw(series_id, 10)
    if not data:
        return None
    d = data[0]
    return (d["date"], f"{d['value']:,.2f}원")


_TRANSFORMS = {
    "yoy_monthly":   _yoy_monthly,
    "level":         _level,
    "level_daily":   _level_daily,
    "level_weekly":  _level_weekly,
    "level_pct_yoy": _level_pct_yoy,
    "level_krw":     _level_krw,
    "mom_abs_k":     _mom_abs_k,
    "mom_pct":       _mom_pct,
    "direct":        _direct,
}


# 한국 지표 ID → (FRED series_id, transform)
_KR_SERIES_MAP = {
    "kr_cpi":   ("KORCPIALLMINMEI", "yoy_monthly"),  # 인덱스(2015=100) → YoY 계산
    "bok_rate": ("IRSTCI01KRM156N", "level"),         # 한국 중앙은행 단기금리
    "usdkrw":   ("DEXKOUS",        "level_krw"),
}


def _build_fred_table(series_map: dict, indicators: list[dict], note: str) -> str:
    rows = []
    for ind in indicators:
        ind_id = ind.get("id", "")
        if ind_id not in series_map:
            continue
        series_id, transform = series_map[ind_id]
        fn = _TRANSFORMS.get(transform)
        if not fn:
            continue
        result = fn(series_id)
        if result:
            date_str, value_str = result
            rows.append(f"| {ind['label']} | {date_str} | {value_str} |")

    if not rows:
        return ""

    lines = [
        "## 📡 FRED 실시간 데이터",
        "아래는 FRED API에서 가져온 실제 경제 지표입니다. 이 수치를 분석의 핵심 기초로 활용하세요.",
        "",
        "| 지표 | 기준일 | 실제값 |",
        "|------|--------|--------|",
        *rows,
        "",
        f"> ⚠️ {note}",
    ]
    return "\n".join(lines)


def fetch_us_macro_data(indicators: list[dict]) -> str:
    if not os.getenv("FRED_API_KEY"):
        return ""
    return _build_fred_table(
        _SERIES_MAP, indicators,
        "ISM PMI, DXY, VIX 등 FRED 미지원 지표는 학습 데이터 기반 추론을 활용하세요."
    )


def fetch_kr_macro_data(indicators: list[dict]) -> str:
    if not os.getenv("FRED_API_KEY"):
        return ""
    return _build_fred_table(
        _KR_SERIES_MAP, indicators,
        "반도체 수출, 외국인 수급 등 FRED 미지원 지표는 학습 데이터 기반 추론을 활용하세요."
    )


def fetch_macro_data(country_label: str, indicators: list[dict]) -> str:
    """국가에 따라 적절한 FRED fetcher를 호출한다."""
    if country_label == "미국":
        return fetch_us_macro_data(indicators)
    if country_label == "한국":
        return fetch_kr_macro_data(indicators)
    return ""
