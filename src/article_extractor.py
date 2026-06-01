import requests
from typing import Optional


def extract(url: str) -> dict:
    """
    URL에서 기사 본문을 추출한다.
    trafilatura → newspaper3k → BeautifulSoup 순서로 폴백.
    반환: {"title": str, "text": str, "url": str, "error": str|None}
    """
    result = {"title": "", "text": "", "url": url, "error": None}

    # 1차: trafilatura
    text, title = _try_trafilatura(url)
    if text:
        result["text"] = text
        result["title"] = title or ""
        return result

    # 2차: newspaper3k
    text, title = _try_newspaper(url)
    if text:
        result["text"] = text
        result["title"] = title or ""
        return result

    # 3차: BeautifulSoup
    text, title = _try_bs4(url)
    if text:
        result["text"] = text
        result["title"] = title or ""
        return result

    result["error"] = (
        "기사 본문을 추출할 수 없습니다. "
        "로그인이 필요한 기사이거나 접근이 제한된 페이지일 수 있습니다."
    )
    return result


def _try_trafilatura(url: str) -> tuple[Optional[str], Optional[str]]:
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None, None
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        # 제목 추출
        meta = trafilatura.extract_metadata(downloaded)
        title = meta.title if meta else None
        return text, title
    except Exception:
        return None, None


def _try_newspaper(url: str) -> tuple[Optional[str], Optional[str]]:
    try:
        from newspaper import Article
        article = Article(url, language="ko")
        article.download()
        article.parse()
        text = article.text.strip()
        title = article.title.strip()
        if len(text) < 100:
            return None, None
        return text, title
    except Exception:
        return None, None


def _try_bs4(url: str) -> tuple[Optional[str], Optional[str]]:
    try:
        from bs4 import BeautifulSoup
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # 제목
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # 본문: <article> → <main> → <body> 순서로 시도
        for tag in ["article", "main", "body"]:
            container = soup.find(tag)
            if container:
                for noise in container.find_all(["script", "style", "nav", "footer", "aside"]):
                    noise.decompose()
                text = container.get_text(separator="\n", strip=True)
                if len(text) >= 100:
                    return text[:8000], title  # 너무 긴 본문 제한
        return None, None
    except Exception:
        return None, None
