#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
매월 1일/15일에 GitHub Actions에서 실행되는 스크립트.
관심 기업들의 최근 이슈를 이메일로 발송한다.
"""
import os
import sys
import json
import smtplib
import io
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import date, timedelta
from pathlib import Path

# stdout 인코딩 설정
if sys.stdout.encoding is None or sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.company_storage import load_company_watchlist, load_company_report_config, load_company_cache
from src.news_searcher import search_news_for_topic
from src.html_exporter import markdown_to_html

_BASE = project_root


def _build_company_report_email(company_name: str, ticker: str, recent_issues: list[dict]) -> str:
    """기업 이슈 리포트를 HTML 이메일로 포맷팅."""
    today = date.today().isoformat()
    title = f"기업 리포트 — {company_name} ({ticker}) · {today}"

    # 마크다운으로 구성
    report_md = f"# {title}\n\n"
    report_md += f"**기업:** {company_name} ({ticker})\n\n"
    report_md += f"**기준일:** {today}\n\n"

    if recent_issues:
        report_md += "## 📰 최근 이슈 (최근 2주)\n\n"
        for i, issue in enumerate(recent_issues[:10], 1):
            report_md += f"{i}. **{issue.get('title', '제목 없음')}**\n"
            report_md += f"   - 출처: {issue.get('source', '미상')}\n"
            if issue.get('published_date'):
                report_md += f"   - 날짜: {issue.get('published_date')}\n"
            report_md += f"   - 요약: {issue.get('summary', '요약 없음')}\n"
            if issue.get('url'):
                report_md += f"   - 링크: {issue.get('url')}\n"
            report_md += "\n"
    else:
        report_md += "## 📰 최근 이슈\n\n"
        report_md += "최근 2주 이내 주요 이슈가 없습니다.\n\n"

    report_md += "---\n\n"
    report_md += "본 보고서는 개인 투자 학습 목적으로 작성되었으며 투자 권유가 아닙니다.\n"

    # HTML로 변환
    html = markdown_to_html(report_md, mermaid_code=None)

    # 한글 폰트 CSS 추가
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

    if '<head>' in html:
        html = html.replace('<head>', f'<head>{korean_font_css}')
    elif '<!DOCTYPE' in html:
        html = html.replace('>', f'><head>{korean_font_css}</head><body>', 1)
    else:
        html = korean_font_css + html

    return html


def _send_via_gmail(subject: str, html: str, recipient: str) -> None:
    """Gmail SMTP를 통해 이메일 발송."""
    email_user = os.getenv("EMAIL_USER")
    email_password = os.getenv("EMAIL_APP_PASSWORD")

    if not email_user or not email_password:
        raise EnvironmentError("EMAIL_USER 또는 EMAIL_APP_PASSWORD 환경변수 필요")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = email_user
    msg["To"] = recipient

    msg.attach(MIMEText(html, "html", "utf-8"))

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
    print("📧 기업 리포트 메일 발송 시작")
    print("=" * 60)

    # 설정 로드
    config = load_company_report_config()
    if not config.get("enabled"):
        print("⚠️ 기업 리포트 메일 발송이 비활성화되어 있습니다.")
        return

    watchlist = load_company_watchlist()
    if not watchlist:
        print("⚠️ 감시 중인 기업이 없습니다.")
        return

    recipients = config.get("recipient_emails", [])
    if not recipients:
        print("⚠️ 수신자 이메일이 설정되지 않았습니다.")
        return

    print(f"\n📍 설정:")
    print(f"  감시 기업: {len(watchlist)}개")
    print(f"  수신자: {', '.join(recipients)}")

    company_cache = load_company_cache()

    # 각 기업별 리포트 생성 및 발송
    total_sent = 0
    for company in watchlist:
        company_name = company.get("name", "미정")
        ticker = company.get("ticker", "UNKNOWN").upper()

        print(f"\n🔍 {company_name} ({ticker}) 이슈 수집 중...")

        # 캐시에서 기업 정보 로드
        cached_data = company_cache.get(ticker, {})
        if not cached_data:
            print(f"⚠️ {ticker} 캐시 데이터 없음 (기업 분석을 먼저 실행해주세요)")
            continue

        # 최근 2주 이내 이슈 검색
        try:
            # 기업 정보를 topic 형태로 변환
            topic = {
                "id": f"company_{ticker}",
                "label": company_name,
                "keywords": [company_name, ticker],
            }

            recent_issues = search_news_for_topic(topic)
            if recent_issues:
                print(f"  ✓ {len(recent_issues)}개 이슈 발견")
            else:
                print(f"  ℹ️ 최근 이슈 없음")

            # 이메일 생성
            html_report = _build_company_report_email(company_name, ticker, recent_issues)
            subject = f"[기업 리포트] {company_name} ({ticker}) · {date.today().isoformat()}"

            # 발송
            for recipient in recipients:
                try:
                    _send_via_gmail(subject, html_report, recipient)
                    total_sent += 1
                except Exception as e:
                    print(f"✗ {recipient} 발송 실패: {e}")

        except Exception as e:
            print(f"✗ {company_name} 처리 중 오류: {e}")

    print("\n" + "=" * 60)
    print(f"✓ 완료! ({total_sent}개 발송됨)")
    print("=" * 60)


if __name__ == "__main__":
    main()
