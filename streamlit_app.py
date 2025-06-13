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
@st.cache_data(ttl=3600)
def get_journal_info_from_s2(journal_name: str):
    """
    Semantic Scholar (S2) API를 사용하여 저널 정보를 조회합니다.
    :param journal_name: Google Scholar에서 가져온 저널 이름
    :return: (영향력 점수, 홈페이지 URL, S2에서 찾은 저널명) 튜플
    """
    if not journal_name:
        return "N/A", "#", "N/A"

    try:
        response = requests.get(
            "https://api.semanticscholar.org/graph/v1/journal/search",
            params={"query": journal_name, "fields": "journalName,homepage,influenceScore"},
            headers={"Accept": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if data.get("total", 0) > 0 and data.get("data"):
            journal_data = data["data"][0]
            
            influence_score = journal_data.get("influenceScore")
            if influence_score is not None:
                try:
                    score_str = f"{float(influence_score):.2f}"
                except (ValueError, TypeError):
                    score_str = "N/A"
            else:
                score_str = "N/A"

            homepage = journal_data.get("homepage", "#")
            s2_journal_name = journal_data.get("journalName", "N/A")

            if homepage is None: homepage = "#"
            if s2_journal_name is None: s2_journal_name = "N/A"

            return score_str, homepage, s2_journal_name
        else:
            return "N/A", "#", "결과 없음"
            
    except requests.exceptions.RequestException as e:
        print(f"API Error for '{journal_name}': {e}")
        return "API 오류", "#", "N/A"
    except Exception as e:
        print(f"Data parsing error for '{journal_name}': {e}")
        return "데이터 오류", "#", "N/A"

# ----------------------------------
# 데이터 변환 함수
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
- **`influenceScore`**: S2가 자체 계산한 저널의 영향력 지표입니다.
- **`S2 저널명`**: 검색된 저널명으로 S2에서 매칭한 공식 저널 이름입니다.
""")

with st.form(key='search_form'):
    keyword = st.text_input("**👉 검색어(Keyword)를 입력하세요**", placeholder="예: large language models")
    num_results = st.number_input("**👉 검색할 논문 수를 선택하세요**", min_value=5, max_value=30, value=10, step=5,
                                  help="API 호출 제한으로 인해 한 번에 너무 많은 수를 검색하면 느려질 수 있습니다.")
    submit_button = st.form_submit_button(label='🔍 검색 시작')

if submit_button and keyword:
    with st.spinner(f"'{keyword}' 논문 검색 및 S2 API로 저널 정보 조회 중..."):
        try:
            search_query = scholarly.search_pubs(keyword)
            results = []
            progress_bar = st.progress(0, text="논문 처리 시작...")

            for i, pub in enumerate(search_query):
                if i >= num_results: break
                time.sleep(0.5)
                bib = pub.get('bib', {})
                venue = bib.get('venue', 'N/A')
                
                influence_score, journal_homepage, s2_name = get_journal_info_from_s2(venue)
                
                results.append({
                    "제목 (Title)": bib.get('title', 'N/A'),
                    "저자 (Authors)": ", ".join(bib.get('author', ['N/A'])),
                    "연도 (Year)": bib.get('pub_year', 'N/A'),
                    "저널/출판물 (Venue)": venue,
                    "영향력 점수 (S2)": influence_score,
                    "피인용 수 (Citations)": pub.get('num_citations', 0),
                    "논문 링크": pub.get('pub_url', '#'),
                    "저널 홈페이지": journal_homepage,
                    "S2 저널명": s2_name,
                })

                progress_percentage = (i + 1) / num_results
                progress_bar.progress(progress_percentage, text=f"논문 처리 중... {i+1}/{num_results}")

            progress_bar.empty()

            if not results:
                st.warning("검색 결과가 없습니다.")
            else:
                df = pd.DataFrame(results)
                st.success(f"총 {len(df)}개의 검색 결과를 찾았습니다.")
                st.dataframe(
                    df, use_container_width=True,
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
                    # --- 오타 수정된 부분 ---
                    st.download_button(
                        label="📄 CSV 파일로 다운로드",
                        data=to_csv(df),
                        file_name=f's2_scholar_results_{keyword.replace(" ", "_")}.csv',
                        mime='text/csv'
                    )
                with col2:
                    # --- 오타 수정된 부분 ---
                    st.download_button(
                        label="📊 Excel 파일로 다운로드",
                        data=to_excel(df),
                        file_name=f's2_scholar_results_{keyword.replace(" ", "_")}.xlsx',
                        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )

        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")

elif submit_button and not keyword:
    st.warning("검색어를 입력해주세요.")
