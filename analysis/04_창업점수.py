"""
04_창업점수.py - NumPy 로 행정동마다 '카페 창업 추천 점수'(0~100)를 계산한다

── 전체 흐름 ──
① 최근 분기 표에 '1년 전 같은 분기 대비 매출 성장률' 을 붙인다
② 점포가 너무 적은 동(10곳 미만)은 숫자가 들쭉날쭉해서 뺀다
③ 지표 4개를 0~100 점으로 바꾼다 (극단값은 5%·95% 지점에서 자른 뒤 최소-최대 정규화)
     점포당 매출 ↑ 좋음 · 점포당 유동인구 ↑ 좋음 · 매출 성장률 ↑ 좋음 · 폐업률 ↓ 좋음(뒤집는다)
④ 가중치로 평균을 내 최종 점수를 만들고, 상위 10곳을 출력·저장한다

실행:  python analysis/04_창업점수.py
점수 계산 함수는 analysis/scoring.py 에 있고, service/main.py 도 같은 함수를 쓴다.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean"
IMG = ROOT / "images"
sns.set_theme(style="whitegrid", font="Malgun Gothic")
plt.rcParams["axes.unicode_minus"] = False

from scoring import DEFAULT_WEIGHTS, add_growth, startup_score   # 계산 함수는 scoring.py 에 있다


def main():
    q = pd.read_csv(CLEAN / "커피_분기별.csv", dtype={"분기": str, "행정동코드": str})
    last = pd.read_csv(CLEAN / "커피_최근분기.csv", dtype={"분기": str, "행정동코드": str})

    df = add_growth(last, q)                            # ①
    df = df[df["점포수"] >= 10]                         # ② 점포 10곳 미만 동은 제외
    print(f"점수를 매긴 행정동: {len(df)}곳")

    ranked = startup_score(df, DEFAULT_WEIGHTS)         # ③ ④
    cols = ["자치구", "행정동", "추천점수", "매출점수", "수요점수", "성장점수", "안정점수", "점포수"]
    top = ranked[cols].head(10)
    print(top.round(1).to_string(index=False))
    ranked.to_csv(CLEAN / "창업점수.csv", index=False, encoding="utf-8-sig")

    # 상위 10곳 점수 구성(지표별 기여)을 누적 막대로 그린다
    part = top.set_index(top["자치구"] + " " + top["행정동"])
    contrib = pd.DataFrame({name: part[name + "점수"] * w for name, w in DEFAULT_WEIGHTS.items()})
    contrib.iloc[::-1].plot(kind="barh", stacked=True, figsize=(9, 5.5),
                            color=["#6F4E37", "#C08552", "#3E7C59", "#4E6E81"])
    plt.title("카페 창업 추천 점수 상위 10 행정동 (지표별 기여)")
    plt.xlabel("점수 (100점 만점)")
    plt.ylabel("")
    plt.tight_layout()
    plt.savefig(IMG / "q7_창업점수.png", dpi=130)
    print("  그래프: images/q7_창업점수.png")


if __name__ == "__main__":
    main()
