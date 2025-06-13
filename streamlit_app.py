import streamlit as st
import pandas as pd
from scholarly import scholarly
import io
from thefuzz import process, fuzz
import os

# --- 1. 페이지 설정 ---
st.set_page_config(
    page_title="논문 검색 다운로더",
    page_icon="📚",
    layout="wide",
)

# --- 2. 핵심 함수 (캐싱으로 성능 최적화) ---
@st.cache_data
def load_journal_db(file_path='journal_if_data.csv'):
    """저널 데이터 CSV 파일을 로드합니다."""
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
    """유사도 매칭으로 저널의 SJR 점수를 찾습니다."""
    if not venue or db_df is None or not journal_names_list:
        return "N/A"
    
    match, score = process.extractOne(venue, journal_names_list, scorer=fuzz.token_sort_ratio)
    
    if score >= 80:
        sjr_value = db_df.loc[db_df['FullName'] == match, 'ImpactFactor'].iloc[0]
        return f"{sjr_value:.3f}"
    else:
        return "N/A"

@st.cache_data
def convert_df_to_csv(df: pd.DataFrame):
    """데이터프레임을 다운로드 가능한 CSV로 변환합니다."""
    return df.to_csv(index=False).encode('utf-8-sig')


# --- 3. UI 본문 구성 ---
st.title("📚 논문 검색 및 정보 다운로더")
st.markdown("Google Scholar에서 논문을 검색하고, **SJR(Scimago Journal Rank) 지표**를 함께 조회하여 다운로드합니다.")

# --- 데이터베이스 로드 및 상태 표시 ---
db_df, journal_names = load_journal_db()

if db_df is None:
    st.error("⚠️ `journal_if_data.csv` 파일을 찾을 수 없습니다. `scrape_if_data.py`를 먼저 실행하여 데이터베이스를 생성해주세요.")
else:
    st.success(f"✅ 총 {len(db_df):,}개의 저널 정보가 담긴 데이터베이스를 성공적으로 로드했습니다.")

    # --- 검색 폼 ---
    with st.form(key='search_form'):
        st.subheader("🔍 검색 조건 입력")
        
        col1, col2 = st.columns(2)
        with col1:
            author = st.text_input("저자 (선택 사항)", placeholder="예: Hinton G")
        with col2:
            keyword = st.text_input("키워드 (필수)", placeholder="예: deep learning")
            
        num_results = st.slider("가져올 논문 수", min_value=5, max_value=50, value=10)
        submit_button = st.form_submit_button(label='검색 시작')

    # --- 검색 실행 및 결과 표시 ---
    if submit_button and keyword:
        # 저자명과 키워드를 조합하여 검색 쿼리 생성
        query = keyword
        if author:
            query += f' author:"{author}"'

        with st.spinner(f"'{query}' 조건으로 논문을 검색 중입니다..."):
            try:
                search_query = scholarly.search_pubs(query)
                results = []

                for i, pub in enumerate(search_query):
                    if i >= num_results: break
                    bib = pub.get('bib', {})
                    venue = bib.get('venue', 'N/A')
                    
                    # SJR 점수 조회
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
                    st.warning("검색된 논문이 없습니다. 다른 키워드나 저자를 시도해보세요.")
                else:
                    st.subheader("📊 검색 결과")
                    df = pd.DataFrame(results)
                    st.dataframe(
                        df, use_container_width=True,
                        column_config={"논문 링크": st.column_config.LinkColumn("바로가기", display_text="🔗 Link")},
                        hide_index=True
                    )
                    
                    st.download_button(
                        label="📄 결과 CSV 파일로 다운로드",
                        data=convert_df_to_csv(df),
                        file_name=f'search_{keyword.replace(" ", "_")}.csv',
                        mime='text/csv'
                    )

            except Exception as e:
                st.error(f"검색 중 오류가 발생했습니다: {e}")

    elif submit_button and not keyword:
        st.warning("키워드는 반드시 입력해야 합니다.")
