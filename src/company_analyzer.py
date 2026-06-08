import os
import json
from openai import OpenAI
from datetime import datetime

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY가 설정되지 않았습니다.")
        _client = OpenAI(api_key=api_key)
    return _client


def analyze_company(name_or_ticker: str) -> dict:
    """
    기업명 또는 티커로 기업을 분석하고 투자 판단용 평가서를 생성.

    반환값: {
        "company_name": str,
        "ticker": str,
        "market": str,
        "overview": str,
        "business": str,
        "financials": str,
        "management": str,
        "investment_points": str,
        "risks": str,
        "valuation": str,
        "latest_news": str,
        "summary": str,
        "retrieved_at": "YYYY-MM-DD HH:MM:SS",
        "data_date": "YYYY-MM-DD"
    }
    """
    prompt = f"""당신은 투자 분석가입니다. 기업명 또는 티커 "{name_or_ticker}"에 대해 최신 웹 검색을 기반으로 다음 정보를 수집하고 분석해주세요.

A4 1페이지 분량의 기업 평가서를 다음 형식으로 작성해주세요:

JSON 형식으로만 반환 (다른 텍스트 없음):
{{
  "company_name": "기업명",
  "ticker": "상장 티커",
  "market": "상장시장 (예: NASDAQ, KRX)",
  "overview": "기업명, 상장시장/티커, 주요 사업 영역, 설립 연도, 본사 위치, 대표자를 포함한 기업 개요 (3~4문장)",
  "business": "주요 제품/서비스, 시장점유율, 경쟁사, 산업 성장성, 시장 규모와 트렌드 (3~4문장)",
  "financials": "마크다운 표로 최근 3~5년 매출, 영업이익, 순이익, 성장률, 부채비율, ROE/ROA, 배당 정책을 보여주고 (1~2문장의 간단한 해석 추가). 표 형식: | 항목 | 2024 | 2023 | 2022 | ... | YoY 성장률 |",
  "management": "CEO/CFO 등 주요 경영진 이력, 주주 구성, 이사회 구조 (2~3문장)",
  "investment_points": "성장 동력, 신사업/혁신 전략, 주요 수주·파트너십, 장기 비전 (2~3문장)",
  "risks": "산업, 경영, 재무, 규제 관련 위험 요소와 대응 가능성 (2~3문장)",
  "valuation": "마크다운 표로 현재 주가, 52주 범위, PER, PBR, 배당 수익률을 보여주고 (1~2문장의 간단한 해석 추가). 표 형식: | 지표 | 값 | 설명 | 예) | 현재 주가 | $123.45 | 2026년 6월 기준 |",
  "latest_news": "최근 3개월 내 주요 뉴스와 최근 2주 이내 핵심 이슈 (2~3문장, 출처와 날짜 명시)",
  "summary": "강점, 약점, 전망, 투자 참고 사항을 1~2문장으로 요약 (투자 권유가 아닌 참고 의견)"
}}

주의사항:
- 현재 날짜를 기반으로 최신 정보를 검색해주세요.
- 모든 정보는 신뢰할 수 있는 출처(공시자료, 공식 웹사이트, 재무 데이터베이스)를 기반으로 하세요.
- 투자 권유성 표현("매수", "상승 확실")은 금지합니다.
- 확실하지 않은 정보는 "정보 확인 필요" 또는 "데이터 미보유"로 명시하세요.
"""

    try:
        client = _get_client()
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            tools=[{"type": "web_search_preview"}],
            input=prompt,
        )

        result_text = response.output_text.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        result_text = result_text.strip()

        company_data = json.loads(result_text)
        company_data["retrieved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        company_data["data_date"] = datetime.now().strftime("%Y-%m-%d")
        return company_data
    except Exception as e:
        print(f"기업 분석 실패 ({name_or_ticker}): {e}")
        return {}


def get_related_tags(company_data: dict, predefined_topics: list[dict], custom_topics: list[dict] = None) -> list[dict]:
    """
    기업 분석 데이터에서 관련 분야 태그를 추출.

    반환값: [
        {"id": "topic_id", "label": "분야명", "is_new": bool},
        ...
    ]
    """
    if not company_data:
        return []

    if custom_topics is None:
        custom_topics = []

    # 기존 분야 (기본 + 커스텀)
    all_existing_topics = predefined_topics + custom_topics
    existing_topic_info = [{"id": t["id"], "label": t["label"]} for t in all_existing_topics]

    prompt = f"""당신은 기업 분석 전문가입니다. 다음 기업 정보에서 관련된 투자 분야 태그를 추출해주세요.

기업 정보:
회사명: {company_data.get('company_name', '')}
주요 사업: {company_data.get('business', '')}
산업: {company_data.get('investment_points', '')}

다음은 기존 관심 분야 카테고리입니다 (기본 분야 + 커스텀 분야):
{json.dumps(existing_topic_info, ensure_ascii=False, indent=2)}

이 기업과 가장 관련된 기존 분야 ID를 최대 3개 추출해주세요.
기존 분야에 없는 새로운 분야가 있으면 제안해주세요.

**중요: 새로운 분야의 id와 label 작성 규칙:**
- id: 영어 소문자, 언더스코어 사용 (예: life_sciences, biotech_innovation)
- label: 반드시 한국어로만 작성 (예: 생명과학, 바이오기술 혁신)

JSON 배열 형식으로만 반환 (다른 텍스트 없음):
[
  {{"id": "existing_topic_id", "is_new": false}},
  {{"id": "new_topic_id", "label": "생명과학 (한국어만)", "is_new": true}}
]
"""

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=256,
        )

        result_text = response.choices[0].message.content.strip()
        result_text = result_text.replace("```json", "").replace("```", "").strip()
        tags = json.loads(result_text)
        return tags if isinstance(tags, list) else []
    except Exception as e:
        print(f"태그 추출 실패: {e}")
        return []


def generate_detailed_report(company_data: dict) -> dict:
    """
    기본 평가서를 바탕으로 섹션별 상세 보고서 생성.
    각 섹션은 단일 문단으로 확장 설명 제공.

    반환값: {
        "overview_detailed": str,
        "business_detailed": str,
        "financials_detailed": str,
        "management_detailed": str,
        "investment_detailed": str,
        "risks_detailed": str,
        "valuation_detailed": str,
        "news_detailed": str
    }
    """
    if not company_data:
        return {}

    # 각 섹션별로 개별 요청 (안정성 향상)
    sections = {
        "overview_detailed": ("기업 개요", company_data.get('overview', '')),
        "business_detailed": ("사업 현황", company_data.get('business', '')),
        "financials_detailed": ("재무 상황", company_data.get('financials', '')),
        "management_detailed": ("경영진/지배구조", company_data.get('management', '')),
        "investment_detailed": ("투자 포인트", company_data.get('investment_points', '')),
        "risks_detailed": ("리스크", company_data.get('risks', '')),
        "valuation_detailed": ("밸류에이션", company_data.get('valuation', '')),
        "news_detailed": ("최신 뉴스", company_data.get('latest_news', '')),
    }

    result = {}
    client = _get_client()

    for section_key, (section_name, section_content) in sections.items():
        if not section_content:
            result[section_key] = ""
            continue

        prompt = f"""당신은 투자 분석가입니다. 다음 정보를 한 문단(3~5문장)으로 더 자세히 설명해주세요.

기업명: {company_data.get('company_name', '')}
섹션: {section_name}

내용: {section_content}

한 문단으로 확장 설명한 텍스트만 반환 (마크다운이나 구조화된 형식 없음):"""

        try:
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=600,
            )

            detailed_text = response.choices[0].message.content.strip()
            result[section_key] = detailed_text

        except Exception as e:
            print(f"상세 보고서 '{section_name}' 생성 실패: {e}")
            result[section_key] = section_content  # fallback: 원문 반환

    return result
