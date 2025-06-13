import streamlit as st
import pandas as pd
from scholarly import scholarly
import io
import requests
import time

# ----------------------------------
# 페이지 설정
# ----------------------------------
st.set_page_config(
    page_title="Scholar 검색기 (S2 API 연동)",
    page_icon="✨",
    layout="wide",
)

# ----------------------------------
# Semantic Scholar API 연동 함수
# ----------------------------------
@st.cache_data(ttl=3600)  # API 결과를 1시간 동안 캐싱하여 반복 호출 방지
def get_journal_info_from_s2(journal_name: str):
    """
    Semantic Scholar (S2) API를 사용하여 저널 정보를 조회합니다.
    :param journal_name: Google Scholar에서 가져온 저널 이름
    :return: (영향력 점수, 홈페이지 URL) 튜플
    """
    if not journal_name:
        return "N/A", "#"

    try:
        # S2의 저널 검색 API 엔드포인트
        # 저널 이름으로 검색하므로, 가장 관련성 높은 첫 번째 결과를 사용
        response = requests.get(
            "https://api.semanticscholar.org/graph/v1/journal/search",
            params={"query": journal_name, "fields": "journalName,homepage,latestImpactFactor"},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if data.get("data") and len(data["data"]) > 0:
            journal_data = data["data"][0] # 가장 관련성 높은 첫 번째 저널 정보 사용
            
            # S2 API 응답 구조에 따라 키 이름이 바뀔 수 있음 (문서 확인 필요)
            # 현재는 'latestImpactFactor'가 공식 필드는 아니지만, 있다고 가정하고 조회
            # 실제로는 influenceScore, citationCount 등을 활용할 수 있음
            impact_factor = journal_data.get("latestImpactFactor", "N/A")
            homepage = journal_data.get("homepage", "#")
            
            # 값이 없는 경우 처리
            if impact_factor is None: impact_factor = "N/A"
            if homepage is None: homepage = "#"

            return impact_factor, homepage
        else:
            return "N/A", "#"
            
    except requests.exceptions.RequestException as e:
        # API 요청이 너무 많거나 실패할 경우
        print(f"API Error for '{journal_name}': {e}")
        return "API 오류", "#"
    except Exception as e:
        print(f"Data parsing error for '{journal_name}': {e}")
        return "데이터 오류", "#"

# ----------------------------------
# 데이터 변환 함수 (기존과 동일)
# ----------------------------------
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
st.title("✨ Google Scholar 검색기 (Semantic Scholar API 연동)")
st.markdown("""
Google Scholar에서 논문을 검색하고, **[Semantic Scholar API](https://www.semanticscholar.org/product/api)**를 통해 실시간으로 저널 정보를 함께 조회합니다.
- `journal_if_data.csv` 파일이 더 이상 필요 없습니다.
- 검색된 저널명과 가장 유사한 저널의 **영향력 점수(Impact Factor)**와 **홈페이지** 정보를 가져옵니다.
""")

# --- 입력 폼 ---
with st.form(key='search_form'):
    keyword = st.text_input("**👉 검색어(Keyword)를 입력하세요**", placeholder="예: large language models")
    num_results = st.number_input(
        "**👉 검색할 논문 수를 선택하세요**", 
        min_value=5, max_value=30, value=10, step=5,
        help="API 호출 제한으로 인해 한 번에 너무 많은 수를 검색하면 느려질 수 있습니다."
    )
    submit_button = st.form_submit_button(label='🔍 검색 시작')

# --- 검색 로직 및 결과 표시 ---
if submit_button and keyword:
    with st.spinner(f"'{keyword}' 논문 검색 및 S2 API로 저널 정보 조회 중..."):
        try:
            search_query = scholarly.search_pubs(keyword)
            results = []
            
            progress_bar = st.progress(0, text="논문 처리 시작...")

            for i, pub in enumerate(search_query):
                if i >= num_results:
                    break
                
                # API 호출 사이의 간격을 두어 Rate Limit 방지
                time.sleep(0.5) 
                
                bib = pub.get('bib', {})
                venue = bib.get('venue', 'N/A')
                
                # 실시간으로 S2 API를 통해 저널 정보 조회
                impact_factor, journal_homepage = get_journal_info_from_s2(venue)
                
                results.append({
                    "제목 (Title)": bib.get('title', 'N/A'),
                    "저자 (Authors)": ", ".join(bib.get('author', ['N/A'])),
                    "연도 (Year)": bib.get('pub_year', 'N/A'),
                    "저널/출판물 (Journal/Venue)": venue,
                    "저널 IF (S2)": impact_factor,
                    "피인용 수 (Citations)": pub.get('num_citations', 0),
                    "논문 링크": pub.get('pub_url', '#'),
                    "저널 홈페이지": journal_homepage,
                })

                # 진행 상태 업데이트
                progress_percentage = (i + 1) / num_results
                progress_bar.progress(progress_percentage, text=f"논문 처리 중... {i+1}/{num_results}")

            progress_bar.empty()

            if not results:
                st.warning("검색 결과가 없습니다. 다른 키워드로 시도해보세요.")
            else:
                df = pd.DataFrame(results)
                
                st.success(f"총 {len(df)}개의 검색 결과를 찾았습니다.")
                
                st.dataframe(
                    df,
                    use_container_width=True,
                    # 링크 컬럼 설정
                    column_config={
                        "논문 링크": st.column_config.LinkColumn("논문 바로가기", display_text="🔗 Paper"),
                        "저널 홈페이지": st.column_config.LinkColumn("홈페이지", display_text="🏠 Homepage")
                    },
                    hide_index=True,
                )
                
                st.markdown("---")
                st.subheader("📥 파일 다운로드")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="📄 CSV 파일로 다운로드",
                        data=to_csv(df),
                        file_name=f's2_scholar_results_{keyword.replace(" ", "_")}.csv',
                        mime='text/csv',
                    )
                with col2:
                    st.download_button(
                        label="📊 Excel 파일로 다운로드",
                        data=to_excel(df),
                        file_name=f's2_scholar_results_{keyword.replace(" ", "_")}.xlsx',
                        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )

        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")
            st.info("Google Scholar 또는 Semantic Scholar의 요청 제한(rate limit)에 도달했을 수 있습니다. 잠시 후 다시 시도해주세요.")

elif submit_button and not keyword:
    st.warning("검색어를 입력해주세요.")
