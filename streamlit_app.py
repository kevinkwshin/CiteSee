import streamlit as st
import pandas as pd
from scholarly import scholarly
import io
from thefuzz import process, fuzz
import os
import numpy as np # numpy 추가

# --- 1. 페이지 설정 및 상수 정의 ---
st.set_page_config(
    page_title="논문 검색 다운로더",
    page_icon="📚",
    layout="wide",
)

MAX_RESULTS_LIMIT = 200
MATCH_SCORE_THRESHOLD = 95 # 저널명 매칭 임계값
TOP_JOURNAL_IF_THRESHOLD = 8.0 # Top 저널 IF 기준

JOURNAL_DATA_FILE = 'journal_impact_data_20250619_153150.csv'

# --- 2. 핵심 함수 (데이터 로딩, 매칭, 스타일링) ---
@st.cache_data
def load_journal_db(file_path=JOURNAL_DATA_FILE):
    if not os.path.exists(file_path):
        return None, None
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
        # 필수 컬럼 결측치 처리
        df.dropna(subset=['journal_title', 'impact_factor'], inplace=True)

        # journal_title을 대문자로 변환 및 문자열로 통일
        df['journal_title'] = df['journal_title'].astype(str).str.upper()

        # impact_factor 처리: '<0.1'을 0.05로, 그 외 숫자로 변환, 변환 불가 시 NaN
        def convert_if(value):
            if isinstance(value, str) and value.strip() == '<0.1':
                return 0.05
            try:
                return float(value)
            except ValueError:
                return np.nan # 숫자로 변환할 수 없는 경우 NaN 처리

        df['impact_factor'] = df['impact_factor'].apply(convert_if)
        df.dropna(subset=['impact_factor'], inplace=True) # IF 변환 후 NaN이 된 행 제거

        return df, df['journal_title'].tolist() # journal_names_list는 이제 모두 대문자
    except Exception as e:
        st.error(f"데이터 파일({file_path}) 로드 오류: {e}")
        return None, None

@st.cache_data
def get_journal_info(venue_from_scholar, db_df, journal_names_list_upper):
    """
    주어진 저널명(venue_from_scholar)을 DB와 매칭하여 Impact Factor 등의 정보를 반환합니다.
    DB의 저널명 리스트(journal_names_list_upper)는 이미 대문자로 변환되어 있어야 합니다.
    반환값: (impact_factor_float, matched_db_journal_name_upper, match_score)
    매칭 실패 시: (np.nan, "DB 매칭 실패", score)
    """
    if not venue_from_scholar or db_df is None or not journal_names_list_upper:
        return np.nan, "N/A", 0

    processed_venue = str(venue_from_scholar).strip().upper() # Google Scholar 저널명도 대문자로
    if not processed_venue:
        return np.nan, "N/A", 0

    # journal_names_list_upper (DB 저널명 리스트)는 이미 대문자
    match_upper, score = process.extractOne(processed_venue, journal_names_list_upper, scorer=fuzz.ratio)

    if score >= MATCH_SCORE_THRESHOLD:
        # match_upper (DB의 대문자 저널명)를 사용하여 Impact Factor 조회
        impact_factor_series = db_df.loc[db_df['journal_title'] == match_upper, 'impact_factor']
        if not impact_factor_series.empty:
            impact_factor_value = impact_factor_series.iloc[0]
            # load_journal_db에서 이미 float으로 변환했으므로 바로 반환
            return impact_factor_value, match_upper, score
        else:
            return np.nan, "DB 조회 오류", score
    else:
        return np.nan, "DB 매칭 실패", score

def classify_sjr(impact_factor_float): # 입력값을 float으로 가정
    if pd.isna(impact_factor_float): # np.nan 또는 None인 경우
        return "N/A"
    try:
        score = float(impact_factor_float) # 이미 float일 수 있지만, 안전하게 변환
        if score >= 1.0: return "우수"
        elif 0.5 <= score < 1.0: return "양호"
        elif 0.2 <= score < 0.5: return "보통"
        else: return "하위" # 0.05와 같은 값도 여기에 포함
    except (ValueError, TypeError):
        return "N/A"

def color_sjr_score(val_float): # 입력값을 float 또는 NaN으로 가정
    if pd.isna(val_float):
        return 'color: grey;'
    try:
        score = float(val_float)
        if score >= 1.0: color = 'green'
        elif 0.5 <= score < 1.0: color = 'blue'
        elif 0.2 <= score < 0.5: color = 'orange'
        else: color = 'red'
        return f'color: {color}; font-weight: bold;'
    except (ValueError, TypeError):
        return 'color: grey;'

@st.cache_data
def convert_df_to_csv(df: pd.DataFrame):
    # IF가 숫자가 아닌 경우 (예: NaN을 문자열 "N/A"로 바꾼 후)를 대비해 모든 값을 문자열로 변환 후 저장
    df_copy = df.copy()
    for col in df_copy.columns:
        if df_copy[col].dtype == 'object': # 문자열로 변환된 숫자형 컬럼 등이 있을 수 있으므로 안전하게 처리
            df_copy[col] = df_copy[col].astype(str)
    return df_copy.to_csv(index=False).encode('utf-8-sig')


# --- 3. UI 본문 구성 ---
st.title("📚 논문 검색 및 정보 다운로더")
st.markdown(f"""
Google Scholar에서 논문을 검색하고, Impact Factor를 함께 조회합니다. (최대 **{MAX_RESULTS_LIMIT}개**까지 표시)

**저널명 매칭 정확도:** Google Scholar의 저널명과 내부 DB의 저널명(모두 대문자로 변환 후 비교) 간 유사도 점수가 **{MATCH_SCORE_THRESHOLD}% 이상**일 경우에만 Impact Factor를 표시합니다.
**🏆 Top 저널 기준:** Impact Factor **{TOP_JOURNAL_IF_THRESHOLD}점 이상**인 저널.
""")

db_df, journal_names_upper = load_journal_db() # journal_names_upper는 대문자화된 리스트
if db_df is None:
    st.error(f"⚠️ `{JOURNAL_DATA_FILE}` 파일을 찾을 수 없습니다. 앱과 동일한 폴더에 해당 파일이 있는지 확인해주세요.")
else:
    st.success(f"✅ 총 {len(db_df):,}개의 저널 정보가 담긴 데이터베이스를 성공적으로 로드했습니다.")

    with st.expander("💡 결과 테이블 해석 가이드 보기"):
        st.markdown(f"""
        - **🏆 Top 저널**: Impact Factor가 {TOP_JOURNAL_IF_THRESHOLD}점 이상인 경우 표시됩니다.
        - **매칭 점수**: Google Scholar의 저널명과 DB의 저널명(모두 대문자화 후 비교) 간의 유사도입니다. ({MATCH_SCORE_THRESHOLD}% 이상일 때 DB 정보 표시)
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
                    venue_from_scholar = bib.get('venue', 'N/A')

                    impact_factor_float, matched_db_journal_name_upper, match_score_val = get_journal_info(
                        venue_from_scholar, db_df, journal_names_upper
                    )

                    if only_high_impact and pd.isna(impact_factor_float):
                        continue
                    
                    # Top 저널 아이콘: IF가 숫자이고 기준점 이상일 때
                    top_journal_icon = ""
                    if not pd.isna(impact_factor_float) and impact_factor_float >= TOP_JOURNAL_IF_THRESHOLD:
                        top_journal_icon = "🏆"
                    
                    results.append({
                        "Top 저널": top_journal_icon,
                        "제목 (Title)": bib.get('title', 'N/A'),
                        "저자 (Authors)": ", ".join(bib.get('author', ['N/A'])),
                        "연도 (Year)": bib.get('pub_year', 'N/A'),
                        "저널명 (검색결과)": venue_from_scholar,
                        "DB 저널명 (매칭시)": matched_db_journal_name_upper,
                        "매칭 점수 (%)": match_score_val if match_score_val > 0 else "N/A",
                        "Impact Factor": impact_factor_float if not pd.isna(impact_factor_float) else "N/A", # NaN이면 "N/A" 문자열로
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
                    # 'Impact Factor' 컬럼이 문자열 "N/A"를 포함할 수 있으므로, 등급 분류 전에 숫자형으로 다시 시도
                    # get_journal_info에서 이미 float 또는 np.nan으로 반환하므로, df_results['Impact Factor']를 바로 사용 가능
                    df_results['IF 등급'] = df_results['Impact Factor'].apply(
                        lambda x: classify_sjr(x) if x != "N/A" else "N/A"
                    )
                    
                    # Impact Factor를 표시용 문자열로 변환 (소수점 3자리 또는 "N/A")
                    df_display = df_results.copy()
                    df_display['Impact Factor'] = df_display['Impact Factor'].apply(
                        lambda x: f"{x:.3f}" if isinstance(x, float) and not pd.isna(x) and x != 0.05 else ("<0.1" if x==0.05 else "N/A")
                    )


                    df_display = df_display[[
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

                    csv_data = convert_df_to_csv(df_display) # 표시용 데이터프레임 사용
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
