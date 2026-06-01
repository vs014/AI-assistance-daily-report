def wrap_mermaid_html(mermaid_code: str) -> str:
    """Mermaid 코드를 HTML div로 감싼다 (html_exporter에서 CDN 스크립트와 함께 사용)."""
    return f'<div class="mermaid">\n{mermaid_code}\n</div>'


def mermaid_to_markdown(mermaid_code: str) -> str:
    """Markdown 보고서용 코드 블록으로 감싼다."""
    return f"```mermaid\n{mermaid_code}\n```"
