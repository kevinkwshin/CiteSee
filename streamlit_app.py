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

# ⭐️ 새로운 기능: 보이지 않는 안전장치 (최대 검색 결과 제한)
MAX_RESULTS_LIMIT = 200

# --- 2. 핵심 함수 (데이터 로딩, 매칭, 스타일링) ---
@st.cache_data
def load_journal_db(file_path='journal_if_data.csv'):
    if not os.path.exists(file_path):
        return None, None
    try:
        df = pd.read_csv(file_path)
        df.dropna(subset=['FullName', 'ImpactFactor'], inplace=True)
        return df, df['FullName'].tolist()
    except Exception as e:
        st.error(f"데이터 파일({file_path}) 로드 오류: {e}")
        return None, None

@st.cache_data
def get_journal_info(venue, db_df, journal_names_list):
    if not venue or db_df is None or not journal_names_list:
        return "N/A"
    match, score = process.extractOne(venue, journal_names_list, scorer=fuzz.token_sort_ratio)
    if score >= 80:
        sjr_value = db_df.loc[db_df['FullName'] == match, 'ImpactFactor'].iloc[0]
        return f"{sjr_value:.3f}"
    return "N/A"

def classify_sjr(sjr_score_str):
    if sjr_score_str == "N/A":
        return "N/A"
    try:
        score = float(sjr_score_str)
        if score >= 1.0: return "우수"
        elif 0.5 <= score < 1.0: return "양호"
        elif 0.2 <= score < 0.5: return "보통"
        else: return "하위"
    except (ValueError, TypeError):
        return "N/A"

def color_sjr_score(val):
    try:
        score = float(val)
        if score >= 1.0: color = 'green'
        elif 0.5 <= score < 1.0: color = 'blue'
        elif 0.2 <= score < 0.5: color = 'orange'
        else: color = 'red'
        return f'color: {color}; font-weight: bold;'
    except (ValueError, TypeError):
        return 'color: grey;'

@st.cache_data
def convert_df_to_csv(df: pd.DataFrame):
    return df.to_csv(index=False).encode('utf-8-sig')


# --- 3. UI 본문 구성 ---
st.title("📚 논문 검색 및 정보 다운로더")
# ⭐️ 새로운 기능: UI 텍스트 수정
st.markdown(f"Google Scholar에서 논문을 검색하고, SJR 지표를 함께 조회합니다. (안정성을 위해 최대 **{MAX_RESULTS_LIMIT}개**까지 표시)")

db_df, journal_names = load_journal_db()
if db_df is None:
    st.error("⚠️ `journal_if_data.csv` 파일을 찾을 수 없습니다. `scrape_if_data.py`를 먼저 실행해주세요.")
else:
    st.success(f"✅ 총 {len(db_df):,}개의 저널 정보가 담긴 데이터베이스를 성공적으로 로드했습니다.")
    
    with st.expander("💡 SJR 점수 해석 가이드 보기"):
        st.markdown("""
        - **<span style='color:green;'>1.0 이상</span>**: 우수 저널
        - **<span style='color:blue;'>0.5 ~ 1.0</span>**: 양호 저널
        - **<span style='color:orange;'>0.2 ~ 0.5</span>**: 보통 저널
        - **<span style='color:red;'>0.2 미만</span>**: 하위 저널
        """, unsafe_allow_html=True)

    with st.form(key='search_form'):
        st.subheader("🔍 검색 조건 입력")
        col1, col2 = st.columns(2)
        with col1:
            author = st.text_input("저자 (선택 사항)", placeholder="예: Hinton G")
        with col2:
            keyword = st.text_input("키워드 (선택 사항)", placeholder="예: deep learning")
        
        # ⭐️ 새로운 기능: 검색 개수 슬라이더 제거
        # num_results = st.slider("가져올 논문 수", min_value=5, max_value=50, value=10)
        
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
                    # ⭐️ 새로운 기능: 내부적으로 설정된 최대 개수까지만 가져옴
                    if i >= MAX_RESULTS_LIMIT:
                        st.info(f"검색 결과가 많아 최대 {MAX_RESULTS_LIMIT}개까지만 표시합니다.")
                        break
                    
                    bib = pub.get('bib', {})
                    venue = bib.get('venue', 'N/A')
                    sjr_score = get_journal_info(venue, db_df, journal_names)
                    
                    results.append({
                        "제목 (Title)": bib.get('title', 'N/A'),
                        "저자 (Authors)": ", ".join(bib.get('author', ['N/A'])),
                        "연도 (Year)": bib.get('pub_year', 'N/A'),
                        "저널 (Venue)": venue,
                        "저널 SJR": sjr_score,
                        "피인용 수": pub.get('num_citations', 0),
                        "논문 링크": pub.get('pub_url', '#'),
                    })

                if not results:
                    st.warning("검색된 논문이 없습니다.")
                else:
                    st.subheader(f"📊 검색 결과 ({len(results)}개)")
                    df = pd.DataFrame(results)
                    df['SJR 등급'] = df['저널 SJR'].apply(classify_sjr)
                    df = df[["제목 (Title)", "저자 (Authors)", "연도 (Year)", "저널 (Venue)", "저널 SJR", "SJR 등급", "피인용 수", "논문 링크"]]
                    
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
