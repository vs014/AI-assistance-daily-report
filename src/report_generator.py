import os
from pathlib import Path
from datetime import date
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_TOKENS = 4096


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")
    return OpenAI(api_key=api_key)


def summarize_article(url: str, title: str, text: str, topics: str) -> str:
    """단일 기사를 요약·분석한다."""
    prompt_template = _load_prompt("article_summary.md")
    prompt = prompt_template.format(url=url, title=title, text=text[:4000], topics=topics)

    response = _client().chat.completions.create(
        model=MODEL,
        max_completion_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def generate_mermaid(content: str) -> str:
    """기사 요약들을 바탕으로 Mermaid 관계도 코드를 생성한다."""
    prompt_template = _load_prompt("mermaid_generator.md")
    prompt = prompt_template.format(content=content[:3000])

    response = _client().chat.completions.create(
        model=MODEL,
        max_completion_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    return raw


def generate_full_report(
    articles: list[dict],
    article_summaries: list[str],
    topics: str,
    report_date: str | None = None,
) -> str:
    """전체 데일리 리포트 Markdown을 생성한다."""
    if report_date is None:
        report_date = date.today().isoformat()

    articles_text = ""
    for i, (art, summary) in enumerate(zip(articles, article_summaries), 1):
        articles_text += f"\n---\n### 기사 {i}: {art.get('title', '제목 없음')}\n출처: {art['url']}\n\n{summary}\n"

    prompt_template = _load_prompt("daily_report.md")
    prompt = prompt_template.format(
        date=report_date,
        topics=topics,
        articles=articles_text,
    )

    response = _client().chat.completions.create(
        model=MODEL,
        max_completion_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def test_connection() -> bool:
    """API 연결 테스트."""
    try:
        resp = _client().chat.completions.create(
            model=MODEL,
            max_completion_tokens=10,
            messages=[{"role": "user", "content": "ping"}],
        )
        print("OpenAI API 연결 성공:", resp.choices[0].message.content)
        return True
    except Exception as e:
        print("OpenAI API 연결 실패:", e)
        return False
