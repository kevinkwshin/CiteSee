import streamlit as st
import pandas as pd
from scholarly import scholarly
import io
import google.generativeai as genai
import time
import re

# --- 1. 페이지 설정 및 API 키 구성 ---
st.set_page_config(
    page_title="AI 논문 검색기",
    page_icon="🔬",
    layout="centered", # 더 집중되고 심플한 UI를 위해 centered 레이아웃 사용
)

# Streamlit Secrets에서 Gemini API 키 가져오기
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except (KeyError, FileNotFoundError):
    st.error("🚨 Gemini API 키를 찾을 수 없습니다.")
    st.info("Streamlit Cloud의 'Settings > Secrets'에 `GEMINI_API_KEY = '당신의API키'` 형식으로 API 키를 추가해주세요.")
    st.stop()

# --- 2. 핵심 함수: Gemini API 호출 ---
@st.cache_data(ttl=3600) # 1시간 동안 API 응답 캐싱
def get_if_from_gemini(journal_name: str):
    """
    Gemini 1.5 Flash 모델을 사용하여 저널의 IF를 '추정'합니다.
    """
    if not journal_name:
        return "N/A"
    
    # 매우 구체적이고 간결한 응답을 유도하는 프롬프트
    prompt = f"""
    What is the most recent official Journal Impact Factor for the journal: "{journal_name}"?
    Respond with ONLY the number (e.g., '42.778') or 'N/A' if you cannot find it. 
    Do not add any other text, explanation, or sentences.
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        
        # AI 응답에서 숫자만 정확히 추출하기 위한 정규표현식
        text_response = response.text.strip()
        match = re.search(r'(\d{1,3}(?:\.\d{1,3})?)', text_response)
        
        if match:
            return match.group(1)
        # 숫자를 찾지 못하면, AI의 응답을 그대로 보여주되 길이를 제한
        elif text_response:
             return text_response if len(text_response) < 15 else "AI 응답 없음"
        else:
            return "N/A"

    except Exception as e:
        print(f"Gemini API Error for '{journal_name}': {e}")
        return "API 오류"


# --- 3. 데이터 변환 함수 ---
@st.cache_data
def convert_to_csv(df):
    return df.to_csv(index=False).encode('utf-8-sig')

# --- 4. UI 본문 구성 ---
st.title("🔬 AI 기반 논문 검색기")
st.warning(
    "**[안내]** 이 앱은 **Google Gemini AI**를 사용하여 저널의 Impact Factor를 **실시간으로 추정**합니다. "
    "AI가 생성하는 정보이므로 **부정확할 수 있으며, 참고용으로만 사용**해주세요."
)

with st.form(key='search_form'):
    keyword = st.text_input("검색할 키워드를 입력하세요", placeholder="예: artificial intelligence in medicine")
    num_results = st.slider("가져올 논문 수", min_value=1, max_value=15, value=5, 
                            help="API 호출 비용과 속도를 위해 최대 15개까지 가능합니다.")
    submit_button = st.form_submit_button(label='🚀 검색 시작')

if submit_button and keyword:
    with st.spinner(f"'{keyword}' 논문 검색 및 AI로 IF 추정 중..."):
        try:
            search_query = scholarly.search_pubs(keyword)
            results = []

            # 진행 상태 바
            progress_bar = st.progress(0)
            
            for i, pub in enumerate(search_query):
                if i >= num_results: break
                
                # Gemini API의 분당 요청 제한(rate limit)을 존중하기 위한 지연
                time.sleep(1) 
                
                bib = pub.get('bib', {})
                venue = bib.get('venue', 'N/A')
                
                impact_factor = get_if_from_gemini(venue)
                
                results.append({
                    "제목 (Title)": bib.get('title', 'N/A'),
                    "저자 (Authors)": ", ".join(bib.get('author', ['N/A'])),
                    "연도 (Year)": bib.get('pub_year', 'N/A'),
                    "저널 (Venue)": venue,
                    "IF 추정치 (AI)": impact_factor,
                    "피인용 수": pub.get('num_citations', 0),
                    "논문 링크": pub.get('pub_url', '#'),
                })
                # 진행 상태 업데이트
                progress_bar.progress((i + 1) / num_results)

            if not results:
                st.warning("검색된 논문이 없습니다. 다른 키워드를 시도해보세요.")
            else:
                st.success("✅ 검색 및 AI 추정 완료!")
                df = pd.DataFrame(results)
                
                st.dataframe(
                    df, use_container_width=True,
                    column_config={"논문 링크": st.column_config.LinkColumn("Link", display_text="🔗")},
                    hide_index=True)
                
                st.download_button(
                    label="📄 결과 CSV 파일로 다운로드",
                    data=convert_to_csv(df),
                    file_name=f'ai_if_search_{keyword.replace(" ", "_")}.csv',
                    mime='text/csv'
                )

        except Exception as e:
            st.error(f"검색 중 오류가 발생했습니다: {e}")
            st.info("Google Scholar 또는 Gemini API의 요청이 일시적으로 차단되었을 수 있습니다.")
