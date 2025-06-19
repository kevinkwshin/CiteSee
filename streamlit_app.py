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
MATCH_SCORE_THRESHOLD = 95 # 저널명 매칭 임계값을 95로 상향 조정 (더 엄격한 매칭)

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
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        df.dropna(subset=['journal_title', 'impact_factor'], inplace=True)
        # journal_title을 문자열로 명시적 변환 (혹시 모를 숫자형 저널명 방지)
        df['journal_title'] = df['journal_title'].astype(str)
        return df, df['journal_title'].tolist()
    except Exception as e:
        st.error(f"데이터 파일({file_path}) 로드 오류: {e}")
        return None, None

@st.cache_data
def get_journal_info(venue, db_df, journal_names_list):
    if not venue or db_df is None or not journal_names_list:
        return "N/A", "N/A", 0

    # Google Scholar 저널명 전처리 (옵션): 양쪽 공백 제거, 소문자화
    # 이는 DB의 journal_names_list도 동일하게 전처리되었을 때 효과적입니다.
    # 여기서는 DB의 journal_title이 대부분 대문자이므로, venue도 대문자로 통일합니다.
    processed_venue = str(venue).strip().upper()
    if not processed_venue: # 전처리 후 빈 문자열이 되면 매칭 불가
        return "N/A", "N/A", 0

    # TheFuzz를 사용하여 가장 유사한 저널명 찾기
    # journal_names_list는 이미 대문자 위주일 것이므로, processed_venue와 비교
    match, score = process.extractOne(processed_venue, journal_names_list, scorer=fuzz.ratio) # scorer를 ratio로 변경 (단순 유사도)

    # 점수가 임계값 이상인 경우에만 정보 반환
    if score >= MATCH_SCORE_THRESHOLD:
        # 찾은 match(DB의 저널명)를 사용하여 Impact Factor 조회
        # db_df['journal_title']도 대문자로 일관성 있게 비교 (load_journal_db에서 이미 대문자로 통일했다면 필요 없음)
        # 여기서는 journal_names_list가 db_df['journal_title']에서 왔으므로 match는 DB의 원본 형태를 가짐
        impact_factor_series = db_df.loc[db_df['journal_title'] == match, 'impact_factor']
        if not impact_factor_series.empty:
            impact_factor_value = impact_factor_series.iloc[0]
            if isinstance(impact_factor_value, (int, float)):
                return f"{impact_factor_value:.3f}", match, score
            else: # '<0.1'과 같은 문자열 값 처리
                return str(impact_factor_value), match, score
        else: # 이론적으로는 extractOne이 journal_names_list에서 찾으므로 이 경우는 드물지만, 안전장치
            return "N/A", "DB 조회 실패", score
    else:
        return "N/A", "매칭 실패", score


def classify_sjr(sjr_score_str):
    if sjr_score_str == "N/A" or sjr_score_str == "<0.1":
        return "N/A"
    try:
        score = float(sjr_score_str)
        if score >= 1.0: return "우수"
        elif 0.5 <= score < 1.0: return "양호"
        elif 0.2 <= score < 0.5: return "보통"
        else: return "하위"
    except (ValueError, TypeError):
        return "N/A"

def color_sjr_score(val):
    try:
        if val == "<0.1":
            score = 0.05
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
st.markdown(f"""
Google Scholar에서 논문을 검색하고, Impact Factor를 함께 조회합니다. (최대 **{MAX_RESULTS_LIMIT}개**까지 표시)

**저널명 매칭 정확도:** Google Scholar의 저널명과 내부 DB의 저널명 간 유사도 점수가 **{MATCH_SCORE_THRESHOLD}% 이상**일 경우에만 Impact Factor를 표시합니다.
""")

db_df, journal_names = load_journal_db()
if db_df is None:
    st.error(f"⚠️ `{JOURNAL_DATA_FILE}` 파일을 찾을 수 없습니다. 앱과 동일한 폴더에 해당 파일이 있는지 확인해주세요.")
else:
    st.success(f"✅ 총 {len(db_df):,}개의 저널 정보가 담긴 데이터베이스를 성공적으로 로드했습니다.")

    with st.expander("💡 결과 테이블 해석 가이드 보기"):
        st.markdown(f"""
        - **🏆 Top 저널**: `{', '.join(list(TOP_JOURNALS)[:3])}` 등 세계 최상위 저널을 특별히 표시합니다. (DB에 해당 저널이 있고, 매칭된 경우)
        - **매칭 점수**: Google Scholar의 저널명과 DB의 저널명 간의 유사도입니다. (현재 {MATCH_SCORE_THRESHOLD}% 이상 매칭)
        - **Impact Factor 등급**: 우수(IF >= 1.0), 양호(0.5 <= IF < 1.0), 보통(0.2 <= IF < 0.5), 하위(IF < 0.2)
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
                    venue = bib.get('venue', 'N/A')

                    if not isinstance(venue, str) or not venue.strip():
                        impact_factor, matched_name, match_score = "N/A", "N/A", 0
                    else:
                        impact_factor, matched_name, match_score = get_journal_info(venue, db_df, journal_names)

                    if only_high_impact and impact_factor == "N/A":
                        continue

                    top_journal_icon = "🏆" if matched_name in TOP_JOURNALS else ""

                    results.append({
                        "Top 저널": top_journal_icon,
                        "제목 (Title)": bib.get('title', 'N/A'),
                        "저자 (Authors)": ", ".join(bib.get('author', ['N/A'])),
                        "연도 (Year)": bib.get('pub_year', 'N/A'),
                        "검색된 저널명 (축약)": venue,
                        "매칭된 저널명 (DB)": matched_name,
                        "매칭 점수 (%)": match_score if match_score > 0 else "N/A", # 0점은 N/A로 표시
                        "Impact Factor": impact_factor,
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
                    df_results['IF 등급'] = df_results['Impact Factor'].apply(classify_sjr)
                    df_results = df_results[[
                        "Top 저널", "제목 (Title)", "저자 (Authors)", "연도 (Year)",
                        "매칭된 저널명 (DB)", "Impact Factor", "IF 등급",
                        "피인용 수", "매칭 점수 (%)", "검색된 저널명 (축약)", "논문 링크"
                    ]]

                    st.dataframe(
                        df_results.style.applymap(color_sjr_score, subset=['Impact Factor']),
                        use_container_width=True,
                        column_config={"논문 링크": st.column_config.LinkColumn("바로가기", display_text="🔗 Link")},
                        hide_index=True
                    )

                    csv_data = convert_df_to_csv(df_results)
                    st.download_button(
                        label="📄 결과 CSV 파일로 다운로드",
                        data=csv_data,
                        file_name=f'search_{query.replace(" ", "_").replace(":", "")}.csv',
                        mime='text/csv'
                    )
            except Exception as e:
                st.error(f"검색 중 오류가 발생했습니다: {e}")
                st.exception(e)
    elif submit_button and not (author or keyword):
        st.warning("저자 또는 키워드 중 하나 이상을 입력해야 합니다.")
