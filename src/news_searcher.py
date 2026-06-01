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
        domains = [s["domain"] for s in trusted.get("global", [])]
        domains += [s["domain"] for s in trusted.get("korean", [])]
        return domains
    except Exception as e:
        print(f"신뢰 도메인 로드 실패: {e}")
        return []


def _build_cache_key(topic_labels: list[str]) -> str:
    sorted_ids = "_".join(sorted(t["id"] for t in get_selected_topics(topic_labels)))
    return f"news_{sorted_ids}_{date.today().isoformat()}"


def _build_search_prompt(topic: dict) -> str:
    today = date.today().isoformat()
    keywords = ", ".join(topic.get("keywords", [])[:5])

    # 신뢰 도메인 목록 로드
    trusted_domains = _load_trusted_domains()
    trusted_str = ", ".join(trusted_domains) if trusted_domains else ""

    sources_instruction = f"""
반드시 다음 신뢰할 수 있는 뉴스 사이트의 기사만 선별해주세요:
{trusted_str}""" if trusted_str else ""

    return f"""{topic['label']} 분야의 최근 24시간 이내 최신 뉴스를 검색해주세요.
키워드: {keywords}
오늘 날짜: {today}
{sources_instruction}

다음 JSON 배열 형식으로 정확히 반환해주세요 (다른 텍스트는 출력하지 말고 JSON만):
[
  {{
    "title": "기사 제목",
    "summary": "핵심 내용 2~3줄",
    "url": "https://example.com/article",
    "source": "뉴스 출처명"
  }}
]
핵심 기사 3~5개만 선별하여 반환해주세요."""


def search_news_for_topic(topic: dict) -> list[dict]:
    """단일 분야의 최신 뉴스를 웹 검색으로 수집."""
    try:
        client = _client()
        prompt = _build_search_prompt(topic)

        response = client.responses.create(
            model=MODEL,
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
        return articles if isinstance(articles, list) else []
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

    # 웹 검색 수행
    topics = get_selected_topics(topic_labels)
    result = {}

    for topic in topics:
        articles = search_news_for_topic(topic)
        result[topic["label"]] = articles

    # 캐시 저장
    set_news_cache(cache_key, result)

    return result


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
