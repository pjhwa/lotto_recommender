import pandas as pd
import sys
import re
import requests
from bs4 import BeautifulSoup
import time  # 로딩 지연 대응 추가

def fetch_latest_lotto():
    """동행복권 사이트에서 최신 로또 데이터 확인"""
    try:
        url = "https://dhlottery.co.kr/gameResult.do?method=byWin"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)  # timeout 증가
        response.raise_for_status()
        # 로딩 지연 대응 (1초 대기)
        time.sleep(1)
        soup = BeautifulSoup(response.text, 'html.parser')
        # 회차 추출 (fallback 추가: ID 못 찾으면 대체 클래스 검색)
        round_elem = soup.find('strong', id='lottoDrwNo')
        if not round_elem:
            # fallback: 클래스나 텍스트 기반 검색
            round_elem = soup.find('strong', string=re.compile(r'\d+회'))
            if not round_elem:
                raise ValueError("회차 정보를 찾을 수 없습니다.")
        round_num = int(re.sub(r'[^0-9]', '', round_elem.text.strip()))
        # 추첨일 추출
        date_elem = soup.find('p', class_='desc')
        if not date_elem:
            raise ValueError("추첨일 정보를 찾을 수 없습니다.")
        date_text = date_elem.text.strip()
        date_match = re.search(r'(\d{4})년 (\d{2})월 (\d{2})일', date_text)
        if date_match:
            year = date_match.group(1)
            month = date_match.group(2).zfill(2)  # 08처럼 2자리 패딩
            day = date_match.group(3).zfill(2)  # 30처럼 2자리 패딩
            draw_date = f"{year}-{month}-{day}"  # YYYY-MM-DD 형식 변환
        else:
            raise ValueError("추첨일 형식 파싱 실패.")
        # 본번호 + 보너스 추출 (fallback 추가: 클래스 동적일 경우)
        win_box = soup.find('div', class_='win_result')
        if not win_box:
            raise ValueError("당첨번호 박스를 찾을 수 없습니다.")
        numbers_spans = win_box.find_all('span', class_='ball_645')
        if not numbers_spans:
            # fallback: 모든 span 검색 후 필터
            numbers_spans = [span for span in win_box.find_all('span') if 'ball_645' in span.get('class', [])]
        if len(numbers_spans) < 7:
            raise ValueError(f"번호 개수 부족: {len(numbers_spans)}개 발견.")
        main_numbers = sorted([int(span.text) for span in numbers_spans[:6]])
        bonus = int(numbers_spans[6].text)
        # 1등 당첨자 수 추출 (fallback 추가: 테이블 구조 변화 대응)
        winner_table = soup.find('table', class_='tbl_data tbl_data_col')
        if not winner_table:
            winner_table = soup.find('table', attrs={'summary': re.compile('당첨금 지급기한 및 1등 당첨자 배출점')})
            if not winner_table:
                raise ValueError("당첨자 테이블을 찾을 수 없습니다.")
        rows = winner_table.find_all('tr')
        if len(rows) < 2:
            raise ValueError("당첨자 테이블 행 부족.")
        winner_count_str = rows[1].find_all('td')[2].text.strip()
        winner_count = int(re.sub(r'[^0-9]', '', winner_count_str))
        return round_num, draw_date, main_numbers[0], main_numbers[1], main_numbers[2], main_numbers[3], main_numbers[4], main_numbers[5], bonus, winner_count
    except Exception as e:
        print(f"오류 발생: {e}. 사이트 구조가 변경되었을 수 있습니다. 직접 사이트를 확인하세요: https://dhlottery.co.kr/gameResult.do?method=byWin")
        return None

def update_lotto_csv(file_path):
    latest_data = fetch_latest_lotto()
    if latest_data is None:
        return

    round_num, draw_date, n1, n2, n3, n4, n5, n6, bonus, winner_count = latest_data

    try:
        df = pd.read_csv(file_path, encoding='utf-8')
    except FileNotFoundError:
        df = pd.DataFrame(columns=['회차', '추첨일', '첫번째', '두번째', '세번째', '네번째', '다섯번째', '여섯번째', '보너스', '1등 당첨자 수'])

    # 마지막 회차 확인
    max_round = df['회차'].max() if not df.empty else 0

    if round_num > max_round:
        new_row = pd.DataFrame([{
            '회차': round_num,
            '추첨일': draw_date,
            '첫번째': n1,
            '두번째': n2,
            '세번째': n3,
            '네번째': n4,
            '다섯번째': n5,
            '여섯번째': n6,
            '보너스': bonus,
            '1등 당첨자 수': winner_count
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(file_path, index=False, encoding='utf-8')
        print(f"최신 {round_num}회 데이터 추가 완료.")
    else:
        print(f"{round_num}회 이미 존재. 추가 생략.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("사용법: python update_lotto.py <csv_file_path>")
        sys.exit(1)

    file_path = sys.argv[1]
    update_lotto_csv(file_path)
