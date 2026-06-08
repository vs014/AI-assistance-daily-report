import os
import json
import yaml
from pathlib import Path
from datetime import date
from dotenv import load_dotenv
from openai import OpenAI
from src.topic_manager import load_topics, get_selected_topics
from src.storage import get_news_cache, set_news_cache

load_dotenv()

_BASE = Path(__file__).parent.parent
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SEARCH_MODEL = os.getenv("SEARCH_MODEL", "gpt-5.4-mini")


def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY가 설정되지 않았습니다.")
    return OpenAI(api_key=api_key)


def _load_trusted_domains() -> list[str]:
    """config/sources.yaml에서 trusted_free 도메인 목록을 로드한다."""
    try:
        sources_path = _BASE / "config" / "sources.yaml"
        with open(sources_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        trusted = data.get("trusted_free", {})
        domains = []
        for section in trusted.values():
            if isinstance(section, list):
                domains += [s["domain"] for s in section]
        return domains
    except Exception as e:
        print(f"신뢰 도메인 로드 실패: {e}")
        return []


def _build_cache_key(topic_labels: list[str]) -> str:
    sorted_ids = "_".join(sorted(t["id"] for t in get_selected_topics(topic_labels)))
    return f"news_{sorted_ids}_{date.today().isoformat()}"


def _build_search_prompt(topic: dict, monthly_context: str = "") -> str:
    today = date.today().isoformat()
    keywords = ", ".join(topic.get("keywords", [])[:5])

    trusted_domains = _load_trusted_domains()
    trusted_str = ", ".join(trusted_domains) if trusted_domains else ""

    sources_instruction = f"""
반드시 다음 신뢰할 수 있는 뉴스 사이트의 기사만 선별해주세요:
{trusted_str}""" if trusted_str else ""

    context_section = ""
    if monthly_context:
        context_section = f"""
[지난달 분석 컨텍스트]
{monthly_context}

위 지난달 데이터를 참고하여 오늘 기사에서 아래를 파악해주세요:
- 지난달 대비 변화된 내용
- 새롭게 등장한 이슈
- 계속 주목해야 할 사항
"""

    return f"""오늘은 {today}입니다. {today} 기준 최신 뉴스를 검색해주세요.
{context_section}
{topic['label']} 분야의 최근 24~48시간 이내 뉴스를 검색해주세요.
키워드: {keywords}
{sources_instruction}

다음 JSON 배열 형식으로 정확히 반환해주세요 (다른 텍스트는 출력하지 말고 JSON만):
[
  {{
    "title": "기사 제목",
    "summary": "핵심 내용 2~3줄 (지난달 대비 변화가 있다면 언급)",
    "url": "https://example.com/article",
    "source": "뉴스 출처명",
    "published_date": "YYYY-MM-DD",
    "change_from_last_month": "변화없음 | 새로운이슈 | 상황변화 | 주목필요"
  }}
]
핵심 기사 3~5개만 선별하여 반환해주세요."""


def _validate_article(article: dict, trusted_domains: list[str]) -> tuple[bool, str]:
    """기사 유효성 검사. (is_valid, warning_msg)를 반환."""
    title = article.get("title", "").strip()
    url = article.get("url", "").strip()
    source = article.get("source", "").strip()
    published_date = article.get("published_date", "").strip()

    if not title:
        return False, "제목 없음"
    if not url or url == "#":
        return False, "URL 누락/유효하지 않음"
    if not source:
        return False, "출처 누락"
    if not published_date:
        return False, "발행일 누락"

    if trusted_domains:
        domain_found = False
        for domain in trusted_domains:
            if domain.lower() in url.lower():
                domain_found = True
                break
        if not domain_found:
            return True, f"신뢰 도메인 미포함: {url}"

    return True, ""


def search_news_for_topic(topic: dict, monthly_context: str = "") -> list[dict]:
    """단일 분야의 최신 뉴스를 웹 검색으로 수집."""
    try:
        client = _client()
        prompt = _build_search_prompt(topic, monthly_context)

        response = client.responses.create(
            model=SEARCH_MODEL,
            tools=[{"type": "web_search_preview"}],
            input=prompt,
        )

        # JSON 파싱
        result_text = response.output_text.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        result_text = result_text.strip()

        articles = json.loads(result_text)
        if not isinstance(articles, list):
            return []

        trusted_domains = _load_trusted_domains()
        validated_articles = []
        for article in articles:
            is_valid, warning = _validate_article(article, trusted_domains)
            if is_valid:
                validated_articles.append(article)
            elif warning:
                print(f"⚠️ {topic['label']} 기사 검증 경고: {warning}")

        return validated_articles
    except Exception as e:
        print(f"뉴스 검색 실패 ({topic['label']}): {e}")
        return []


def collect_all_news(topic_labels: list[str]) -> dict[str, list[dict]]:
    """선택된 모든 분야의 뉴스를 수집 (캐시 적중 시 캐시 사용)."""
    if not topic_labels:
        return {}

    cache_key = _build_cache_key(topic_labels)

    # 캐시 확인
    cached = get_news_cache(cache_key)
    if cached:
        return cached

    # 지난달 컨텍스트 로드
    from src.storage import load_monthly_context
    last_month = (date.today().replace(day=1) - __import__("datetime").timedelta(days=1)).strftime("%Y-%m")
    monthly_context = load_monthly_context(last_month)

    # 웹 검색 수행
    topics = get_selected_topics(topic_labels)
    result = {}

    for topic in topics:
        articles = search_news_for_topic(topic, monthly_context)
        result[topic["label"]] = articles

    # 캐시 저장
    set_news_cache(cache_key, result)

    return result


def extract_topics_from_query(query: str) -> list[dict]:
    """
    서술형 텍스트에서 뉴스 검색 카테고리들을 추출한다.
    반환: [{"id": str, "label": str, "keywords": list[str]}, ...]
    """
    import json as _json
    import re as _re

    prompt = f"""다음 경제 관심사 설명에서 뉴스 검색에 사용할 카테고리를 추출하세요.

입력: "{query}"

각 카테고리는 명확한 주제 단위로 분리하고, 검색에 유용한 키워드도 함께 추출하세요.

JSON 배열만 반환 (설명 없이):
[
  {{"label": "짧은 카테고리명(10자 이내)", "keywords": ["키워드1", "키워드2", "키워드3"]}},
  ...
]"""

    response = _client().chat.completions.create(
        model=MODEL,
        max_completion_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content.strip()
    raw = _re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
    items = _json.loads(raw)
    result = []
    for item in items:
        label = item.get("label", "").strip()
        if label:
            result.append({
                "id": f"custom_{label.replace(' ', '_').replace('/', '_')}",
                "label": label,
                "keywords": item.get("keywords", []),
            })
    return result


def generate_monthly_summary(archive: dict) -> str:
    """
    월간 아카이브 데이터를 AI로 요약.
    archive: {date_str: {topic: [articles]}}
    """
    topics_data: dict[str, list[dict]] = {}
    for day_articles in archive.values():
        for topic, articles in day_articles.items():
            if topic not in topics_data:
                topics_data[topic] = []
            topics_data[topic].extend(articles)

    summary_input = ""
    for topic, articles in topics_data.items():
        summary_input += f"\n### {topic}\n"
        for a in articles[:30]:
            summary_input += f"- {a.get('title', '')}: {str(a.get('summary', ''))[:100]}\n"

    prompt = f"""다음은 지난 한 달간 수집된 경제 뉴스 요약입니다.

{summary_input[:6000]}

위 내용을 바탕으로 분야별 핵심 정보를 아래 형식으로 정리해주세요:

[분야명]
- 주요 이슈: (2~3가지 핵심 이슈)
- 결론/트렌드: (1~2문장)
- 다음 달 주목 사항: (1~2가지)

투자 권유 표현은 금지합니다."""

    try:
        response = _client().chat.completions.create(
            model=MODEL,
            max_completion_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"월간 요약 생성 실패: {e}")
        return ""


def generate_daily_briefing(collected: dict[str, list[dict]]) -> str:
    """
    수집된 분야별 기사들을 바탕으로 오늘의 종합 뉴스 브리핑을 한 문단으로 생성.
    """
    if not collected or all(len(articles) == 0 for articles in collected.values()):
        return "검색된 뉴스가 없습니다."

    # 분야별 기사를 텍스트로 직렬화
    articles_text = []
    for topic_label, articles in collected.items():
        if articles:
            topic_summary = f"[{topic_label}]\n"
            for art in articles[:2]:  # 분야당 상위 2개만
                topic_summary += f"- {art.get('title', '')}: {art.get('summary', '')}\n"
            articles_text.append(topic_summary)

    input_text = "\n".join(articles_text)

    prompt = f"""다음은 오늘 수집된 다양한 분야의 뉴스와 기사 요약입니다:

{input_text}

위 뉴스들을 종합하여 오늘의 전체 시장/경제 동향을 한 문단(3~5문장)으로 정리해주세요.
투자 권유성 표현은 절대 금지하고, 객관적인 사실 기반의 분석만 포함해주세요.
시나리오와 체크포인트 형식으로 작성하되, 투자자 관점의 리스크/기회 요인을 간략히 언급해주세요."""

    try:
        client = _client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=300,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"브리핑 생성 실패: {e}")
        return "브리핑 생성에 실패했습니다."
