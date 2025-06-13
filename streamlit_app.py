import streamlit as st
import pandas as pd
from scholarly import scholarly
import io
from thefuzz import process, fuzz
import os

# ----------------------------------
# 페이지 설정
# ----------------------------------
st.set_page_config(
    page_title="Google Scholar 검색 결과 다운로더",
    page_icon="🎓",
    layout="wide",
)

# ----------------------------------
# 데이터 처리 및 조회 함수
# ----------------------------------
@st.cache_data
def load_if_data(file_path='journal_if_data.csv'):
    if not os.path.exists(file_path):
        return None, None
    try:
        df = pd.read_csv(file_path)
        if 'FullName' not in df.columns or 'ImpactFactor' not in df.columns:
            st.error(f"`{file_path}` 파일에 'FullName' 또는 'ImpactFactor' 컬럼이 없습니다.")
            return None, None
        df.dropna(subset=['FullName', 'ImpactFactor'], inplace=True)
        return df, df['FullName'].tolist()
    except Exception as e:
        st.error(f"IF 데이터 파일({file_path})을 로드하는 중 오류 발생: {e}")
        return None, None

@st.cache_data
def get_impact_factor(venue, if_df, journal_names):
    if not venue or if_df is None or not journal_names:
        return "N/A"
    match, score = process.extractOne(venue, journal_names, scorer=fuzz.token_sort_ratio)
    if score >= 85:
        if_value = if_df.loc[if_df['FullName'] == match, 'ImpactFactor'].iloc[0]
        return if_value
    else:
        return "N/A"

@st.cache_data
def to_excel(df: pd.DataFrame):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

@st.cache_data
def to_csv(df: pd.DataFrame):
    return df.to_csv(index=False).encode('utf-8-sig')

# ----------------------------------
# Streamlit 앱 UI 구성
# ----------------------------------
st.title("🎓 Google Scholar 검색 결과 다운로더 (IF 포함)")
st.markdown("""
이 앱은 [Google Scholar](https://scholar.google.com/)에서 키워드를 검색하고, 결과를 **CSV 또는 Excel 파일**로 다운로드할 수 있도록 도와줍니다.
- **저널 IF**: `journal_if_data.csv` 파일을 기반으로 저널의 Impact Factor(또는 SJR 지표)를 함께 표시합니다.
""")

if_df, journal_names = load_if_data()
if if_df is None:
    st.error("`journal_if_data.csv` 파일을 찾을 수 없습니다. 먼저 스크레이핑 스크립트를 실행하여 파일을 생성해주세요.")

with st.form(key='search_form'):
    keyword = st.text_input("**👉 검색어(Keyword)를 입력하세요**", placeholder="예: quantum computing")
    num_results = st.number_input("**👉 검색할 논문 수를 선택하세요**", min_value=5, max_value=50, value=10, step=5)
    submit_button = st.form_submit_button(label='🔍 검색 시작')

if submit_button and keyword:
    with st.spinner(f"'{keyword}'에 대한 논문을 검색 중입니다..."):
        try:
            search_query = scholarly.search_pubs(keyword)
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            for i, pub in enumerate(search_query):
                if i >= num_results: break
                bib = pub.get('bib', {})
                venue = bib.get('venue', 'N/A')
                impact_factor = get_impact_factor(venue, if_df, journal_names)
                results.append({
                    "제목 (Title)": bib.get('title', 'N/A'),
                    "저자 (Authors)": ", ".join(bib.get('author', ['N/A'])),
                    "연도 (Year)": bib.get('pub_year', 'N/A'),
                    "저널/출판물 (Journal/Venue)": venue,
                    "저널 IF (Impact Factor)": impact_factor,
                    "피인용 수 (Citations)": pub.get('num_citations', 0),
                    "링크 (URL)": pub.get('pub_url', '#'),
                })
                progress_percentage = (i + 1) / num_results
                progress_bar.progress(progress_percentage)
                status_text.text(f"논문 처리 중... {i+1}/{num_results}")
            
            progress_bar.empty()
            status_text.empty()

            if not results:
                st.warning("검색 결과가 없습니다.")
            else:
                df = pd.DataFrame(results)
                st.success(f"총 {len(df)}개의 검색 결과를 찾았습니다.")
                st.dataframe(df, use_container_width=True, column_config={"링크 (URL)": st.column_config.LinkColumn("Link", display_text="🔗 바로가기")}, hide_index=True)
                st.markdown("---")
                st.subheader("📥 파일 다운로드")
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button("📄 CSV 파일로 다운로드", to_csv(df), f'scholar_results_{keyword.replace(" ", "_")}.csv', 'text/csv')
                with col2:
                    st.download_button("📊 Excel 파일로 다운로드", to_excel(df), f'scholar_results_{keyword.replace(" ", "_")}.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")

elif submit_button and not keyword:
    st.warning("검색어를 입력해주세요.")
