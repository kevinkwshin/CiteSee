import streamlit as st
import pandas as pd
from scholarly import scholarly
import io
import google.generativeai as genai
import time
import re

# --- 1. 페이지 설정 ---
st.set_page_config(
    page_title="AI 논문 검색기",
    page_icon="🔬",
    layout="centered",
)

# --- 2. 사이드바: API 키 입력 ---
st.sidebar.title("⚙️ 설정")
gemini_api_key = st.sidebar.text_input(
    "Gemini API 키를 입력하세요",
    type="password",
    help="Google AI Studio에서 무료 API 키를 발급받을 수 있습니다."
)
st.sidebar.markdown("[API 키 발급받기 (Google AI Studio)](https://aistudio.google.com/)", unsafe_allow_html=True)

# API 키가 입력되었는지 확인하고 Gemini 라이브러리 설정
api_configured = False
if gemini_api_key:
    try:
        genai.configure(api_key=gemini_api_key)
        st.sidebar.success("✅ API 키가 성공적으로 설정되었습니다.")
        api_configured = True
    except Exception as e:
        st.sidebar.error(f"API 키 설정 오류: {e}")

# --- 3. 핵심 함수: Gemini API 호출 ---
@st.cache_data(ttl=3600)
def get_if_from_gemini(journal_name: str):
    if not journal_name:
        return "N/A"
    
    prompt = f"""
    What is the most recent official Journal Impact Factor for the journal: "{journal_name}"?
    Respond with ONLY the number (e.g., '42.778') or 'N/A' if you cannot find it. 
    Do not add any other text or explanation.
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        text_response = response.text.strip()
        match = re.search(r'(\d{1,3}(?:\.\d{1,3})?)', text_response)
        
        if match:
            return match.group(1)
        return text_response if len(text_response) < 15 else "AI 응답 없음"

    except Exception as e:
        # API 호출 중 발생하는 오류 (잘못된 키, 사용량 초과 등)
        error_message = str(e)
        if "API key not valid" in error_message:
            return "잘못된 키"
        return "API 오류"


# --- 4. 데이터 변환 함수 ---
@st.cache_data
def convert_to_csv(df):
    return df.to_csv(index=False).encode('utf-8-sig')


# --- 5. UI 본문 ---
st.title("🔬 AI 논문 검색기")

if not api_configured:
    st.info("👈 시작하려면, 사이드바에 자신의 Google Gemini API 키를 입력해주세요.")
    st.image("https://i.imgur.com/3Z6n5pD.png", caption="사이드바에 API 키를 입력하는 곳이 있습니다.")

# API 키가 설정된 경우에만 검색 폼과 안내 표시
if api_configured:
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
                progress_bar = st.progress(0, "검색 시작...")
                
                for i, pub in enumerate(search_query):
                    if i >= num_results: break
                    time.sleep(1) # API Rate Limit 존중
                    
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
                    progress_bar.progress((i + 1) / num_results, f"논문 처리 중... {i+1}/{num_results}")

                if not results:
                    st.warning("검색된 논문이 없습니다.")
                else:
                    st.success("✅ 검색 및 AI 추정 완료!")
                    df = pd.DataFrame(results)
                    st.dataframe(
                        df, use_container_width=True,
                        column_config={"논문 링크": st.column_config.LinkColumn("Link", display_text="🔗")},
                        hide_index=True)
                    st.download_button("📄 결과 CSV 파일로 다운로드", convert_to_csv(df), f'ai_if_search_{keyword.replace(" ", "_")}.csv", 'text/csv')

            except Exception as e:
                st.error(f"검색 중 오류 발생: {e}")
