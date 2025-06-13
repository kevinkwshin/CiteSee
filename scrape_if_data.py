import requests
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm
import time
import random
import csv # CSV 저장 방식을 더 명시적으로 제어하기 위해 추가

def scrape_scimago_data(start_page=1, max_pages=10, delay_seconds=2):
    """
    Scimago Journal & Country Rank 웹사이트에서 저널 랭킹 데이터를 스크레이핑합니다.
    SJR 지표를 Impact Factor의 대안으로 사용합니다.

    :param start_page: 스크레이핑을 시작할 페이지 번호
    :param max_pages: 스크레이핑할 최대 페이지 수 (1페이지당 50개 저널)
    :param delay_seconds: 각 요청 사이의 평균 대기 시간 (IP 차단 방지)
    :return: 저널 이름과 SJR 지표가 담긴 Pandas DataFrame
    """
    base_url = "https://www.scimagojr.com/journalrank.php"
    # User-Agent를 다양하게 설정하여 차단 위험을 줄입니다.
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    }
    
    journal_data = []
    
    print(f"Scimago Journal Rank에서 {start_page}페이지부터 총 {max_pages}개 페이지의 데이터를 스크레이핑합니다...")
    print(f"예상 소요 시간: 약 {max_pages * delay_seconds / 60:.1f} 분")

    for page in tqdm(range(start_page, start_page + max_pages), desc="페이지 스크레이핑 중"):
        params = {'page': page}
        try:
            response = requests.get(base_url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', class_='tabletable')
            if not table:
                print(f"\n{page}페이지에서 테이블을 찾을 수 없습니다. 중단합니다.")
                break
                
            rows = table.find('tbody').find_all('tr')
            if not rows:
                print(f"\n{page}페이지에 데이터가 없습니다. 마지막 페이지일 수 있습니다.")
                break

            for row in rows:
                cols = row.find_all('td')
                if len(cols) > 4:
                    title = cols[1].find('a').text.strip()
                    sjr_value_str = cols[3].text.strip()
                    
                    try:
                        # SJR 값 "0,123"을 숫자 0.123으로 변환
                        sjr_float = float(sjr_value_str.replace(',', '.'))
                    except ValueError:
                        sjr_float = 0.0

                    journal_data.append({
                        "FullName": title,
                        "ImpactFactor": sjr_float
                    })
            
            # IP 차단을 피하기 위해 랜덤한 딜레이를 줍니다.
            sleep_time = delay_seconds + random.uniform(0, 1)
            time.sleep(sleep_time)

        except requests.exceptions.RequestException as e:
            print(f"\n{page}페이지를 가져오는 중 오류 발생: {e}")
            print("네트워크 문제일 수 있습니다. 잠시 후 다시 시도해주세요.")
            break
        except Exception as e:
            print(f"\n{page}페이지 데이터 처리 중 예상치 못한 오류 발생: {e}")
            break

    if not journal_data:
        print("스크레이핑된 데이터가 없습니다.")
        return None

    df = pd.DataFrame(journal_data)
    return df

def save_to_csv_safely(df, filename="journal_if_data.csv"):
    """
    쉼표(,)가 포함된 데이터를 안전하게 CSV로 저장합니다.
    Pandas의 to_csv는 기본적으로 이 처리를 잘 해주지만, 명시적으로 quoting 옵션을 사용합니다.
    """
    print(f"\n'{filename}' 파일로 저장 중...")
    # quoting=csv.QUOTE_NONNUMERIC은 숫자가 아닌 모든 필드를 따옴표로 감쌉니다.
    # QUOTE_MINIMAL은 쉼표 등 특수문자가 포함된 필드만 감싸는 기본값입니다.
    df.to_csv(filename, index=False, encoding='utf-8-sig', quoting=csv.QUOTE_MINIMAL)
    print("저장 완료!")


if __name__ == "__main__":
    # ==================================================================
    # 여기서 스크레이핑할 페이지 수를 조절하세요.
    # 1페이지당 50개 저널입니다.
    # 예: 200페이지 = 10,000개 저널 (약 7분 소요)
    # 400페이지 = 20,000개 저널 (약 14분 소요)
    # ==================================================================
    TOTAL_PAGES_TO_SCRAPE = 200 
    
    scraped_df = scrape_scimago_data(max_pages=TOTAL_PAGES_TO_SCRAPE) 
    
    if scraped_df is not None and not scraped_df.empty:
        print(f"\n성공! 총 {len(scraped_df)}개의 저널 데이터를 수집했습니다.")
        save_to_csv_safely(scraped_df)
    else:
        print("\n스크레이핑에 실패하여 파일을 생성하지 않았습니다.")
