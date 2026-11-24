"""
scoring.py - 카페 창업 추천 점수 계산 함수 모음

04_창업점수.py(분석)와 service/main.py(웹 서비스)가 같은 계산을 쓰도록 함수만 따로 모은 파일이다.
"""
import numpy as np
import pandas as pd

# 지표 이름 → (열 이름, 클수록 좋으면 True)
INDICATORS = {
    "매출": ("점포당매출", True),
    "수요": ("점포당_유동인구", True),
    "성장": ("매출성장률", True),
    "안정": ("폐업률", False),          # 폐업률은 낮을수록 좋다 → 점수를 뒤집는다
}
DEFAULT_WEIGHTS = {"매출": 0.35, "수요": 0.25, "성장": 0.20, "안정": 0.20}


def to_score(values, higher_is_better=True):
    """숫자 배열을 0~100 점으로 바꾼다.
    극단값 몇 개 때문에 나머지가 모두 0 근처로 몰리지 않게, 5%·95% 지점 밖은 그 값으로 자른다(clip)."""
    x = np.asarray(values, dtype=float)
    low, high = np.nanpercentile(x, [5, 95])            # 아래 5%, 위 5% 경계값
    x = np.clip(x, low, high)                           # 경계 밖은 경계값으로
    score = (x - low) / (high - low) * 100              # 최소-최대 정규화 → 0~100
    if not higher_is_better:
        score = 100 - score                             # 낮을수록 좋은 지표는 뒤집는다
    return np.nan_to_num(score, nan=50)                 # 값이 없으면 중간 점수(50)


def startup_score(df, weights):
    """지표마다 점수를 매기고 가중 평균한 '추천점수' 열을 붙여 돌려준다"""
    df = df.copy()
    total = sum(weights.values())                       # 가중치 합이 1 이 아니어도 되게 나눠 준다
    df["추천점수"] = 0.0
    for name, (col, higher) in INDICATORS.items():
        df[name + "점수"] = to_score(df[col], higher)
        df["추천점수"] += df[name + "점수"] * weights[name] / total
    return df.sort_values("추천점수", ascending=False)


def add_growth(last, q):
    """1년 전 같은 분기(예: 20262 → 20252) 매출과 비교한 성장률(%)을 붙인다"""
    latest = last["분기"].iloc[0]
    year_ago = str(int(latest[:4]) - 1) + latest[4]      # 연도에서 1을 뺀다
    prev = q[q["분기"] == year_ago][["행정동코드", "매출액"]].rename(columns={"매출액": "작년매출"})
    out = last.merge(prev, on="행정동코드", how="left")
    out["매출성장률"] = (out["매출액"] / out["작년매출"] - 1) * 100
    return out
