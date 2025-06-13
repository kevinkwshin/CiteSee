import requests
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm  # 진행 상황을 보여주기 위한 라이브러리
import time

def scrape_scimago_data(max_pages=10):
    """
    Scimago Journal & Country Rank 웹사이트에서 저널 랭킹 데이터를 스크레이핑합니다.
    SJR 지표를 Impact Factor의 대안으로 사용합니다.
    
    :param max_pages: 스크레이핑할 페이지 수 (1페이지당 50개 저널)
    :return: 저널 이름과 SJR 지표가 담긴 Pandas DataFrame
    """
    base_url = "https://www.scimagojr.com/journalrank.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    journal_data = []
    
    print(f"Scimago Journal Rank에서 상위 {max_pages * 50}개 저널 데이터를 스크레이핑합니다...")

    # tqdm을 사용하여 진행 바 표시
    for page in tqdm(range(1, max_pages + 1), desc="페이지 스크레이핑 중"):
        params = {'page': page, 'total_size': 53000} # 예시 total_size, 실제 값은 바뀔 수 있음
        try:
            response = requests.get(base_url, headers=headers, params=params)
            response.raise_for_status()  # HTTP 오류가 발생하면 예외를 발생시킴
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            table = soup.find('table', class_='tabletable')
            if not table:
                print(f"{page}페이지에서 테이블을 찾을 수 없습니다.")
                continue
                
            rows = table.find('tbody').find_all('tr')
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) > 4:
                    # 데이터 추출
                    title = cols[1].find('a').text.strip()
                    sjr_value = cols[3].text.strip()
                    
                    # SJR 값은 "0,123" 형태이므로 숫자로 변환
                    try:
                        sjr_float = float(sjr_value.replace(',', '.'))
                    except ValueError:
                        sjr_float = 0.0

                    journal_data.append({
                        "FullName": title,
                        "ImpactFactor": sjr_float  # 컬럼명을 ImpactFactor로 통일
                    })
            
            # 서버에 부담을 주지 않기 위해 요청 사이에 딜레이 추가
            time.sleep(1)

        except requests.exceptions.RequestException as e:
            print(f"\n{page}페이지를 가져오는 중 오류 발생: {e}")
            break
        except Exception as e:
            print(f"\n데이터 처리 중 오류 발생: {e}")
            break

    if not journal_data:
        print("데이터를 스크레이핑하지 못했습니다.")
        return None

    df = pd.DataFrame(journal_data)
    return df

if __name__ == "__main__":
    # 상위 20페이지(1000개 저널) 데이터를 스크레이핑
    # 더 많은 데이터가 필요하면 max_pages 값을 늘리세요.
    scraped_df = scrape_scimago_data(max_pages=20) 
    
    if scraped_df is not None and not scraped_df.empty:
        # 결과를 CSV 파일로 저장
        output_filename = "journal_if_data.csv"
        scraped_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
        print(f"\n성공! 총 {len(scraped_df)}개의 저널 데이터를 '{output_filename}' 파일로 저장했습니다.")
    else:
        print("\n스크레이핑에 실패하여 파일을 생성하지 않았습니다.")
