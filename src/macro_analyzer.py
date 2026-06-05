import os
import re
from pathlib import Path
from datetime import date
import yaml
from dotenv import load_dotenv
from openai import OpenAI
from src.storage import get_macro_cache, set_macro_cache
from src.fred_fetcher import fetch_macro_data

load_dotenv()

_BASE = Path(__file__).parent.parent
_PROMPTS_DIR = _BASE / "prompts"
_CONFIG_DIR = _BASE / "config"
_INDICATORS_PATH = _CONFIG_DIR / "macro_indicators.yaml"
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SEARCH_MODEL = os.getenv("SEARCH_MODEL", "gpt-5.4-mini")

_indicators_cache: dict | None = None


# ── 설정 로드 ──────────────────────────────────────────────────────────────────

def load_indicators() -> dict:
    global _indicators_cache
    if _indicators_cache is None:
        with open(_INDICATORS_PATH, encoding="utf-8") as f:
            _indicators_cache = yaml.safe_load(f)
    return _indicators_cache


def get_countries() -> list[dict]:
    return load_indicators().get("countries", [])


def get_country_labels() -> list[str]:
    return [c["label"] for c in get_countries()]


def get_categories_for_country(country_label: str) -> list[str]:
    for c in get_countries():
        if c["label"] == country_label:
            return [cat["label"] for cat in c.get("categories", [])]
    return []


def get_indicators_for_selection(country_label: str, category_labels: list[str]) -> list[dict]:
    result = []
    for c in get_countries():
        if c["label"] != country_label:
            continue
        for cat in c.get("categories", []):
            if cat["label"] in category_labels:
                for ind in cat.get("indicators", []):
                    result.append({**ind, "category": cat["label"], "country": country_label})
    return result


def get_all_indicators_for_country(country_label: str) -> list[dict]:
    result = []
    for c in get_countries():
        if c["label"] != country_label:
            continue
        for cat in c.get("categories", []):
            for ind in cat.get("indicators", []):
                result.append({**ind, "category": cat["label"], "country": country_label})
    return result


# ── OpenAI 클라이언트 ──────────────────────────────────────────────────────────

def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY가 설정되지 않았습니다.")
    return OpenAI(api_key=api_key)


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


# ── GPT 웹 검색: FRED 검증 + 미지원 지표 수집 ─────────────────────────────────

_WEB_SEARCH_TARGETS = {
    "미국": {
        "경기":    ["ISM 제조업 PMI", "ISM 서비스업 PMI"],
        "금융시장": ["달러인덱스(DXY)", "VIX 공포지수"],
    },
    "한국": {
        "수출": ["한국 반도체 수출(최근 월)"],
        "수급": ["코스피 외국인 순매수(최근)"],
    },
    "중국": {
        "경기": ["중국 NBS 제조업 PMI", "Caixin 서비스업 PMI"],
        "물가": ["중국 CPI(전년동월비)", "중국 PPI(전년동월비)"],
        "무역": ["중국 수출(전년동월비)", "중국 수입(전년동월비)"],
    },
}


def _fetch_web_indicators(
    country_label: str,
    category_labels: list[str],
    fred_data: str,
) -> str:
    """
    GPT 웹 검색으로 두 가지 역할 수행:
    1. FRED 수치 검증 및 최신 시장 분위기 보완
    2. FRED 미지원 지표 (ISM PMI, VIX, DXY, 중국 지표 등) 실시간 수집
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return ""

    targets = []
    for cat, inds in _WEB_SEARCH_TARGETS.get(country_label, {}).items():
        if cat in category_labels:
            targets.extend(inds)

    fred_section = f"\n\n[FRED 수집 데이터]\n{fred_data}" if fred_data else ""
    targets_text = ", ".join(targets) if targets else "없음"

    query = f"""다음 질문에 한국어로 답변해주세요. (국가: {country_label})
{fred_section}

① FRED 데이터가 있다면, 위 수치들이 현재 최신값인지 확인하고 더 최근 수치가 있으면 알려주세요.
② 다음 지표들의 최신 실제 수치(날짜 포함)를 알려주세요: {targets_text}
③ 현재 {country_label} 시장의 최근 주요 이슈와 분위기(금리 기대, 환율 방향, 주요 이벤트)를 3~4줄로 요약해주세요.

수치는 반드시 숫자로 표기해주세요."""

    try:
        client = _client()
        response = client.responses.create(
            model=SEARCH_MODEL,
            tools=[{"type": "web_search_preview"}],
            input=query,
        )
        return "## 🌐 GPT 웹 검색 보완 데이터\n" + response.output_text
    except Exception:
        return ""


# ── Macro 분석 ─────────────────────────────────────────────────────────────────

def analyze_macro(
    country_label: str,
    category_labels: list[str],
    period: str,
    topics: str,
    watchlist: str,
) -> tuple[str, bool]:
    """
    선택된 국가·카테고리의 지표를 GPT로 분석한다.
    반환: (Markdown 형식의 분석 보고서, 캐시에서 로드 여부)
    """
    cache_key = f"{country_label}_{'_'.join(sorted(category_labels))}_{period}_{date.today().isoformat()}"
    cached = get_macro_cache(cache_key)
    if cached:
        return cached, True

    indicators = get_indicators_for_selection(country_label, category_labels)
    if not indicators:
        return "선택된 카테고리에 해당하는 지표가 없습니다.", False

    # 카테고리당 최대 3개 지표
    _seen_cats: dict[str, int] = {}
    trimmed = []
    for ind in indicators:
        cat = ind["category"]
        if _seen_cats.get(cat, 0) < 3:
            trimmed.append(ind)
            _seen_cats[cat] = _seen_cats.get(cat, 0) + 1

    indicators_text = ", ".join(f"{ind['label']}({ind.get('unit','')})" for ind in trimmed)

    # FRED 구조화 데이터
    fred_data = fetch_macro_data(country_label, trimmed)

    # GPT 웹 검색: FRED 검증 + 미지원 지표 + 시장 분위기
    web_data = _fetch_web_indicators(country_label, category_labels, fred_data)

    topics_short = topics[:300]
    watchlist_short = watchlist[:200]

    prompt_template = _load_prompt("macro_search.md")
    prompt = prompt_template.format(
        date=date.today().strftime("%Y년 %m월 %d일"),
        country=country_label,
        categories=", ".join(category_labels),
        period=period,
        topics=topics_short,
        watchlist=watchlist_short,
        indicators=indicators_text,
        fred_data=fred_data,
        web_data=web_data,
    )

    response = _client().chat.completions.create(
        model=MODEL,
        max_completion_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    result = response.choices[0].message.content
    set_macro_cache(cache_key, result)
    return result, False


# ── 대시보드 파싱 ──────────────────────────────────────────────────────────────

def parse_dashboard(analysis_text: str) -> dict:
    pattern = re.compile(r"\[DASHBOARD_START\](.*?)\[DASHBOARD_END\]", re.DOTALL)
    match = pattern.search(analysis_text)
    if not match:
        return {}

    dashboard = {}
    for line in match.group(1).strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            dashboard[key.strip()] = value.strip()
    return dashboard


# ── 지표 사전 ──────────────────────────────────────────────────────────────────

def get_indicator_description(indicator: dict) -> str:
    """개별 지표의 사전 설명을 GPT API로 생성한다."""
    prompt_template = _load_prompt("macro_dictionary.md")
    prompt = prompt_template.format(
        label=indicator.get("label", ""),
        country=indicator.get("country", ""),
        category=indicator.get("category", ""),
        release_cycle=indicator.get("release_cycle", ""),
        unit=indicator.get("unit", ""),
    )

    response = _client().chat.completions.create(
        model=MODEL,
        max_completion_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


# ── Mermaid 인과관계도 ─────────────────────────────────────────────────────────

def generate_macro_mermaid(analysis_text: str) -> str:
    from src.report_generator import generate_mermaid
    return generate_mermaid(analysis_text[:3000])
