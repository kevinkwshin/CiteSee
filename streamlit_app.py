import streamlit as st
import pandas as pd
from scholarly import scholarly
import io
from thefuzz import process, fuzz
import os
import numpy as np

# --- 1. 페이지 설정 및 상수 정의 ---
st.set_page_config(
    page_title="논문 검색 다운로더",
    page_icon="📚",
    layout="wide",
)

MAX_RESULTS_LIMIT = 200
MATCH_SCORE_THRESHOLD = 95
TOP_JOURNAL_IF_THRESHOLD = 8.0

JOURNAL_DATA_FILE = 'journal_impact_data_20250619_153150.csv'

# --- 2. 핵심 함수 (데이터 로딩, 매칭, 스타일링) ---
@st.cache_data
def load_journal_db(file_path=JOURNAL_DATA_FILE):
    if not os.path.exists(file_path):
        return None, None
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        df.dropna(subset=['journal_title', 'impact_factor'], inplace=True)
        df['journal_title_upper'] = df['journal_title'].astype(str).str.upper() # 대문자 컬럼 추가

        def convert_if(value):
            if isinstance(value, str) and value.strip() == '<0.1':
                return 0.05
            try:
                return float(value)
            except ValueError:
                return np.nan
        df['impact_factor_numeric'] = df['impact_factor'].apply(convert_if) # 숫자형 IF 컬럼 추가
        df.dropna(subset=['impact_factor_numeric'], inplace=True)
        return df, df['journal_title_upper'].tolist() # 대문자 저널명 리스트 반환
    except Exception as e:
        st.error(f"데이터 파일({file_path}) 로드 오류: {e}")
        return None, None

@st.cache_data
def get_journal_info_with_log(venue_from_scholar, db_df, journal_names_list_upper):
    """
    저널명 매칭을 시도하고, Impact Factor와 함께 매칭 시도 로그를 반환합니다.
    반환: (if_float, db_matched_journal_original_case, scholar_venue_processed, best_db_candidate_upper, score)
    매칭 실패 시 if_float는 np.nan, db_matched_journal_original_case는 "DB 매칭 실패"
    """
    if not venue_from_scholar or db_df is None or not journal_names_list_upper:
        return np.nan, "N/A", str(venue_from_scholar), "N/A", 0

    scholar_venue_processed = str(venue_from_scholar).strip().upper()
    if not scholar_venue_processed:
        return np.nan, "N/A", str(venue_from_scholar), "N/A", 0

    best_db_candidate_upper, score = process.extractOne(scholar_venue_processed, journal_names_list_upper, scorer=fuzz.ratio)

    if score >= MATCH_SCORE_THRESHOLD:
        # 매칭된 대문자 DB 저널명으로 원본 DB 데이터에서 IF와 원본 저널명(대소문자 유지)을 찾음
        matched_row = db_df.loc[db_df['journal_title_upper'] == best_db_candidate_upper]
        if not matched_row.empty:
            if_float = matched_row['impact_factor_numeric'].iloc[0]
            db_matched_journal_original_case = matched_row['journal_title'].iloc[0] # 원본 케이스 저널명
            return if_float, db_matched_journal_original_case, scholar_venue_processed, best_db_candidate_upper, score
        else: # 이 경우는 거의 발생하지 않아야 함
            return np.nan, "DB 조회 오류", scholar_venue_processed, best_db_candidate_upper, score
    else:
        # 매칭 실패 시에도, 가장 유사했던 후보와 점수는 로그용으로 반환
        return np.nan, "DB 매칭 실패", scholar_venue_processed, best_db_candidate_upper, score


def classify_sjr(impact_factor_float):
    if pd.isna(impact_factor_float):
        return "N/A"
    try:
        score = float(impact_factor_float)
        if score >= 1.0: return "우수"
        elif 0.5 <= score < 1.0: return "양호"
        elif 0.2 <= score < 0.5: return "보통"
        else: return "하위"
    except (ValueError, TypeError):
        return "N/A"

def color_sjr_score(val_float_or_str): # 입력이 숫자 또는 "N/A" 또는 "<0.1" 문자열일 수 있음
    if isinstance(val_float_or_str, str):
        if val_float_or_str == "N/A":
            return 'color: grey;'
        elif val_float_or_str == "<0.1":
            score = 0.05
        else: # 숫자로 된 문자열 (예: "8.000")
            try:
                score = float(val_float_or_str)
            except ValueError:
                return 'color: grey;'
    elif pd.isna(val_float_or_str):
        return 'color: grey;'
    else: # float
        score = val_float_or_str

    try:
        if score >= 1.0: color = 'green'
        elif 0.5 <= score < 1.0: color = 'blue'
        elif 0.2 <= score < 0.5: color = 'orange'
        else: color = 'red' # 0.05 (<0.1)도 여기에 포함
        return f'color: {color}; font-weight: bold;'
    except (ValueError, TypeError): # 혹시 모를 다른 타입 에러 방지
        return 'color: grey;'


@st.cache_data
def convert_df_to_csv(df: pd.DataFrame):
    df_copy = df.copy()
    for col in df_copy.columns:
        df_copy[col] = df_copy[col].astype(str)
    return df_copy.to_csv(index=False).encode('utf-8-sig')


# --- 3. UI 본문 구성 ---
st.title("📚 논문 검색 및 정보 다운로더")
st.markdown(f"""
Google Scholar에서 논문을 검색하고, Impact Factor를 함께 조회합니다. (최대 **{MAX_RESULTS_LIMIT}개**까지 표시)

**저널명 매칭:** Google Scholar의 저널명과 내부 DB의 저널명 (모두 **대문자로 변환 후 비교**) 간 유사도 점수가 **{MATCH_SCORE_THRESHOLD}% 이상**일 경우에만 Impact Factor를 표시합니다.
**🏆 Top 저널 기준:** Impact Factor **{TOP_JOURNAL_IF_THRESHOLD}점 이상**인 저널.
""")

db_df, journal_names_upper_list = load_journal_db() # 이제 journal_names_upper_list는 대문자
if db_df is None:
    st.error(f"⚠️ `{JOURNAL_DATA_FILE}` 파일을 찾을 수 없습니다. 앱과 동일한 폴더에 해당 파일이 있는지 확인해주세요.")
else:
    st.success(f"✅ 총 {len(db_df):,}개의 저널 정보가 담긴 데이터베이스를 성공적으로 로드했습니다. (저널명은 대문자로 통일하여 매칭)")

    with st.expander("💡 결과 테이블 해석 가이드 보기"):
        st.markdown(f"""
        - **🏆 Top 저널**: Impact Factor가 {TOP_JOURNAL_IF_THRESHOLD}점 이상인 경우 표시됩니다.
        - **저널명 (검색결과)**: Google Scholar에서 가져온 원본 저널명입니다.
        - **DB 저널명 (매칭시)**: DB에서 매칭된 저널명(원본 대소문자)입니다. 매칭 실패 시 "DB 매칭 실패"로 표시됩니다.
        - **매칭 점수**: Google Scholar 저널명(대문자화)과 DB 저널명(대문자화) 간의 유사도입니다.
        - **Impact Factor 등급**: 우수(IF >= 1.0), 양호(0.5 <= IF < 1.0), 보통(0.2 <= IF < 0.5), 하위(IF < 0.2)
        """)

    with st.form(key='search_form'):
        st.subheader("🔍 검색 조건 입력")
        col1, col2 = st.columns(2)
        with col1:
            author = st.text_input("저자 (선택 사항)", placeholder="예: Hinton G")
        with col2:
            keyword = st.text_input("키워드 (선택 사항)", placeholder="예: deep learning")

        only_if_found = st.checkbox("Impact Factor 정보가 있는 저널만 찾기 (DB에서 매칭되는 저널만 표시)", value=True)

        submit_button = st.form_submit_button(label='검색 시작')

    if submit_button and (author or keyword):
        query_parts = []
        if keyword: query_parts.append(keyword)
        if author: query_parts.append(f'author:"{author}"')
        query = " ".join(query_parts)

        failed_matches_log = [] # 매칭 실패 로그를 저장할 리스트

        with st.spinner(f"'{query}' 조건으로 논문을 검색 중입니다..."):
            try:
                search_query = scholarly.search_pubs(query)
                results = []
                for i, pub in enumerate(search_query):
                    if i >= MAX_RESULTS_LIMIT:
                        st.info(f"검색 결과가 많아 최대 {MAX_RESULTS_LIMIT}개까지만 표시합니다.")
                        break

                    bib = pub.get('bib', {})
                    venue_from_scholar = bib.get('venue', 'N/A')

                    if_float, db_matched_journal_original, scholar_venue_processed, best_db_candidate, score_val = get_journal_info_with_log(
                        venue_from_scholar, db_df, journal_names_upper_list
                    )

                    # 상세 로그 기록 (점수가 0보다 크고 임계값 미만인 경우)
                    if pd.isna(if_float) and score_val > 0 and score_val < MATCH_SCORE_THRESHOLD :
                        failed_matches_log.append({
                            "논문 제목": bib.get('title', 'N/A')[:50] + "...", # 너무 길면 자르기
                            "GS 저널명 (원본)": venue_from_scholar,
                            "GS 저널명 (처리됨)": scholar_venue_processed,
                            "DB 최유사 후보 (처리됨)": best_db_candidate,
                            "유사도 점수": score_val
                        })
                    
                    if only_if_found and pd.isna(if_float):
                        continue
                    
                    top_journal_icon = ""
                    if not pd.isna(if_float) and if_float >= TOP_JOURNAL_IF_THRESHOLD:
                        top_journal_icon = "🏆"
                    
                    results.append({
                        "Top 저널": top_journal_icon,
                        "제목 (Title)": bib.get('title', 'N/A'),
                        "저자 (Authors)": ", ".join(bib.get('author', ['N/A'])),
                        "연도 (Year)": bib.get('pub_year', 'N/A'),
                        "저널명 (검색결과)": venue_from_scholar,
                        "DB 저널명 (매칭시)": db_matched_journal_original,
                        "매칭 점수 (%)": score_val if score_val > 0 else "N/A",
                        "_Impact Factor_numeric": if_float, # 숫자형 IF는 내부 계산용으로 숨김 (또는 다른 이름)
                        "Impact Factor": f"{if_float:.3f}" if not pd.isna(if_float) and if_float != 0.05 else ("<0.1" if if_float == 0.05 else "N/A"),
                        "피인용 수": pub.get('num_citations', 0),
                        "논문 링크": pub.get('pub_url', '#'),
                    })

                if not results:
                    st.warning("조건에 맞는 논문이 없습니다. (필터를 해제하거나 다른 키워드를 시도해보세요)")
                else:
                    subheader_text = f"📊 검색 결과 ({len(results)}개)"
                    if only_if_found:
                        subheader_text += " - Impact Factor 정보가 있는 저널만 필터링됨"
                    st.subheader(subheader_text)

                    df_results = pd.DataFrame(results)
                    df_results['IF 등급'] = df_results['_Impact Factor_numeric'].apply(classify_sjr) # 숫자형 IF로 등급 계산
                    
                    df_display = df_results[[
                        "Top 저널", "제목 (Title)", "저자 (Authors)", "연도 (Year)",
                        "저널명 (검색결과)", "DB 저널명 (매칭시)", "Impact Factor", "IF 등급",
                        "피인용 수", "매칭 점수 (%)", "논문 링크"
                    ]]

                    st.dataframe(
                        df_display.style.applymap(color_sjr_score, subset=['Impact Factor']),
                        use_container_width=True,
                        column_config={"논문 링크": st.column_config.LinkColumn("바로가기", display_text="🔗 Link")},
                        hide_index=True
                    )

                    csv_data = convert_df_to_csv(df_display)
                    st.download_button(
                        label="📄 결과 CSV 파일로 다운로드",
                        data=csv_data,
                        file_name=f'search_{query.replace(" ", "_").replace(":", "")}.csv',
                        mime='text/csv'
                    )
                
                # 매칭 실패 로그 표시
                if failed_matches_log:
                    st.subheader("⚠️ 저널명 매칭 실패 상세 로그 (유사도 > 0점, 임계값 미만)")
                    st.caption(f"아래는 Impact Factor를 찾지 못했으나, DB에서 어느 정도 유사한 저널을 찾았던 경우입니다. (현재 매칭 임계값: {MATCH_SCORE_THRESHOLD}%)")
                    df_failed_log = pd.DataFrame(failed_matches_log)
                    st.dataframe(df_failed_log, use_container_width=True, hide_index=True)

            except Exception as e:
                st.error(f"검색 중 오류가 발생했습니다: {e}")
                st.exception(e)
    elif submit_button and not (author or keyword):
        st.warning("저자 또는 키워드 중 하나 이상을 입력해야 합니다.")
