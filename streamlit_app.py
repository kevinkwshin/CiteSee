import streamlit as st
import pandas as pd
from scholarly import scholarly
import io
import requests
from bs4 import BeautifulSoup
import re
import time

# --- 1. 페이지 설정 및 상수 정의 ---
st.set_page_config(
    page_title="논문 검색기",
    page_icon="🎯",
    layout="centered", # 심플한 UI를 위한 레이아웃
)

# High Impact Journal을 판단하는 IF 임계값 (이 값보다 높으면 'Y')
# 이 기준은 분야마다 다르므로, 필요에 따라 조절할 수 있습니다.
HIGH_IMPACT_THRESHOLD = 10.0

# --- 2. 핵심 함수: Google 검색으로 Y/N 판별 ---
@st.cache_data(ttl=3600) # 1시간 동안 검색 결과 캐싱
def check_if_high_impact(journal_name: str):
    """
    Google 검색으로 저널의 IF를 찾아, 임계값과 비교하여 Y/N을 반환합니다.
    **매우 불안정하며 실험적인 기능입니다.**
    """
    if not journal_name:
        return "N/A"

    try:
        query = f'"{journal_name}" journal impact factor'
        url = f"https://www.google.com/search?q={query}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if "Our systems have detected unusual traffic" in response.text:
            return "차단됨"
        
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        page_text = soup.get_text()
        
        # IF로 추정되는 숫자 패턴 찾기
        pattern = r"(?:impact factor|if)\s*[:\-]?\s*(\d{1,3}\.\d{1,3})"
        match = re.search(pattern, page_text, re.IGNORECASE)
        
        if match:
            extracted_if = float(match.group(1))
            # 임계값과 비교하여 Y/N 반환
            return "Y" if extracted_if >= HIGH_IMPACT_THRESHOLD else "N"
        else:
            return "N/A" # IF 정보를 찾지 못함

    except Exception:
        return "오류"

# --- 3. 데이터 변환 함수 ---
@st.cache_data
def convert_to_csv(df):
    return df.to_csv(index=False).encode('utf-8-sig')

# --- 4. UI 본문 ---
st.title("🎯 논문 검색기")
st.info(
    f"**[안내]** 'High Impact' 여부는 Google 검색을 통해 추정한 IF가 **{HIGH_IMPACT_THRESHOLD} 이상**인지 여부로 판단합니다. "
    "이 과정은 **부정확할 수 있으며, Google에 의해 차단**될 수 있습니다."
)

with st.form(key='search_form'):
    keyword = st.text_input("검색 키워드", placeholder="예: quantum computing")
    num_results = st.slider("검색할 논문 수", 1, 10, 5, help="Google 검색 차단 방지를 위해 최대 10개까지 가능합니다.")
    submit_button = st.form_submit_button(label='검색')

if submit_button and keyword:
    with st.spinner("논문 검색 및 High Impact 여부 확인 중..."):
        try:
            search_query = scholarly.search_pubs(keyword)
            results = []

            for i, pub in enumerate(search_query):
                if i >= num_results: break
                time.sleep(1) # Google 검색 부하를 줄이기 위한 지연
                
                bib = pub.get('bib', {})
                venue = bib.get('venue', 'N/A')
                
                high_impact_status = check_if_high_impact(venue)
                
                results.append({
                    "제목 (Title)": bib.get('title', 'N/A'),
                    "저널 (Venue)": venue,
                    "연도 (Year)": bib.get('pub_year', 'N/A'),
                    "High Impact": high_impact_status,
                    "피인용 수": pub.get('num_citations', 0),
                    "저자 (Authors)": ", ".join(bib.get('author', ['N/A'])),
                    "논문 링크": pub.get('pub_url', '#'),
                })

            if not results:
                st.warning("검색된 논문이 없습니다.")
            else:
                st.success("✅ 검색이 완료되었습니다.")
                df = pd.DataFrame(results)
                
                # 컬럼 순서를 더 보기 좋게 재배치
                df = df[["제목 (Title)", "저널 (Venue)", "연도 (Year)", "High Impact", "피인용 수", "저자 (Authors)", "논문 링크"]]
                
                st.dataframe(
                    df, use_container_width=True,
                    column_config={"논문 링크": st.column_config.LinkColumn("Link", display_text="🔗")},
                    hide_index=True)
                
                st.download_button(
                    label="📄 CSV 다운로드",
                    data=convert_to_csv(df),
                    file_name=f'search_{keyword.replace(" ", "_")}.csv',
                    mime='text/csv'
                )

        except Exception as e:
            st.error(f"검색 중 오류가 발생했습니다: {e}")
