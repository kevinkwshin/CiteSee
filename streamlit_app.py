import streamlit as st
import pandas as pd
from scholarly import scholarly
import io
import requests
from bs4 import BeautifulSoup
import re
import time

# ----------------------------------
# 페이지 설정
# ----------------------------------
st.set_page_config(
    page_title="논문 검색기 (Google IF 스크레이퍼)",
    page_icon="🧪",
    layout="wide",
)

# ----------------------------------
# Google 검색 스크레이핑 함수
# ----------------------------------
@st.cache_data(ttl=3600)  # 결과를 1시간 동안 캐시
def get_if_from_google_search(journal_name: str):
    """
    Google 검색을 통해 저널의 Impact Factor를 스크레이핑합니다.
    **매우 불안정하며 실험적인 기능입니다.**
    """
    if not journal_name:
        return "N/A"

    try:
        # 검색어 생성 (저널 이름과 "impact factor"를 함께 검색)
        query = f'"{journal_name}" journal impact factor'
        url = f"https://www.google.com/search?q={query}"
        
        # Google 차단을 피하기 위한 User-Agent 설정
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        # Google이 요청을 차단했는지 확인 (응답 내용으로 판단)
        if "Our systems have detected unusual traffic" in response.text:
            return "Scraping Blocked"
        
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 페이지 전체 텍스트에서 IF 패턴 검색
        page_text = soup.get_text()
        
        # 정규표현식으로 "Impact Factor: 12.345" 와 같은 패턴 찾기
        # (?: ... ) 는 non-capturing group 입니다.
        pattern = r"(?:impact factor|if)\s*[:\-]?\s*(\d{1,3}\.\d{1,3})"
        match = re.search(pattern, page_text, re.IGNORECASE)
        
        if match:
            return match.group(1) # 첫 번째 캡처 그룹 (숫자 부분) 반환
        else:
            return "Not Found"

    except requests.exceptions.RequestException:
        return "Network Error"
    except Exception:
        return "Parsing Error"

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
st.title("🧪 논문 검색기 (실험적 IF 스크레이퍼)")
st.warning(
    "**[중요] 안내:** 이 앱은 **Google 검색**을 통해 저널의 Impact Factor를 **실시간으로 추정**합니다. "
    "이 방법은 아래와 같은 한계가 있습니다.\n"
    "1. Google의 정책에 의해 **검색이 자주 차단**될 수 있습니다. ('Scraping Blocked' 오류)\n"
    "2. 표시되는 수치는 **정확하지 않거나 오래된 정보**일 수 있습니다.\n"
    "3. 검색 속도가 매우 느립니다."
)

with st.form(key='search_form'):
    keyword = st.text_input("**👉 검색어(Keyword)를 입력하세요**", placeholder="예: nature machine intelligence")
    num_results = st.number_input("**👉 검색할 논문 수를 선택하세요**", min_value=1, max_value=10, value=5, step=1,
                                  help="속도와 차단 방지를 위해 한 번에 최대 10개까지 가능합니다.")
    submit_button = st.form_submit_button(label='🔍 검색 시작')

if submit_button and keyword:
    with st.spinner(f"논문 검색 및 Google에서 IF 추정 중... (매우 느릴 수 있습니다)"):
        try:
            search_query = scholarly.search_pubs(keyword)
            results = []
            
            for i, pub in enumerate(search_query):
                if i >= num_results: break
                
                # Google 검색 요청 사이에 충분한 시간 간격 주기
                time.sleep(1) 
                
                bib = pub.get('bib', {})
                venue = bib.get('venue', 'N/A')
                # Google Scholar가 제공하는 저널명은 '...'으로 축약되는 경우가 많음
                # 예: 'Nature Machine Intelligence' -> 'Nat. Mach. Intell.'
                # 이는 정확한 검색을 방해할 수 있음
                
                impact_factor = get_if_from_google_search(venue)
                
                results.append({
                    "제목 (Title)": bib.get('title', 'N/A'),
                    "저자 (Authors)": ", ".join(bib.get('author', ['N/A'])),
                    "연도 (Year)": bib.get('pub_year', 'N/A'),
                    "저널/출판물 (Venue)": venue,
                    "IF 추정치 (Google)": impact_factor,
                    "피인용 수 (Citations)": pub.get('num_citations', 0),
                    "논문 링크": pub.get('pub_url', '#'),
                })

            df = pd.DataFrame(results)
            st.success(f"총 {len(df)}개의 검색 결과를 찾았습니다.")
            st.dataframe(
                df, use_container_width=True,
                column_config={"논문 링크": st.column_config.LinkColumn("바로가기")},
                hide_index=True)
            
            st.markdown("---")
            st.subheader("📥 파일 다운로드")
            col1, col2 = st.columns(2)
            with col1:
                st.download_button("📄 CSV 다운로드", to_csv(df), f'google_if_{keyword.replace(" ", "_")}.csv', 'text/csv')
            with col2:
                st.download_button("📊 Excel 다운로드", to_excel(df), f'google_if_{keyword.replace(" ", "_")}.xlsx')

        except Exception as e:
            st.error(f"검색 중 심각한 오류가 발생했습니다: {e}")
            st.info("Google Scholar의 요청이 차단되었을 수 있습니다. 잠시 후 다시 시도해주세요.")

elif submit_button and not keyword:
    st.warning("검색어를 입력해주세요.")
