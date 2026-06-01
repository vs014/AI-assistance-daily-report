import streamlit as st
from datetime import date

from src.topic_manager import get_topic_labels, format_topics_for_prompt
from src.html_exporter import markdown_to_html
from src.storage import (
    save_macro_report, list_reports,
    delete_macro_cache, delete_news_cache,
    save_daily_config, load_daily_config,
)
from src.news_searcher import collect_all_news, generate_daily_briefing
from src.macro_analyzer import (
    get_country_labels, get_categories_for_country,
    get_all_indicators_for_country,
    analyze_macro, parse_dashboard, generate_macro_mermaid,
    get_indicator_description,
)

st.set_page_config(
    page_title="개인 경제 AI 비서",
    page_icon="📈",
    layout="wide",
)

st.title("📈 개인 경제 AI 비서")
st.caption("기사 URL 기반 리포트 생성 · Macro 지표 대시보드 · 지표 사전")

# ── 사이드바 ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")

    all_topics = get_topic_labels()
    selected_topics = st.multiselect(
        "관심 분야 선택",
        options=all_topics,
        default=all_topics[:3],
        help="리포트 생성 및 Macro 분석에 반영됩니다.",
    )

    report_style = st.radio(
        "보고서 스타일",
        options=["보고서형", "블로그형"],
        index=0,
    )

    st.divider()
    st.subheader("📁 저장된 리포트")
    saved = list_reports("html")
    if saved:
        for p in saved[:5]:
            st.text(p.name)
    else:
        st.caption("저장된 리포트가 없습니다.")

    st.divider()
    st.subheader("📧 매일 뉴스 메일 설정")
    st.caption("관심 분야와 이메일을 저장하면 매일 오전 7시(KST)에 뉴스가 발송됩니다.")

    # 현재 저장된 설정 로드
    config = load_daily_config()
    current_emails = config.get("emails", [])

    # 이메일 목록 표시
    if current_emails:
        st.write("**📧 현재 수신자 목록:**")
        for i, email in enumerate(current_emails):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.text(f"{i+1}. {email}")
            with col2:
                if st.button("🗑️", key=f"remove_email_{i}"):
                    current_emails.pop(i)
                    save_daily_config(config.get("topics", []), current_emails)
                    st.rerun()

    # 새 이메일 추가
    st.write("**➕ 새 이메일 추가:**")
    new_email = st.text_input("이메일 주소", placeholder="your.email@gmail.com", key="new_email_input")

    col_add, col_clear = st.columns(2)
    with col_add:
        if st.button("➕ 이메일 추가", key="add_email_btn"):
            if not new_email:
                st.error("이메일을 입력해주세요.")
            elif "@" not in new_email:
                st.error("올바른 이메일 형식이 아닙니다.")
            elif new_email in current_emails:
                st.warning("이미 추가된 이메일입니다.")
            else:
                current_emails.append(new_email)
                save_daily_config(config.get("topics", []), current_emails)
                st.success(f"✓ {new_email} 추가됨")
                st.rerun()

    with col_clear:
        if st.button("🗑️ 모두 삭제", key="clear_all_emails"):
            save_daily_config(config.get("topics", []), [])
            st.warning("모든 이메일이 삭제되었습니다.")
            st.rerun()

    # 분야 선택
    st.divider()
    st.write("**분야 선택:**")
    daily_topics = st.multiselect(
        "매일 받을 분야",
        options=all_topics,
        default=config.get("topics", selected_topics),
        help="이 분야들의 뉴스를 매일 받게 됩니다.",
    )

    if st.button("💾 분야 저장", key="save_topics_btn"):
        if not daily_topics:
            st.error("분야를 하나 이상 선택해주세요.")
        else:
            save_daily_config(daily_topics, current_emails)
            st.success("✓ 분야 저장 완료!")

    # 현재 설정 요약
    if config:
        st.divider()
        st.caption(f"📌 분야: {', '.join(config['topics'])}")
        st.caption(f"📨 발송 대상: {len(config['emails'])}명" if config['emails'] else "📨 발송 대상: 0명")

# ── 탭 구성 (4개) ────────────────────────────────────────────────────────────
tab_generate, tab_macro, tab_dict, tab_preview = st.tabs([
    "📰 리포트 생성",
    "📊 Macro 대시보드",
    "📚 지표 사전",
    "🖥️ 미리보기",
])

# ════════════════════════════════════════════════════════════════════════════════
# 탭 1: 뉴스 자동 검색 (신규)
# ════════════════════════════════════════════════════════════════════════════════
with tab_generate:
    st.subheader("🔍 관심 분야 최신 뉴스 자동 검색")
    st.caption("관심 분야를 선택하면 AI가 최근 24시간 뉴스를 자동으로 검색합니다.")

    news_topics = st.multiselect(
        "검색할 분야 선택",
        options=all_topics,
        default=selected_topics,
        help="선택한 분야별로 각각 AI 웹 검색을 수행합니다.",
    )

    col_btn, col_cache = st.columns([3, 1])
    with col_btn:
        search_btn = st.button("🔍 뉴스 검색", type="primary", use_container_width=True)
    with col_cache:
        clear_cache_btn = st.button("🗑️ 캐시 초기화", key="clear_news_cache")

    if clear_cache_btn and news_topics:
        try:
            from src.news_searcher import _build_cache_key
            cache_key = _build_cache_key(news_topics)
            delete_news_cache(cache_key)
            st.session_state.pop("news_result", None)
            st.success("캐시가 초기화되었습니다. 다시 검색하세요.")
        except Exception as e:
            st.error(f"캐시 초기화 실패: {e}")

    if search_btn:
        if not news_topics:
            st.warning("분야를 하나 이상 선택해주세요.")
        else:
            progress = st.progress(0, text="뉴스 검색 중...")
            status_placeholder = st.empty()

            for i, label in enumerate(news_topics):
                progress.progress(i / len(news_topics), text=f"검색 중: {label}")
                status_placeholder.caption(f"({i+1}/{len(news_topics)})")

            with st.spinner("모든 분야의 뉴스를 수집 중..."):
                try:
                    result = collect_all_news(news_topics)
                    st.session_state["news_result"] = result
                    st.success("뉴스 검색 완료!")
                except Exception as e:
                    st.error(f"뉴스 검색 실패: {e}")
                    progress.progress(1.0, text="완료")
                    st.stop()

            with st.spinner("오늘의 뉴스 브리핑 생성 중..."):
                try:
                    briefing = generate_daily_briefing(result)
                    st.session_state["news_briefing"] = briefing
                except Exception as e:
                    st.warning(f"브리핑 생성 실패: {e}")
                    st.session_state["news_briefing"] = ""

            progress.progress(1.0, text="완료")

    # 결과 표시
    if "news_result" in st.session_state:
        st.divider()
        result = st.session_state["news_result"]

        if not result or all(len(articles) == 0 for articles in result.values()):
            st.info("검색된 뉴스가 없습니다.")
        else:
            # 오늘의 브리핑 표시
            if st.session_state.get("news_briefing"):
                st.markdown("### 💡 오늘의 뉴스 브리핑")
                st.info(st.session_state["news_briefing"])
                st.divider()

            # 분야별 기사 카드
            st.markdown("### 📰 분야별 주요 기사")
            for topic_label, articles in result.items():
                with st.expander(f"**{topic_label}** — {len(articles)}건", expanded=True):
                    if not articles:
                        st.caption("검색된 기사가 없습니다.")
                    else:
                        for i, art in enumerate(articles, 1):
                            st.markdown(f"{i}. **[{art.get('title', '제목 없음')}]({art.get('url', '#')})**")
                            st.caption(f"출처: {art.get('source', '출처 미상')}")
                            st.write(art.get('summary', '요약 없음'))
                            st.divider()

# ════════════════════════════════════════════════════════════════════════════════
# 탭 2: Macro 대시보드 (신규)
# ════════════════════════════════════════════════════════════════════════════════
with tab_macro:
    st.subheader("📊 Macro 경제 지표 대시보드")
    st.caption("국가와 카테고리를 선택하면 Claude가 웹에서 최신 지표를 검색·분석합니다.")

    col_country, col_period = st.columns([2, 1])
    with col_country:
        country_labels = get_country_labels()
        selected_country = st.selectbox(
            "분석 국가",
            options=country_labels,
            index=0,
            key="macro_country",
        )
    with col_period:
        selected_period = st.selectbox(
            "분석 기간",
            options=["최근 3개월", "최근 6개월", "최근 1년"],
            index=2,
            key="macro_period",
        )

    categories = get_categories_for_country(selected_country)
    selected_categories = st.multiselect(
        "분석 카테고리",
        options=categories,
        default=categories[:2] if len(categories) >= 2 else categories,
        key="macro_categories",
        help="분석할 지표 카테고리를 선택하세요.",
    )

    col_macro_btn, col_cache_btn = st.columns([3, 1])
    with col_macro_btn:
        macro_btn = st.button("🔎 Macro 분석 시작", type="primary", key="macro_btn", use_container_width=True)
    with col_cache_btn:
        clear_cache_btn = st.button("🗑️ 오늘 캐시 초기화", key="clear_macro_cache", use_container_width=True)

    if clear_cache_btn and selected_categories:
        from datetime import date as _date
        cache_key = f"{selected_country}_{'_'.join(sorted(selected_categories))}_{selected_period}_{_date.today().isoformat()}"
        delete_macro_cache(cache_key)
        st.session_state.pop("macro_analysis", None)
        st.session_state.pop("macro_dashboard", None)
        st.session_state.pop("macro_html", None)
        st.session_state.pop("macro_mermaid", None)
        st.success("캐시가 초기화되었습니다. 다시 분석을 실행하세요.")

    if macro_btn:
        if not selected_categories:
            st.warning("카테고리를 하나 이상 선택해주세요.")
        else:
            topics_str = format_topics_for_prompt(selected_topics) if selected_topics else "없음"

            # watchlist 로드
            try:
                import yaml
                from pathlib import Path
                wl_path = Path(__file__).parent / "data" / "watchlist.yaml"
                with open(wl_path, encoding="utf-8") as f:
                    wl_data = yaml.safe_load(f)
                stocks = [s["name"] for s in wl_data.get("watchlist", {}).get("stocks", [])]
                sectors = wl_data.get("watchlist", {}).get("sectors", [])
                watchlist_str = "관심 종목: " + ", ".join(stocks) + "\n관심 섹터: " + ", ".join(sectors)
            except Exception:
                watchlist_str = "없음"

            with st.spinner(f"Claude가 {selected_country} 경제 지표를 분석 중입니다... (약 30~60초 소요)"):
                try:
                    analysis, from_cache = analyze_macro(
                        country_label=selected_country,
                        category_labels=selected_categories,
                        period=selected_period,
                        topics=topics_str,
                        watchlist=watchlist_str,
                    )
                    dashboard_data = parse_dashboard(analysis)

                    if not from_cache:
                        with st.spinner("인과관계도 생성 중..."):
                            try:
                                macro_mermaid = generate_macro_mermaid(analysis)
                            except Exception:
                                macro_mermaid = None
                    else:
                        macro_mermaid = st.session_state.get("macro_mermaid")

                    html_content = markdown_to_html(analysis, macro_mermaid)

                    st.session_state["macro_analysis"] = analysis
                    st.session_state["macro_dashboard"] = dashboard_data
                    st.session_state["macro_html"] = html_content
                    st.session_state["macro_mermaid"] = macro_mermaid
                    st.session_state["macro_from_cache"] = from_cache

                    if from_cache:
                        st.info("오늘 분석 결과를 캐시에서 불러왔습니다. 새 분석을 원하면 '오늘 캐시 초기화' 버튼을 누르세요.")
                    else:
                        st.success("Macro 분석 완료!")
                except Exception as e:
                    st.error(f"분석 실패: {e}")

    # 결과 표시 (session_state 기반)
    if "macro_analysis" in st.session_state:
        st.divider()
        if st.session_state.get("macro_from_cache"):
            st.info("📦 캐시된 결과 표시 중 — '오늘 캐시 초기화' 후 재분석하면 최신 결과를 가져옵니다.")

        # 대시보드 요약 카드
        dashboard = st.session_state.get("macro_dashboard", {})
        if dashboard:
            st.subheader("📋 대시보드 요약")
            _CARD_COLORS = {
                "Risk-On": "🟢", "Risk-Off": "🔴", "중립": "🟡",
                "상승": "🔴", "하락": "🟢", "안정": "🟡",
                "강함": "🔴", "완화": "🟢",
                "강세": "🔴", "약세": "🟢",
                "긍정": "🟢", "부정": "🔴",
            }
            cards = list(dashboard.items())
            cols = st.columns(min(len(cards), 4))
            for i, (k, v) in enumerate(cards):
                icon = _CARD_COLORS.get(v.split("/")[0].strip(), "⚪")
                cols[i % 4].metric(label=k, value=f"{icon} {v}")

        st.divider()

        # 저장 버튼
        col_save, col_dl = st.columns(2)
        with col_save:
            if st.button("🌐 Macro 보고서 저장", key="save_macro"):
                path = save_macro_report(st.session_state["macro_html"], fmt="html")
                st.success(f"저장 완료: {path}")
        with col_dl:
            st.download_button(
                label="⬇️ Macro 보고서 다운로드",
                data=st.session_state["macro_html"].encode("utf-8"),
                file_name=f"{date.today().isoformat()}_macro_report.html",
                mime="text/html",
                key="dl_macro",
            )

        with st.expander("📄 분석 보고서 전문", expanded=True):
            st.markdown(st.session_state["macro_analysis"])

        if st.session_state.get("macro_mermaid"):
            with st.expander("🔗 Mermaid 인과관계도 코드"):
                st.code(st.session_state["macro_mermaid"], language="text")

# ════════════════════════════════════════════════════════════════════════════════
# 탭 3: 지표 사전 (신규)
# ════════════════════════════════════════════════════════════════════════════════
with tab_dict:
    st.subheader("📚 경제 지표 사전")
    st.caption("각 지표의 의미, 시장 영향, 투자 활용법을 확인하세요.")

    country_labels = get_country_labels()
    dict_country = st.radio(
        "국가 선택",
        options=country_labels,
        horizontal=True,
        key="dict_country",
    )

    all_indicators = get_all_indicators_for_country(dict_country)
    categories_in_country = list(dict.fromkeys(ind["category"] for ind in all_indicators))
    dict_category = st.selectbox(
        "카테고리 필터",
        options=["전체"] + categories_in_country,
        key="dict_category",
    )

    filtered = (
        all_indicators if dict_category == "전체"
        else [ind for ind in all_indicators if ind["category"] == dict_category]
    )

    st.divider()

    for ind in filtered:
        with st.expander(f"**{ind['label']}** — {ind['category']} · {ind.get('release_cycle', '')}"):
            col_l, col_r = st.columns([3, 1])
            with col_l:
                st.markdown(f"**설명:** {ind.get('description', '')}")
                st.markdown(f"**단위:** `{ind.get('unit', '-')}`")
            with col_r:
                st.markdown(f"**발표 주기:** {ind.get('release_cycle', '-')}")

            st.markdown("**📈 예상치 상회 시:**")
            st.info(ind.get("higher_than_expected", "-"))
            st.markdown("**📉 예상치 하회 시:**")
            st.success(ind.get("lower_than_expected", "-"))

            if ind.get("related_sectors"):
                st.markdown("**관련 섹터:** " + " · ".join(ind["related_sectors"]))

            # AI 상세 설명 (on-demand)
            btn_key = f"dict_ai_{ind['id']}"
            if st.button("🤖 AI 상세 설명 보기", key=btn_key):
                with st.spinner("AI 설명 생성 중..."):
                    try:
                        desc = get_indicator_description(ind)
                        st.session_state[f"dict_desc_{ind['id']}"] = desc
                    except Exception as e:
                        st.error(f"설명 생성 실패: {e}")

            if f"dict_desc_{ind['id']}" in st.session_state:
                st.markdown(st.session_state[f"dict_desc_{ind['id']}"])

# ════════════════════════════════════════════════════════════════════════════════
# 탭 4: 미리보기 (Macro 보고서만)
# ════════════════════════════════════════════════════════════════════════════════
with tab_preview:
    st.subheader("🖥️ Macro 보고서 미리보기")
    st.caption("Macro 대시보드 탭에서 분석한 보고서를 HTML로 미리볼 수 있습니다.")

    if "macro_html" in st.session_state:
        col_save, col_dl = st.columns(2)
        with col_save:
            if st.button("💾 HTML 파일로 저장", key="save_html_preview"):
                path = save_macro_report(st.session_state["macro_html"], fmt="html")
                st.success(f"저장 완료: {path}")
        with col_dl:
            st.download_button(
                label="⬇️ HTML 다운로드",
                data=st.session_state["macro_html"].encode("utf-8"),
                file_name=f"{date.today().isoformat()}_macro_report.html",
                mime="text/html",
                key="dl_preview",
            )

        st.components.v1.html(
            st.session_state["macro_html"],
            height=900,
            scrolling=True,
        )
    else:
        st.info("📊 Macro 대시보드 탭에서 먼저 분석을 실행해주세요.")
