import markdown as md_lib
from datetime import date


_DISCLAIMER = (
    "⚠️ 본 보고서는 개인 투자 학습 목적으로 작성되었으며 투자 권유가 아닙니다."
)

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
  <style>
    body {{ font-family: 'Noto Sans KR', sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; line-height: 1.7; color: #222; }}
    h1 {{ border-bottom: 2px solid #2563eb; padding-bottom: 8px; color: #1e3a8a; }}
    h2 {{ color: #1d4ed8; margin-top: 2em; }}
    h3 {{ color: #2563eb; }}
    blockquote {{ border-left: 4px solid #93c5fd; padding-left: 12px; color: #555; }}
    .disclaimer {{ background: #fef9c3; border: 1px solid #fde047; border-radius: 6px; padding: 10px 16px; margin-bottom: 24px; font-size: 0.9em; color: #713f12; }}
    .mermaid {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin: 16px 0; overflow-x: auto; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 8px 12px; }}
    th {{ background: #dbeafe; }}
    code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }}
    pre {{ background: #f1f5f9; padding: 16px; border-radius: 8px; overflow-x: auto; }}
    .meta {{ color: #64748b; font-size: 0.85em; margin-bottom: 16px; }}
  </style>
</head>
<body>
  <div class="disclaimer">{disclaimer}</div>
  <p class="meta">생성일: {report_date}</p>
  {body}
  <script>mermaid.initialize({{ startOnLoad: true, theme: 'default' }});</script>
</body>
</html>
"""


def markdown_to_html(markdown_text: str, mermaid_code: str | None = None) -> str:
    """
    Markdown 보고서를 완성형 HTML로 변환한다.
    mermaid_code가 있으면 ## 5. 기업 관계도 섹션 아래에 삽입한다.
    """
    report_date = date.today().strftime("%Y년 %m월 %d일")
    title = f"데일리 경제 리포트 — {report_date}"

    # Mermaid 블록 삽입
    if mermaid_code:
        mermaid_section = f"\n## 5. 기업 관계도\n\n```mermaid\n{mermaid_code}\n```\n"
        if "## 5." not in markdown_text and "## 6." in markdown_text:
            markdown_text = markdown_text.replace("## 6.", mermaid_section + "\n## 6.")
        elif "## 5." not in markdown_text:
            markdown_text += mermaid_section

    # Markdown → HTML 변환
    body_html = md_lib.markdown(
        markdown_text,
        extensions=["tables", "fenced_code", "nl2br"],
    )

    # Mermaid 코드 블록을 <div class="mermaid">로 교체
    body_html = _replace_mermaid_blocks(body_html)

    return _HTML_TEMPLATE.format(
        title=title,
        disclaimer=_DISCLAIMER,
        report_date=report_date,
        body=body_html,
    )


def _replace_mermaid_blocks(html: str) -> str:
    """<code class="language-mermaid">...</code> 블록을 Mermaid div로 교체."""
    import re
    pattern = re.compile(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        re.DOTALL,
    )
    def replacer(m):
        code = m.group(1).strip()
        return f'<div class="mermaid">{code}</div>'
    return pattern.sub(replacer, html)
