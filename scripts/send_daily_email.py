#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
매일 오전 7시(KST)에 GitHub Actions에서 실행되는 스크립트.
data/daily_config.json을 읽어 뉴스를 수집하고 Gmail로 발송한다.
"""
import os
import sys
import json
import smtplib
import io

# stdout 인코딩 설정
if sys.stdout.encoding is None or sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import date, timedelta
from pathlib import Path

# 프로젝트 루트를 path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.news_searcher import collect_all_news, generate_daily_briefing, search_news_for_topic, generate_monthly_summary
from src.storage import (
    load_daily_config, load_custom_topics,
    save_to_monthly_archive, load_monthly_archive,
    save_monthly_context, cleanup_old_monthly_data,
)
from src.html_exporter import markdown_to_html

_BASE = project_root


def _build_email_html(briefing: str, collected: dict[str, list[dict]]) -> str:
    """브리핑과 기사를 HTML 이메일로 포맷팅."""
    today = date.today().isoformat()
    title = f"일일 경제 브리핑 — {today}"

    # 분야별 기사를 마크다운으로 변환
    articles_md = f"# {title}\n\n## 💡 오늘의 뉴스 브리핑\n\n{briefing}\n\n"
    articles_md += "## 📰 분야별 주요 기사\n\n"

    for topic_label, articles in collected.items():
        if articles:
            articles_md += f"### {topic_label} — {len(articles)}건\n\n"
            for i, art in enumerate(articles, 1):
                articles_md += f"{i}. **[{art.get('title', '제목 없음')}]({art.get('url', '#')})**\n"
                _date = art.get('published_date', '')
                _date_str = f" · {_date}" if _date else ""
                articles_md += f"   출처: {art.get('source', '출처 미상')}{_date_str}\n"
                articles_md += f"   {art.get('summary', '요약 없음')}\n\n"

    # HTML로 변환
    html = markdown_to_html(articles_md, mermaid_code=None)

    # 한글 폰트 CSS 추가 - Gmail/이메일 클라이언트에서 호환성 높음
    korean_font_css = """
    <style>
    @charset "UTF-8";

    * {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic", "맑은 고딕", "돋움", sans-serif !important;
    }

    html, body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic", "맑은 고딕", "돋움", sans-serif !important;
    }

    h1, h2, h3, h4, h5, h6, p, div, span, a, li, td, th {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic", "맑은 고딕", "돋움", sans-serif !important;
    }
    </style>
    """

    # <head> 태그 찾아서 CSS 주입
    if '<head>' in html:
        html = html.replace('<head>', f'<head>{korean_font_css}')
    elif '<!DOCTYPE' in html:
        html = html.replace('>', f'><head>{korean_font_css}</head><body>', 1)
    else:
        html = korean_font_css + html

    return html


def _build_pdf_from_html(html: str) -> bytes:
    """PDF 생성 (선택사항). 실패 시 빈 바이트 반환."""
    try:
        from weasyprint import HTML
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', encoding='utf-8', delete=False) as f:
            f.write(html)
            temp_html_path = f.name

        try:
            pdf_bytes = HTML(filename=temp_html_path).write_pdf()
            return pdf_bytes
        finally:
            try:
                os.unlink(temp_html_path)
            except:
                pass

    except Exception:
        return b""


def _send_via_gmail(html: str, pdf_bytes: bytes | None, recipient: str) -> None:
    """Gmail SMTP를 통해 이메일 발송."""
    email_user = os.getenv("EMAIL_USER")
    email_password = os.getenv("EMAIL_APP_PASSWORD")

    if not email_user or not email_password:
        raise EnvironmentError("EMAIL_USER 또는 EMAIL_APP_PASSWORD 환경변수 필요")

    today = date.today().isoformat()
    subject = f"[일일 경제 브리핑] {today}"

    # 이메일 구성
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = email_user
    msg["To"] = recipient

    # HTML 본문
    msg.attach(MIMEText(html, "html", "utf-8"))

    # PDF 첨부 (생성된 경우)
    if pdf_bytes:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= daily_briefing_{today}.pdf"
        )
        msg.attach(part)

    # 발송
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_user, email_password)
            server.sendmail(email_user, recipient, msg.as_string())
        print(f"✓ 메일 발송 성공: {recipient}")
    except Exception as e:
        print(f"✗ 메일 발송 실패: {e}")
        raise


def main():
    """메인 실행 함수."""
    print("=" * 60)
    print("📧 일일 뉴스 메일 발송 시작")
    print("=" * 60)

    # 설정 로드
    config = load_daily_config()
    topics = config.get("topics") or []
    custom_topic_ids = config.get("custom_topic_ids", [])
    recipients = config.get("emails", [])  # 여러 이메일 지원

    # 환경변수로 폴백
    if not topics and not custom_topic_ids:
        topics_str = os.getenv("DAILY_TOPICS", "")
        topics = [t.strip() for t in topics_str.split(",") if t.strip()]

    if not recipients:
        single_recipient = os.getenv("EMAIL_RECIPIENT")
        recipients = [single_recipient] if single_recipient else []

    if not topics and not custom_topic_ids:
        print("✗ 설정 오류: 분야 또는 이메일이 설정되지 않았습니다.")
        print(f"  topics: {topics}")
        print(f"  custom_topic_ids: {custom_topic_ids}")
        print(f"  recipients: {recipients}")
        return

    if not recipients:
        print("✗ 설정 오류: 수신자 이메일이 설정되지 않았습니다.")
        return

    # 커스텀 카테고리 로드
    all_custom = load_custom_topics()
    custom_for_email = [ct for ct in all_custom if ct["id"] in custom_topic_ids]

    print(f"\n📍 설정:")
    if topics:
        print(f"  기본 분야: {', '.join(topics)}")
    if custom_for_email:
        print(f"  커스텀 분야: {', '.join(ct['label'] for ct in custom_for_email)}")
    print(f"  수신자: {', '.join(recipients)} ({len(recipients)}명)")

    # 뉴스 수집
    print(f"\n🔍 뉴스 수집 중...")
    try:
        collected = collect_all_news(topics) if topics else {}
        for ct in custom_for_email:
            collected[ct["label"]] = search_news_for_topic(ct)
        total_articles = sum(len(arts) for arts in collected.values())
        print(f"  ✓ {total_articles}개 기사 수집")
        if total_articles == 0:
            print("  ⚠️ 경고: 수집된 기사가 없습니다!")
            print(f"     Topics: {topics}")
            print(f"     Custom topics: {[ct['label'] for ct in custom_for_email]}")
    except Exception as e:
        print(f"  ✗ 뉴스 수집 실패: {e}")
        import traceback
        traceback.print_exc()
        raise

    # 월간 아카이브 저장
    print(f"\n📁 월간 아카이브 저장 중...")
    save_to_monthly_archive(collected)
    print(f"  ✓ 아카이브 저장 완료")

    # 매달 1일: 지난달 요약 생성 + 오래된 데이터 정리
    today = date.today()
    if today.day == 1:
        last_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        print(f"\n📊 {last_month} 월간 요약 생성 중...")
        archive = load_monthly_archive(last_month)
        if archive:
            summary = generate_monthly_summary(archive)
            if summary:
                save_monthly_context(last_month, summary)
                print(f"  ✓ {last_month} 월간 요약 생성 완료")
            else:
                print(f"  ⚠️ 월간 요약 생성 실패")
        else:
            print(f"  ⚠️ {last_month} 아카이브 데이터 없음")
        cleanup_old_monthly_data()
        print(f"  ✓ 오래된 아카이브 정리 완료")

    # 브리핑 생성
    print(f"\n💭 브리핑 생성 중...")
    briefing = generate_daily_briefing(collected)
    print(f"  ✓ 브리핑 생성 완료")

    # HTML 이메일 생성
    print(f"\n🎨 이메일 포맷팅 중...")
    email_html = _build_email_html(briefing, collected)
    print(f"  ✓ HTML 생성 완료")

    # PDF 생성
    print(f"\n📄 PDF 생성 중...")
    pdf_bytes = _build_pdf_from_html(email_html)
    if pdf_bytes:
        print(f"  ✓ PDF 생성 완료 ({len(pdf_bytes)} bytes)")
    else:
        print(f"  ⚠️ PDF 생성 실패 (본문만 발송)")

    # 메일 발송 (모든 수신자에게)
    print(f"\n📧 메일 발송 중...")
    failed_count = 0
    for i, recipient in enumerate(recipients, 1):
        try:
            _send_via_gmail(email_html, pdf_bytes, recipient)
        except Exception as e:
            print(f"✗ {recipient} 발송 실패: {e}")
            failed_count += 1

    print("\n" + "=" * 60)
    if failed_count == 0:
        print(f"✓ 완료! ({len(recipients)}명에게 발송됨)")
    else:
        print(f"⚠️  {len(recipients) - failed_count}/{len(recipients)}명에게 발송됨 ({failed_count}명 실패)")
    print("=" * 60)


if __name__ == "__main__":
    main()
