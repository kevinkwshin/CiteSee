import requests
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm
import time
import random
import csv

def scrape_scimago_data(max_pages=300):
    base_url = "https://www.scimagojr.com/journalrank.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9,ko-KR;q=0.8,ko;q=0.7",
    }
    journal_data = []
    
    print(f"Scimago Journal Rank에서 상위 {max_pages * 50}개 저널 데이터를 스크레이핑합니다...")

    for page in tqdm(range(1, max_pages + 1), desc="페이지 스크레이핑 중"):
        params = {'page': page}
        try:
            response = requests.get(base_url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            table = soup.select_one("div.table_wrap > table")
            if not table: break
                
            tbody = table.find('tbody')
            if not tbody: continue

            rows = tbody.find_all('tr')
            if not rows: break

            for row in rows:
                cols = row.find_all('td')
                if len(cols) > 4:
                    title = cols[1].find('a').text.strip()
                    sjr_value_str = cols[3].text.strip()

                    # =================================================================
                    # ⭐️⭐️⭐️ SJR 점수 칸이 비어있는 경우를 처리하는 로직 추가! ⭐️⭐️⭐️
                    # =================================================================
                    if not sjr_value_str:
                        # 점수 칸이 비어있으면, 이 행은 건너뛰고 다음 행으로 넘어감
                        continue
                    # =================================================================

                    numeric_part = sjr_value_str.split(' ')[0]
                    sjr_float = float(numeric_part.replace(',', '.'))
                    journal_data.append({"FullName": title, "ImpactFactor": sjr_float})
            
            time.sleep(random.uniform(1.5, 3.0))

        except requests.exceptions.RequestException as e:
            print(f"\n❌ 네트워크 또는 HTTP 오류 발생: {e}")
            break
        except Exception as e:
            # 이제 이 오류는 발생하지 않아야 합니다.
            print(f"\n❌ 데이터 처리 중 예상치 못한 오류 발생: {e}")
            break

    return pd.DataFrame(journal_data)

if __name__ == "__main__":
    TOTAL_PAGES_TO_SCRAPE = 300
    scraped_df = scrape_scimago_data(max_pages=TOTAL_PAGES_TO_SCRAPE) 
    
    if scraped_df is not None and not scraped_df.empty:
        output_filename = "journal_if_data.csv"
        scraped_df.to_csv(output_filename, index=False, encoding='utf-8-sig', quoting=csv.QUOTE_MINIMAL)
        print(f"\n✅ 성공! 총 {len(scraped_df)}개의 저널 데이터를 '{output_filename}' 파일로 저장했습니다.")
    else:
        print("\n스크레이핑에 실패하여 파일을 생성하지 않았습니다.")
