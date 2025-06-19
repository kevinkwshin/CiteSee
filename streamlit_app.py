import streamlit as st
import pandas as pd
from scholarly import scholarly
import io
from thefuzz import process, fuzz
import os

# --- 1. 페이지 설정 및 상수 정의 ---
st.set_page_config(
    page_title="논문 검색 다운로더",
    page_icon="📚",
    layout="wide",
)

MAX_RESULTS_LIMIT = 200
MATCH_SCORE_THRESHOLD = 85 # 저널명 매칭 임계값

# 제공된 CSV의 journal_title 컬럼 값과 일치하도록 대문자로 변경
TOP_JOURNALS = {
    "NATURE", "SCIENCE", "CELL", "THE LANCET", "NEW ENGLAND JOURNAL OF MEDICINE",
    "CA - A CANCER JOURNAL FOR CLINICIANS", "NATURE REVIEWS MOLECULAR CELL BIOLOGY",
    "NATURE MEDICINE", "THE LANCET NEUROLOGY", "JAMA - JOURNAL OF THE AMERICAN MEDICAL ASSOCIATION"
}
# 제공된 CSV 파일명
JOURNAL_DATA_FILE = 'journal_impact_data_20250619_153150.csv'

# --- 2. 핵심 함수 (데이터 로딩, 매칭, 스타일링) ---
@st.cache_data
def load_journal_db(file_path=JOURNAL_DATA_FILE):
    if not os.path.exists(file_path):
        return None, None
    try:
        # CSV 파일 읽기 시 encoding='utf-8-sig' 추가
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        # journal_title과 impact_factor 컬럼의 결측치 제거
        df.dropna(subset=['journal_title', 'impact_factor'], inplace=True)
        # impact_factor를 숫자로 변환 시도, 변환 불가 시 N/A 또는 0으로 처리 (여기서는 일단 유지)
        # 사용자가 제공한 CSV의 impact_factor 컬럼은 이미 숫자형이거나, pandas가 잘 처리할 것으로 예상
        return df, df['journal_title'].tolist()
    except Exception as e:
        st.error(f"데이터 파일({file_path}) 로드 오류: {e}")
        return None, None

@st.cache_data
def get_journal_info(venue, db_df, journal_names_list):
    if not venue or db_df is None or not journal_names_list:
        return "N/A", "N/A", 0
    
    # venue(검색된 저널명)도 대문자로 변환하여 매칭률 향상 (DB의 journal_title이 대문자 위주이므로)
    match, score = process.extractOne(str(venue).upper(), journal_names_list, scorer=fuzz.token_sort_ratio)
    
    if score >= MATCH_SCORE_THRESHOLD:
        # db_df에서 'journal_title'로 매칭된 행을 찾고, 'impact_factor' 값을 가져옴
        impact_factor_value = db_df.loc[db_df['journal_title'] == match, 'impact_factor'].iloc[0]
        # 숫자인 경우에만 .3f 포맷 적용
        if isinstance(impact_factor_value, (int, float)):
            return f"{impact_factor_value:.3f}", match, score
        else: # <0.1 같은 문자열 값 처리
            return str(impact_factor_value), match, score
            
    else:
        return "N/A", "매칭 실패", score

def classify_sjr(sjr_score_str): # 함수명은 SJR로 되어있지만, 실제로는 Impact Factor를 사용
    if sjr_score_str == "N/A" or sjr_score_str == "<0.1": # "<0.1"도 처리
        return "N/A"
    try:
        score = float(sjr_score_str)
        if score >= 1.0: return "우수"
        elif 0.5 <= score < 1.0: return "양호"
        elif 0.2 <= score < 0.5: return "보통"
        else: return "하위"
    except (ValueError, TypeError):
        return "N/A"

def color_sjr_score(val): # 함수명은 SJR로 되어있지만, 실제로는 Impact Factor를 사용
    try:
        if val == "<0.1": # "<0.1" 특별 처리
            score = 0.05 # 임의의 작은 값으로 처리하여 하위 등급 색상 적용
        else:
            score = float(val)
            
        if score >= 1.0: color = 'green'
        elif 0.5 <= score < 1.0: color = 'blue'
        elif 0.2 <= score < 0.5: color = 'orange'
        else: color = 'red'
        return f'color: {color}; font-weight: bold;'
    except (ValueError, TypeError):
        return 'color: grey;'

@st.cache_data
def convert_df_to_csv(df: pd.DataFrame):
    return df.to_csv(index=False).encode('utf-8-sig')


# --- 3. UI 본문 구성 ---
st.title("📚 논문 검색 및 정보 다운로더")
st.markdown(f"Google Scholar에서 논문을 검색하고, Impact Factor를 함께 조회합니다. (최대 **{MAX_RESULTS_LIMIT}개**까지 표시)")

db_df, journal_names = load_journal_db()
if db_df is None:
    st.error(f"⚠️ `{JOURNAL_DATA_FILE}` 파일을 찾을 수 없습니다. 앱과 동일한 폴더에 해당 파일이 있는지 확인해주세요.")
else:
    st.success(f"✅ 총 {len(db_df):,}개의 저널 정보가 담긴 데이터베이스를 성공적으로 로드했습니다.")
    
    with st.expander("💡 결과 테이블 해석 가이드 보기"):
        st.markdown(f"""
        - **🏆 Top 저널**: `{', '.join(list(TOP_JOURNALS)[:3])}` 등 세계 최상위 저널을 특별히 표시합니다. (DB에 해당 저널이 있는 경우)
        - **매칭 점수**: Google Scholar의 축약된 저널명과 DB의 전체 저널명 간의 유사도입니다.
        - **{MATCH_SCORE_THRESHOLD}% 이상**일 경우에만 Impact Factor 점수를 표시하여 정확도를 높였습니다.
        - Impact Factor 등급: 우수(>=1.0), 양호(0.5~0.999), 보통(0.2~0.499), 하위(<0.2)
        """)

    with st.form(key='search_form'):
        st.subheader("🔍 검색 조건 입력")
        col1, col2 = st.columns(2)
        with col1:
            author = st.text_input("저자 (선택 사항)", placeholder="예: Hinton G")
        with col2:
            keyword = st.text_input("키워드 (선택 사항)", placeholder="예: deep learning")
        
        only_high_impact = st.checkbox("Impact Factor 정보가 있는 저널만 찾기 (DB에서 매칭되는 저널만 표시)", value=True)
        
        submit_button = st.form_submit_button(label='검색 시작')

    if submit_button and (author or keyword):
        query_parts = []
        if keyword: query_parts.append(keyword)
        if author: query_parts.append(f'author:"{author}"')
        query = " ".join(query_parts)

        with st.spinner(f"'{query}' 조건으로 논문을 검색 중입니다..."):
            try:
                search_query = scholarly.search_pubs(query)
                results = []
                for i, pub in enumerate(search_query):
                    if i >= MAX_RESULTS_LIMIT:
                        st.info(f"검색 결과가 많아 최대 {MAX_RESULTS_LIMIT}개까지만 표시합니다.")
                        break
                    
                    bib = pub.get('bib', {})
                    venue = bib.get('venue', 'N/A') # Google Scholar에서 가져온 저널명
                    
                    # venue가 유효한 문자열인지 확인 (간혹 비어있거나 None일 수 있음)
                    if not isinstance(venue, str) or not venue.strip():
                        impact_factor, matched_name, match_score = "N/A", "N/A", 0
                    else:
                        impact_factor, matched_name, match_score = get_journal_info(venue, db_df, journal_names)
                    
                    if only_high_impact and impact_factor == "N/A":
                        continue
                    
                    # TOP_JOURNALS 매칭 시 journal_title (matched_name) 사용
                    top_journal_icon = "🏆" if matched_name in TOP_JOURNALS else ""
                    
                    results.append({
                        "Top 저널": top_journal_icon,
                        "제목 (Title)": bib.get('title', 'N/A'),
                        "저자 (Authors)": ", ".join(bib.get('author', ['N/A'])),
                        "연도 (Year)": bib.get('pub_year', 'N/A'),
                        "검색된 저널명 (축약)": venue,
                        "매칭된 저널명 (DB)": matched_name,
                        "매칭 점수 (%)": match_score,
                        "Impact Factor": impact_factor, # 컬럼명 변경
                        "피인용 수": pub.get('num_citations', 0),
                        "논문 링크": pub.get('pub_url', '#'),
                    })

                if not results:
                    st.warning("조건에 맞는 논문이 없습니다. (필터를 해제하거나 다른 키워드를 시도해보세요)")
                else:
                    subheader_text = f"📊 검색 결과 ({len(results)}개)"
                    if only_high_impact:
                        subheader_text += " - Impact Factor 정보가 있는 저널만 필터링됨"
                    st.subheader(subheader_text)

                    df_results = pd.DataFrame(results)
                    df_results['IF 등급'] = df_results['Impact Factor'].apply(classify_sjr) # SJR -> IF
                    df_results = df_results[[
                        "Top 저널", "제목 (Title)", "저자 (Authors)", "연도 (Year)", 
                        "매칭된 저널명 (DB)", "Impact Factor", "IF 등급", 
                        "피인용 수", "매칭 점수 (%)", "검색된 저널명 (축약)", "논문 링크"
                    ]]
                    
                    st.dataframe(
                        df_results.style.applymap(color_sjr_score, subset=['Impact Factor']), # SJR -> IF
                        use_container_width=True,
                        column_config={"논문 링크": st.column_config.LinkColumn("바로가기", display_text="🔗 Link")},
                        hide_index=True
                    )
                    
                    csv_data = convert_df_to_csv(df_results) # df -> df_results
                    st.download_button(
                        label="📄 결과 CSV 파일로 다운로드",
                        data=csv_data, # 변수 사용
                        file_name=f'search_{query.replace(" ", "_").replace(":", "")}.csv',
                        mime='text/csv'
                    )
            except Exception as e:
                st.error(f"검색 중 오류가 발생했습니다: {e}")
                st.exception(e) # 더 자세한 에러 로깅
    elif submit_button and not (author or keyword):
        st.warning("저자 또는 키워드 중 하나 이상을 입력해야 합니다.")
