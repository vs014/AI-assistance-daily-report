# 개인 경제 AI 비서 — CLAUDE.md

## 프로젝트 목적
사용자가 기사 URL을 입력하면 투자자 관점의 데일리 경제 리포트(HTML/Markdown)를
자동 생성해주는 개인용 경제 리서치 보조 도구.

## 기술 스택
- Python 3.10+
- Streamlit (UI)
- Anthropic Claude API (claude-sonnet-4-6)
- trafilatura / newspaper3k / BeautifulSoup4 (기사 추출)
- Mermaid.js (관계도 시각화)
- 로컬 파일 저장 (HTML / Markdown)

## 금지사항
- API 키를 코드에 직접 작성하지 않는다 — 반드시 .env 파일 사용
- 유료 기사 원문 전체를 파일로 저장하지 않는다 — 출처 URL + AI 요약만 저장
- 기사 내용을 외부 서버에 자동 업로드하지 않는다
- 투자 권유성 표현("매수하라", "상승 확실") 사용 금지 — 시나리오/체크포인트 중심

## 코딩 규칙
- 모든 소스 파일은 src/ 하위에 위치
- 프롬프트 템플릿은 prompts/ 하위 .md 파일로 관리
- 설정값은 config/*.yaml 파일로 분리
- 환경변수 로드는 python-dotenv 사용
- 에러 발생 시 예외를 삼키지 않고 Streamlit st.error()로 표시

## 보고서 섹션 구조
1. 오늘의 핵심 요약
2. 시장 흐름 해석
3. 주요 기사 요약 (기사별)
4. 관심 분야별 분석
5. 기업 관계도 (Mermaid)
6. 투자자 관점 체크포인트
7. 오늘의 시장 자세 (1~2줄)

## 면책 문구 (모든 HTML 보고서에 포함)
"본 보고서는 개인 투자 학습 목적으로 작성되었으며 투자 권유가 아닙니다."
