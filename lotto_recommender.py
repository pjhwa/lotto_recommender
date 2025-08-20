import pandas as pd
from collections import Counter
import itertools
import numpy as np
import sys

def load_lotto_data(file_path):
    """CSV 파일 로드 및 데이터 검증"""
    try:
        df = pd.read_csv(file_path, encoding='utf-8')
        required_cols = ['첫번째', '두번째', '세번째', '네번째', '다섯번째', '여섯번째']
        if not all(col in df.columns for col in required_cols):
            raise ValueError("CSV 파일에 필요한 컬럼이 없습니다: " + ', '.join(required_cols))
        
        # 번호 데이터 추출 및 검증 (1~45 범위)
        numbers_df = df[required_cols]
        all_numbers = numbers_df.values.flatten()
        if not all(1 <= n <= 45 for n in all_numbers if pd.notna(n)):
            raise ValueError("번호 데이터가 1~45 범위를 벗어났습니다.")
        
        return df, numbers_df, all_numbers
    except Exception as e:
        print(f"파일 로드 오류: {e}")
        sys.exit(1)

def analyze_frequencies(all_numbers, recent_numbers):
    """빈도 분석"""
    full_freq = Counter(all_numbers)
    recent_freq = Counter(recent_numbers)
    return full_freq, recent_freq

def analyze_statistics(numbers_df):
    """통계 분석: 홀/짝, 합계, 연속 패턴"""
    # 홀/짝
    all_numbers = numbers_df.values.flatten()
    odds = sum(1 for n in all_numbers if n % 2 == 1)
    evens = len(all_numbers) - odds
    odd_ratio = odds / len(all_numbers)
    
    # 합계
    sums = numbers_df.sum(axis=1)
    sum_mean = np.mean(sums)
    sum_p25, sum_p75 = np.percentile(sums, [25, 75])
    
    # 연속 쌍 평균
    consec_count = 0
    for row in numbers_df.itertuples(index=False):
        sorted_row = sorted(row)
        consec = sum(1 for i in range(5) if sorted_row[i+1] - sorted_row[i] == 1)
        consec_count += consec
    avg_consec = consec_count / len(numbers_df)
    
    return odd_ratio, sum_mean, sum_p25, sum_p75, avg_consec

def get_past_combinations(numbers_df):
    """과거 당첨 조합 set (중복 확인용)"""
    past_combs = set()
    for row in numbers_df.itertuples(index=False):
        past_combs.add(frozenset(row))
    return past_combs

def generate_recommendations(full_freq, recent_freq, past_combs, sum_p25, sum_p75, avg_consec):
    """추천 조합 생성"""
    # 후보 번호 풀: 전체 상위 15 + 최근 상위 10 (중복 제거)
    top_full = [num for num, _ in full_freq.most_common(15)]
    top_recent = [num for num, _ in recent_freq.most_common(10)]
    candidates = sorted(set(top_full + top_recent))
    
    # 가능한 조합 생성
    all_combs = list(itertools.combinations(candidates, 6))
    
    # 필터링된 조합 리스트
    filtered_combs = []
    for comb in all_combs:
        sorted_comb = sorted(comb)
        comb_sum = sum(sorted_comb)
        odd_count = sum(1 for n in sorted_comb if n % 2 == 1)
        consec_pairs = sum(1 for i in range(5) if sorted_comb[i+1] - sorted_comb[i] == 1)
        if (
            sum_p25 <= comb_sum <= sum_p75 and  # 합계 범위
            odd_count in [3, 4] and  # 홀/짝 균형
            consec_pairs <= 1 and  # 연속 최대 1개
            frozenset(sorted_comb) not in past_combs  # 미출현
        ):
            # 점수 계산: 전체 빈도 + 최근 가중
            score = sum(full_freq.get(n, 0) for n in sorted_comb) + 0.5 * sum(recent_freq.get(n, 0) for n in sorted_comb)
            filtered_combs.append((sorted_comb, score))
    
    # 점수 내림차순 정렬 및 상위 5개 선택
    filtered_combs.sort(key=lambda x: x[1], reverse=True)
    recommendations = [comb for comb, _ in filtered_combs[:5]]
    
    # 부족 시 조건 완화 (합계 범위 확대)
    if len(recommendations) < 5:
        print("필터링된 조합 부족: 합계 범위 완화하여 재시도")
        extended_min = sum_p25 - 20
        extended_max = sum_p75 + 20
        for comb in all_combs:
            sorted_comb = sorted(comb)
            comb_sum = sum(sorted_comb)
            odd_count = sum(1 for n in sorted_comb if n % 2 == 1)
            consec_pairs = sum(1 for i in range(5) if sorted_comb[i+1] - sorted_comb[i] == 1)
            if (
                extended_min <= comb_sum <= extended_max and
                odd_count in [3, 4] and
                consec_pairs <= 1 and
                frozenset(sorted_comb) not in past_combs
            ):
                score = sum(full_freq.get(n, 0) for n in sorted_comb) + 0.5 * sum(recent_freq.get(n, 0) for n in sorted_comb)
                filtered_combs.append((sorted_comb, score))
        filtered_combs.sort(key=lambda x: x[1], reverse=True)
        recommendations = [comb for comb, _ in filtered_combs[:5]]
    
    return recommendations

def main():
    if len(sys.argv) != 2:
        print("사용법: python lotto_recommender.py <csv_file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    df, numbers_df, all_numbers = load_lotto_data(file_path)
    
    # 최근 50회 번호
    recent_df = df.tail(50)
    recent_numbers = recent_df[['첫번째', '두번째', '세번째', '네번째', '다섯번째', '여섯번째']].values.flatten()
    
    full_freq, recent_freq = analyze_frequencies(all_numbers, recent_numbers)
    odd_ratio, sum_mean, sum_p25, sum_p75, avg_consec = analyze_statistics(numbers_df)
    past_combs = get_past_combinations(numbers_df)
    
    # 분석 결과 출력
    print("=== 로또 데이터 분석 결과 ===")
    print(f"총 회차 수: {len(df)}")
    print(f"전체 번호 빈도 상위 10: {full_freq.most_common(10)}")
    print(f"최근 50회 빈도 상위 10: {recent_freq.most_common(10)}")
    print(f"홀수 비율: {odd_ratio:.2%}")
    print(f"합계 평균: {sum_mean:.1f}, 25%~75% 범위: {sum_p25}~{sum_p75}")
    print(f"평균 연속 쌍 수: {avg_consec:.2f}")
    
    # 추천
    recommendations = generate_recommendations(full_freq, recent_freq, past_combs, sum_p25, sum_p75, avg_consec)
    print("\n=== 추천 번호 조합 (당첨 가능성 높은 5개) ===")
    for i, comb in enumerate(recommendations, 1):
        print(f"{i}. {comb}")

if __name__ == "__main__":
    main()
