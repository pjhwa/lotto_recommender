import pandas as pd
from collections import Counter
import itertools
import numpy as np
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

def load_lotto_data(file_path):
    try:
        df = pd.read_csv(file_path, encoding='utf-8')
        required_cols = ['첫번째', '두번째', '세번째', '네번째', '다섯번째', '여섯번째']
        if not all(col in df.columns for col in required_cols):
            raise ValueError("CSV 파일에 필요한 컬럼이 없습니다: " + ', '.join(required_cols))
        
        numbers_df = df[required_cols]
        all_numbers = numbers_df.values.flatten()
        if not all(1 <= n <= 45 for n in all_numbers if pd.notna(n)):
            raise ValueError("번호 데이터가 1~45 범위를 벗어났습니다.")
        
        return df, numbers_df, all_numbers
    except Exception as e:
        print(f"파일 로드 오류: {e}")
        sys.exit(1)

def analyze_frequencies(all_numbers, recent_numbers):
    full_freq = Counter(all_numbers)
    recent_freq = Counter(recent_numbers)
    return full_freq, recent_freq

def analyze_statistics(numbers_df):
    all_numbers = numbers_df.values.flatten()
    odds = sum(1 for n in all_numbers if n % 2 == 1)
    evens = len(all_numbers) - odds
    odd_ratio = odds / len(all_numbers)
    
    sums = numbers_df.sum(axis=1)
    sum_mean = np.mean(sums)
    sum_std = np.std(sums)  # 합계 표준편차 추가
    sum_p25, sum_p75 = np.percentile(sums, [25, 75])
    
    consec_count = 0
    for row in numbers_df.itertuples(index=False):
        sorted_row = sorted(row)
        consec = sum(1 for i in range(5) if sorted_row[i+1] - sorted_row[i] == 1)
        consec_count += consec
    avg_consec = consec_count / len(numbers_df)
    
    return odd_ratio, sum_mean, sum_std, sum_p25, sum_p75, avg_consec

def get_past_combinations(numbers_df):
    past_combs = set()
    for row in numbers_df.itertuples(index=False):
        past_combs.add(frozenset(row))
    return past_combs

def generate_recommendations(full_freq, recent_freq, past_combs, sum_mean, sum_std, odd_ratio, avg_consec):
    top_full = [num for num, _ in full_freq.most_common(20)]  # 확대
    top_recent = [num for num, _ in recent_freq.most_common(15)]  # 확대
    candidates = sorted(set(top_full + top_recent))
    
    all_combs = list(itertools.combinations(candidates, 6))
    
    filtered_combs = []
    for comb in all_combs:
        sorted_comb = sorted(comb)
        comb_sum = sum(sorted_comb)
        odd_count = sum(1 for n in sorted_comb if n % 2 == 1)
        consec_pairs = sum(1 for i in range(5) if sorted_comb[i+1] - sorted_comb[i] == 1)
        if (
            abs(comb_sum - sum_mean) <= sum_std * 1.5 and  # 합계 편차 보완 (±1.5 std)
            odd_count in [3, 4] and  # 홀수 필수 3-4
            0 <= consec_pairs <= 2 and  # 연속 확대 (backtest 보완)
            frozenset(sorted_comb) not in past_combs
        ):
            score = 0.7 * sum(full_freq.get(n, 0) for n in sorted_comb) + 0.3 * sum(recent_freq.get(n, 0) for n in sorted_comb)  # 가중 조정
            filtered_combs.append((sorted_comb, score))
    
    filtered_combs.sort(key=lambda x: x[1], reverse=True)
    
    recommendations = [comb for comb, _ in filtered_combs[:5]]
    
    if len(recommendations) < 5:
        print("필터링된 조합 부족: 합계 범위 완화하여 재시도")
        extended_min = sum_mean - sum_std * 2
        extended_max = sum_mean + sum_std * 2
        extended_filtered = []
        for comb in all_combs:
            sorted_comb = sorted(comb)
            comb_sum = sum(sorted_comb)
            odd_count = sum(1 for n in sorted_comb if n % 2 == 1)
            consec_pairs = sum(1 for i in range(5) if sorted_comb[i+1] - sorted_comb[i] == 1)
            if (
                extended_min <= comb_sum <= extended_max and
                odd_count in [3, 4] and
                0 <= consec_pairs <= 2 and
                frozenset(sorted_comb) not in past_combs
            ):
                score = 0.7 * sum(full_freq.get(n, 0) for n in sorted_comb) + 0.3 * sum(recent_freq.get(n, 0) for n in sorted_comb)
                extended_filtered.append((sorted_comb, score))
        extended_filtered.sort(key=lambda x: x[1], reverse=True)
        recommendations = [comb for comb, _ in extended_filtered[:5]]
    
    return recommendations

def backtest_recommendations(df, file_path):
    # 백테스트 로직 (생략, 필요 시 구현 - backtest_log.csv 생성)
    print("백테스트 수행 중... (구현 필요)")
    # 예시: df 분석 후 로그 저장
    # ...

def main():
    backtest_mode = '-b' in sys.argv
    if len(sys.argv) < 2 or (backtest_mode and len(sys.argv) < 3):
        print("사용법: python lotto_recommender.py <csv_file_path> [-b]")
        sys.exit(1)
    
    file_path = sys.argv[1] if not backtest_mode else sys.argv[2]
    
    update_lotto_csv(file_path)
    
    df, numbers_df, all_numbers = load_lotto_data(file_path)
    
    recent_df = df.tail(50)
    recent_numbers = recent_df[['첫번째', '두번째', '세번째', '네번째', '다섯번째', '여섯번째']].values.flatten()
    
    full_freq, recent_freq = analyze_frequencies(all_numbers, recent_numbers)
    odd_ratio, sum_mean, sum_std, sum_p25, sum_p75, avg_consec = analyze_statistics(numbers_df)  # sum_std 추가
    past_combs = get_past_combinations(numbers_df)
    
    if backtest_mode:
        backtest_recommendations(df, file_path)
    else:
        print("=== 로또 데이터 분석 결과 ===")
        print(f"총 회차 수: {len(df)}")
        print(f"전체 번호 빈도 상위 10: {[(int(num), count) for num, count in full_freq.most_common(10)]}")
        print(f"최근 50회 빈도 상위 10: {[(int(num), count) for num, count in recent_freq.most_common(10)]}")
        print(f"홀수 비율: {odd_ratio:.2%}")
        print(f"합계 평균: {sum_mean:.1f}, 표준편차: {sum_std:.1f}, 25%~75% 범위: {sum_p25}~{sum_p75}")
        print(f"평균 연속 쌍 수: {avg_consec:.2f}")
        
        recommendations = generate_recommendations(full_freq, recent_freq, past_combs, sum_mean, sum_std, odd_ratio, avg_consec)
        print("\n=== 추천 번호 조합 (당첨 가능성 높은 5개) ===")
        for i, comb in enumerate(recommendations, 1):
            print(f"{i}. {[int(n) for n in comb]}")

if __name__ == "__main__":
    main()
