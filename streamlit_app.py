import streamlit as st
import pandas as pd
from scholarly import scholarly
import io
from thefuzz import process, fuzz
import os

# --- 1. 페이지 설정 및 상수 정의 ---
st.set_page_config(
    page_title="논문 검색 다운로더",
    page_icon="📚",
    layout="wide",
)

MAX_RESULTS_LIMIT = 200
MATCH_SCORE_THRESHOLD = 85

TOP_JOURNALS = {
    "Nature", "Science", "Cell", "The Lancet", "New England Journal of Medicine",
    "CA - A Cancer Journal for Clinicians", "Nature Reviews Molecular Cell Biology",
    "Nature Medicine", "The Lancet Neurology", "JAMA - Journal of the American Medical Association"
}

# --- 2. 핵심 함수 (데이터 로딩, 매칭, 스타일링) ---
@st.cache_data
def load_journal_db(file_path='journal_if_data.csv'):
    # ... (이전과 동일, 변경 없음)
    if not os.path.exists(file_path): return None, None
    try:
        df = pd.read_csv(file_path)
        df.dropna(subset=['FullName', 'ImpactFactor'], inplace=True)
        return df, df['FullName'].tolist()
    except Exception as e:
        st.error(f"데이터 파일({file_path}) 로드 오류: {e}")
        return None, None

@st.cache_data
def get_journal_info(venue, db_df, journal_names_list):
    # ... (이전과 동일, 변경 없음)
    if not venue or db_df is None or not journal_names_list:
        return "N/A", "N/A", 0
    match, score = process.extractOne(venue, journal_names_list, scorer=fuzz.token_sort_ratio)
    if score >= MATCH_SCORE_THRESHOLD:
        sjr_value = db_df.loc[db_df['FullName'] == match, 'ImpactFactor'].iloc[0]
        return f"{sjr_value:.3f}", match, score
    else:
        return "N/A", "매칭 실패", score

def classify_sjr(sjr_score_str):
    # ... (이전과 동일, 변경 없음)
    if sjr_score_str == "N/A": return "N/A"
    try:
        score = float(sjr_score_str)
        if score >= 1.0: return "우수"
        elif 0.5 <= score < 1.0: return "양호"
        elif 0.2 <= score < 0.5: return "보통"
        else: return "하위"
    except (ValueError, TypeError): return "N/A"

def color_sjr_score(val):
    # ... (이전과 동일, 변경 없음)
    try:
        score = float(val)
        if score >= 1.0: color = 'green'
        elif 0.5 <= score < 1.0: color = 'blue'
        elif 0.2 <= score < 0.5: color = 'orange'
        else: color = 'red'
        return f'color: {color}; font-weight: bold;'
    except (ValueError, TypeError): return 'color: grey;'

@st.cache_data
def convert_df_to_csv(df: pd.DataFrame):
    return df.to_csv(index=False).encode('utf-8-sig')


# --- 3. UI 본문 구성 ---
st.title("📚 논문 검색 및 정보 다운로더")
st.markdown(f"Google Scholar에서 논문을 검색하고, SJR 지표를 함께 조회합니다. (최대 **{MAX_RESULTS_LIMIT}개**까지 표시)")

db_df, journal_names = load_journal_db()
if db_df is None:
    st.error("⚠️ `journal_if_data.csv` 파일을 찾을 수 없습니다. `scrape_if_data.py`를 먼저 실행해주세요.")
else:
    st.success(f"✅ 총 {len(db_df):,}개의 저널 정보가 담긴 데이터베이스를 성공적으로 로드했습니다.")
    
    with st.expander("💡 결과 테이블 해석 가이드 보기"):
        st.markdown(f"""
        - **🏆 Top 저널**: Nature, Science 등 세계 최상위 저널을 특별히 표시합니다.
        - **매칭 점수**: Google Scholar의 축약된 저널명과 DB의 전체 저널명 간의 유사도입니다.
        - **{MATCH_SCORE_THRESHOLD}% 이상**일 경우에만 SJR 점수를 표시하여 정확도를 높였습니다.
        """)

    with st.form(key='search_form'):
        st.subheader("🔍 검색 조건 입력")
        col1, col2 = st.columns(2)
        with col1:
            author = st.text_input("저자 (선택 사항)", placeholder="예: Hinton G")
        with col2:
            keyword = st.text_input("키워드 (선택 사항)", placeholder="예: deep learning")
        
        # ⭐️ 새로운 기능: High Impact 저널 필터링 체크박스
        only_high_impact = st.checkbox("High Impact 저널만 찾기 (DB에서 매칭되는 저널만 표시)", value=True)
        
        submit_button = st.form_submit_button(label='검색 시작')

    if submit_button and (author or keyword):
        query_parts = []
        if keyword: query_parts.append(keyword)
        if author: query_parts.append(f'author:"{author}"')
        query = " ".join(query_parts)

        with st.spinner(f"'{query}' 조건으로 논문을 검색 중입니다..."):
            try:
                search_query = scholarly.search_pubs(query)
                results = []
                for i, pub in enumerate(search_query):
                    if i >= MAX_RESULTS_LIMIT:
                        st.info(f"검색 결과가 많아 최대 {MAX_RESULTS_LIMIT}개까지만 표시합니다.")
                        break
                    
                    bib = pub.get('bib', {})
                    venue = bib.get('venue', 'N/A')
                    sjr_score, matched_name, match_score = get_journal_info(venue, db_df, journal_names)
                    
                    # ⭐️ 새로운 기능: 필터링 로직
                    # 체크박스가 선택되었고, SJR 점수를 찾지 못했다면(매칭 실패) 건너뛴다.
                    if only_high_impact and sjr_score == "N/A":
                        continue
                    
                    top_journal_icon = "🏆" if matched_name in TOP_JOURNALS else ""
                    
                    results.append({
                        "Top 저널": top_journal_icon,
                        "제목 (Title)": bib.get('title', 'N/A'),
                        "저자 (Authors)": ", ".join(bib.get('author', ['N/A'])),
                        "연도 (Year)": bib.get('pub_year', 'N/A'),
                        "검색된 저널명 (축약)": venue,
                        "매칭된 저널명 (전체)": matched_name,
                        "매칭 점수 (%)": match_score,
                        "저널 SJR": sjr_score,
                        "피인용 수": pub.get('num_citations', 0),
                        "논문 링크": pub.get('pub_url', '#'),
                    })

                if not results:
                    st.warning("조건에 맞는 논문이 없습니다. (필터를 해제하거나 다른 키워드를 시도해보세요)")
                else:
                    # ⭐️ 새로운 기능: 필터링 여부에 따라 동적으로 제목 변경
                    subheader_text = f"📊 검색 결과 ({len(results)}개)"
                    if only_high_impact:
                        subheader_text += " - High Impact 저널만 필터링됨"
                    st.subheader(subheader_text)

                    df = pd.DataFrame(results)
                    df['SJR 등급'] = df['저널 SJR'].apply(classify_sjr)
                    df = df[[
                        "Top 저널", "제목 (Title)", "저자 (Authors)", "연도 (Year)", 
                        "매칭된 저널명 (전체)", "저널 SJR", "SJR 등급", 
                        "피인용 수", "매칭 점수 (%)", "검색된 저널명 (축약)", "논문 링크"
                    ]]
                    
                    st.dataframe(
                        df.style.applymap(color_sjr_score, subset=['저널 SJR']),
                        use_container_width=True,
                        column_config={"논문 링크": st.column_config.LinkColumn("바로가기", display_text="🔗 Link")},
                        hide_index=True
                    )
                    
                    st.download_button(
                        label="📄 결과 CSV 파일로 다운로드",
                        data=convert_df_to_csv(df),
                        file_name=f'search_{query.replace(" ", "_").replace(":", "")}.csv',
                        mime='text/csv'
                    )
            except Exception as e:
                st.error(f"검색 중 오류가 발생했습니다: {e}")
    elif submit_button and not (author or keyword):
        st.warning("저자 또는 키워드 중 하나 이상을 입력해야 합니다.")
