import streamlit as st
import pandas as pd
from scholarly import scholarly
import io
import requests
import time
import json # JSON을 예쁘게 출력하기 위해 추가

# ----------------------------------
# 페이지 설정
# ----------------------------------
st.set_page_config(
    page_title="Scholar 검색기 (S2 API 연동)",
    page_icon="🛠️",
    layout="wide",
)

# ----------------------------------
# Semantic Scholar API 연동 함수 (로그 기능 강화)
# ----------------------------------
@st.cache_data(ttl=3600)
def get_journal_info_from_s2(journal_name: str):
    """
    S2 API를 사용하여 저널 정보를 조회하고, 모든 과정을 로그로 반환합니다.
    :return: ((결과 튜플), (로그 딕셔너리))
    """
    log_info = {
        "input_journal": journal_name,
        "request_url": "N/A",
        "status_code": "N/A",
        "raw_response": "N/A",
        "error_message": "N/A",
    }
    
    if not journal_name:
        log_info["error_message"] = "입력된 저널명이 없습니다."
        return (("N/A", "#", "N/A"), log_info)

    try:
        params = {"query": journal_name, "fields": "journalName,homepage,influenceScore"}
        response = requests.get(
            "https://api.semanticscholar.org/graph/v1/journal/search",
            params=params,
            headers={"Accept": "application/json"},
            timeout=15
        )
        
        # --- 모든 응답 정보를 로그에 기록 ---
        log_info["request_url"] = response.url # 최종적으로 요청된 URL
        log_info["status_code"] = response.status_code
        log_info["raw_response"] = response.text

        response.raise_for_status() # 200번대 코드가 아니면 여기서 에러 발생시킴
        
        data = response.json()

        if data.get("total", 0) > 0 and data.get("data"):
            journal_data = data["data"][0]
            influence_score = journal_data.get("influenceScore")
            score_str = f"{float(influence_score):.2f}" if influence_score is not None else "N/A"
            homepage = journal_data.get("homepage") or "#"
            s2_journal_name = journal_data.get("journalName") or "N/A"
            return ((score_str, homepage, s2_journal_name), log_info)
        else:
            log_info["error_message"] = "API는 성공했으나, 응답 데이터에 결과가 없습니다."
            return (("N/A", "#", "결과 없음"), log_info)
            
    except requests.exceptions.HTTPError as http_err:
        log_info["error_message"] = f"HTTP 에러 발생: {http_err}"
    except requests.exceptions.RequestException as req_err:
        log_info["error_message"] = f"네트워크/요청 에러 발생: {req_err}"
    except Exception as e:
        log_info["error_message"] = f"알 수 없는 에러 발생: {e}"

    return (("API 오류", "#", "N/A"), log_info)


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
st.title("🛠️ Scholar 검색기 (API 디버거 포함)")
st.markdown("Google Scholar 논문을 검색하고, Semantic Scholar API로 저널 정보를 실시간 조회합니다.")

with st.form(key='search_form'):
    keyword = st.text_input("**👉 검색어(Keyword)를 입력하세요**", placeholder="예: large language models")
    num_results = st.number_input("**👉 검색할 논문 수를 선택하세요**", min_value=1, max_value=20, value=5, step=1)
    submit_button = st.form_submit_button(label='🔍 검색 시작')

if submit_button and keyword:
    with st.spinner(f"'{keyword}' 논문 검색 및 S2 API로 저널 정보 조회 중..."):
        search_query = scholarly.search_pubs(keyword)
        results = []
        api_logs = [] # API 로그를 저장할 리스트

        for i, pub in enumerate(search_query):
            if i >= num_results: break
            time.sleep(0.5)
            bib = pub.get('bib', {})
            venue = bib.get('venue', 'N/A')
            
            # API 호출 및 결과와 로그를 함께 받음
            (api_result, log_info) = get_journal_info_from_s2(venue)
            influence_score, journal_homepage, s2_name = api_result
            api_logs.append(log_info) # 로그 저장
            
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
        
        st.success(f"총 {len(results)}개의 검색 결과를 찾았습니다.")
        df = pd.DataFrame(results)
        st.dataframe(
            df, use_container_width=True,
            column_config={
                "논문 링크": st.column_config.LinkColumn("바로가기"),
                "저널 홈페이지": st.column_config.LinkColumn("바로가기")
            }, hide_index=True)
        
        st.markdown("---")
        st.subheader("📥 파일 다운로드")
        col1, col2 = st.columns(2)
        # ... (다운로드 버튼 코드는 동일)
        
        # --- 상세 로그 표시 섹션 ---
        with st.expander("🔍 API 요청 상세 로그 보기 (문제 해결용)"):
            if not api_logs:
                st.info("기록된 로그가 없습니다.")
            else:
                for idx, log in enumerate(api_logs):
                    st.markdown(f"---")
                    st.markdown(f"**#{idx+1} 요청**")
                    st.markdown(f"**- 요청 저널명:** `{log['input_journal']}`")
                    st.markdown(f"**- 상태 코드:** `{log['status_code']}`")
                    
                    if log['error_message'] != "N/A":
                        st.error(f"**- 오류 메시지:** {log['error_message']}")

                    st.markdown("**- 전체 요청 URL:**")
                    st.code(log['request_url'], language='text')

                    st.markdown("**- 서버 원본 응답:**")
                    try:
                        # JSON 형식이라면 예쁘게 출력
                        pretty_json = json.dumps(json.loads(log['raw_response']), indent=2)
                        st.code(pretty_json, language='json')
                    except (json.JSONDecodeError, TypeError):
                        # JSON이 아니면 그냥 텍스트로 출력
                        st.code(log['raw_response'], language='text')

elif submit_button and not keyword:
    st.warning("검색어를 입력해주세요.")
