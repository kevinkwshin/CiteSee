import streamlit as st
import pandas as pd
from scholarly import scholarly
import io

# ----------------------------------
# 페이지 설정
# ----------------------------------
st.set_page_config(
    page_title="Google Scholar 검색 결과 다운로더",
    page_icon="🎓",
    layout="wide",
)

# ----------------------------------
# 데이터 처리를 위한 함수
# ----------------------------------

# Excel 파일로 변환하는 함수
@st.cache_data
def to_excel(df: pd.DataFrame):
    """데이터프레임을 Excel 파일 형식의 bytes로 변환합니다."""
    output = io.BytesIO()
    # openpyxl 엔진을 사용해야 합니다.
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    processed_data = output.getvalue()
    return processed_data

# CSV 파일로 변환하는 함수
@st.cache_data
def to_csv(df: pd.DataFrame):
    """데이터프레임을 CSV 파일 형식의 bytes로 변환합니다."""
    # utf-8-sig로 인코딩해야 Excel에서 한글이 깨지지 않습니다.
    return df.to_csv(index=False).encode('utf-8-sig')


# ----------------------------------
# Streamlit 앱 UI 구성
# ----------------------------------

st.title("🎓 Google Scholar 검색 결과 다운로더")
st.markdown("""
이 앱은 [Google Scholar](https://scholar.google.com/)에서 키워드를 검색하고, 결과를 **CSV 또는 Excel 파일**로 다운로드할 수 있도록 도와줍니다.
- **검색어**: 찾고 싶은 논문의 키워드를 입력하세요. (예: `machine learning`, `artificial intelligence in healthcare`)
- **검색할 논문 수**: 가져올 논문의 최대 개수를 지정합니다. (최대 50개)
""")

# --- 입력 위젯 ---
with st.form(key='search_form'):
    keyword = st.text_input(
        "**👉 검색어(Keyword)를 입력하세요**", 
        placeholder="예: quantum computing"
    )
    num_results = st.number_input(
        "**👉 검색할 논문 수를 선택하세요**", 
        min_value=5, max_value=50, value=10, step=5
    )
    submit_button = st.form_submit_button(label='🔍 검색 시작')

# --- 검색 로직 및 결과 표시 ---
if submit_button and keyword:
    with st.spinner(f"'{keyword}'에 대한 논문을 검색 중입니다... 잠시만 기다려주세요."):
        try:
            # scholarly를 사용하여 검색 수행
            search_query = scholarly.search_pubs(keyword)
            
            results = []
            for i, pub in enumerate(search_query):
                if i >= num_results:
                    break
                
                # 각 필드에 대해 정보가 없는 경우를 대비하여 .get() 사용
                bib = pub.get('bib', {})
                title = bib.get('title', 'N/A')
                authors = ", ".join(bib.get('author', ['N/A']))
                pub_year = bib.get('pub_year', 'N/A')
                venue = bib.get('venue', 'N/A')
                num_citations = pub.get('num_citations', 0)
                pub_url = pub.get('pub_url', '#')
                
                results.append({
                    "제목 (Title)": title,
                    "저자 (Authors)": authors,
                    "연도 (Year)": pub_year,
                    "저널/출판물 (Journal/Venue)": venue,
                    "피인용 수 (Citations)": num_citations,
                    "링크 (URL)": pub_url,
                })
            
            if not results:
                st.warning("검색 결과가 없습니다. 다른 키워드로 시도해보세요.")
            else:
                # 결과를 데이터프레임으로 변환
                df = pd.DataFrame(results)
                
                st.success(f"총 {len(df)}개의 검색 결과를 찾았습니다.")
                
                # --- 데이터프레임 표시 ---
                st.dataframe(
                    df,
                    use_container_width=True,
                    # 링크를 클릭 가능하게 설정
                    column_config={
                        "링크 (URL)": st.column_config.LinkColumn(
                            "Link to Source", display_text="🔗 바로가기"
                        )
                    },
                    hide_index=True
                )
                
                st.markdown("---")
                st.subheader("📥 파일 다운로드")
                
                # --- 다운로드 버튼 ---
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="📄 CSV 파일로 다운로드",
                        data=to_csv(df),
                        file_name=f'scholar_results_{keyword.replace(" ", "_")}.csv',
                        mime='text/csv',
                    )
                with col2:
                    st.download_button(
                        label="📊 Excel 파일로 다운로드",
                        data=to_excel(df),
                        file_name=f'scholar_results_{keyword.replace(" ", "_")}.xlsx',
                        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )

        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")
            st.info("Google Scholar의 요청 제한(rate limit)에 도달했을 수 있습니다. 잠시 후 다시 시도해주세요.")

elif submit_button and not keyword:
    st.warning("검색어를 입력해주세요.")
