"""
03_탐색분석.py - pandas 로 질문에 답하고 seaborn 으로 그래프를 그린다

── 전체 흐름 (질문 6개) ──
Q1 어느 자치구가 커피 매출이 크고, 점포 1곳당 매출은 어떤가?   → 막대 그래프
Q2 서울 커피 매출은 분기마다 어떻게 변했나?                       → 꺾은선 그래프
Q3 자치구마다 바쁜 시간대가 다른가?                               → 히트맵(자치구 × 시간대 비중)
Q4 누가 커피를 사는가? (연령대 · 성별)                            → 막대 그래프
Q5 점포가 많은 동은 점포당 매출이 낮을까? (포화)                  → 산점도
Q6 지표끼리 얼마나 함께 움직이나?                                  → 상관 히트맵
그래프는 images 폴더에 PNG 로 저장하고, 핵심 숫자는 화면에 출력한다.

실행:  python analysis/03_탐색분석.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                                   # 창을 띄우지 않고 파일로만 저장
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "clean"
IMG = ROOT / "images"
IMG.mkdir(exist_ok=True)

sns.set_theme(style="whitegrid", font="Malgun Gothic")  # 한글 글꼴 (Windows 기본 맑은 고딕)
plt.rcParams["axes.unicode_minus"] = False               # 음수 기호가 깨지지 않게
EOK = 100_000_000                                        # 1억 (원 → 억 원)


def save(name):
    """현재 그래프를 images/이름.png 로 저장하고 닫는다"""
    plt.tight_layout()
    plt.savefig(IMG / f"{name}.png", dpi=130)
    plt.close()
    print("  그래프:", f"images/{name}.png")


def main():
    q = pd.read_csv(CLEAN / "커피_분기별.csv", dtype={"분기": str, "행정동코드": str})
    last = pd.read_csv(CLEAN / "커피_최근분기.csv", dtype={"분기": str, "행정동코드": str})

    # ---------------------------------------------------------------- Q1 자치구별 매출과 점포당 매출
    gu = last.groupby("자치구")[["매출액", "점포수"]].sum()          # 자치구마다 동을 더한다
    gu["점포당매출"] = gu["매출액"] / gu["점포수"]                    # 자치구 전체 매출 ÷ 전체 점포
    gu = gu.sort_values("매출액", ascending=False)
    print("[Q1] 매출 상위 3 자치구 (억 원):", (gu["매출액"].head(3) / EOK).round(0).to_dict())
    print("     점포당 매출 상위 3 (백만 원):", (gu["점포당매출"].sort_values(ascending=False).head(3) / 1e6).round(1).to_dict())

    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    sns.barplot(x=gu["매출액"] / EOK, y=gu.index, color="#6F4E37", ax=axes[0])
    axes[0].set(title="자치구별 커피 매출 (억 원, 최근 분기)", xlabel="", ylabel="")
    per = gu["점포당매출"].sort_values(ascending=False) / 1e6
    sns.barplot(x=per, y=per.index, color="#C08552", ax=axes[1])
    axes[1].set(title="점포 1곳당 매출 (백만 원)", xlabel="", ylabel="")
    save("q1_자치구별매출")

    # ---------------------------------------------------------------- Q2 분기별 추이
    trend = q.groupby("분기")["매출액"].sum() / EOK                 # 서울 전체 분기 매출
    label = [f"{s[:4]}-{s[4]}Q" for s in trend.index]                # 20262 → 2026-2Q
    print("[Q2] 분기별 매출 (억 원):", dict(zip(label, trend.round(0))))
    plt.figure(figsize=(9, 4.5))
    sns.lineplot(x=label, y=trend.values, marker="o", color="#6F4E37")
    plt.title("서울 커피 업종 분기 매출 (억 원)")
    plt.ylim(0, trend.max() * 1.15)                                  # 0 부터 그려 차이를 과장하지 않는다
    save("q2_분기추이")

    # ---------------------------------------------------------------- Q3 자치구 × 시간대 매출 비중
    times = ["06~11시", "11~14시", "14~17시", "17~21시", "21~24시", "00~06시"]
    tz = last.groupby("자치구")[times].sum()
    tz_pct = tz.div(tz.sum(axis=1), axis=0) * 100                    # 행(자치구)마다 합이 100% 가 되게
    tz_pct = tz_pct.sort_values("06~11시", ascending=False)         # 아침 비중이 큰 순서로
    print("[Q3] 아침(06~11시) 비중 상위 3:", tz_pct["06~11시"].head(3).round(1).to_dict())
    plt.figure(figsize=(8, 9))
    sns.heatmap(tz_pct, annot=True, fmt=".0f", cmap="YlOrBr", cbar_kws={"label": "%"})
    plt.title("자치구별 시간대 매출 비중 (%)")
    save("q3_시간대히트맵")

    # ---------------------------------------------------------------- Q4 연령대·성별
    ages = ["10대", "20대", "30대", "40대", "50대", "60대이상"]
    age = last[ages].sum() / last[ages].sum().sum() * 100
    female = last["여성매출"].sum() / (last["남성매출"].sum() + last["여성매출"].sum()) * 100
    print("[Q4] 연령대 비중(%):", age.round(1).to_dict(), " 여성 비중:", round(female, 1))
    plt.figure(figsize=(8, 4.5))
    sns.barplot(x=age.index, y=age.values, color="#3E7C59")
    plt.title(f"연령대별 커피 매출 비중 (%) - 여성 {female:.0f}%")
    plt.xlabel("")                                                   # 축 이름(None) 지우기
    save("q4_연령대")

    # ---------------------------------------------------------------- Q5 포화: 점포 수 vs 점포당 매출
    d = last.dropna(subset=["점포당매출"])
    corr = d["점포수"].corr(d["점포당매출"])
    print(f"[Q5] 점포수와 점포당 매출의 상관계수: {corr:.2f}")
    plt.figure(figsize=(9, 6))
    sns.scatterplot(data=d, x="점포수", y=d["점포당매출"] / 1e6, size="매출액", sizes=(10, 300),
                    alpha=0.6, color="#6F4E37", legend=False)
    for _, row in d.nlargest(5, "점포수").iterrows():               # 점포가 가장 많은 5곳에 이름 붙이기
        plt.annotate(row["행정동"], (row["점포수"], row["점포당매출"] / 1e6), fontsize=9)
    plt.title("행정동별 점포 수와 점포당 매출 (백만 원) - 점 크기 = 매출")
    plt.ylabel("점포당 매출 (백만 원)")
    save("q5_포화산점도")

    # ---------------------------------------------------------------- Q6 지표끼리의 상관
    cols = ["매출액", "점포수", "점포당매출", "프랜차이즈비율", "폐업률", "유동인구_일평균", "직장인구", "상주인구"]
    c = last[cols].corr()
    print("[Q6] 매출액과 상관이 큰 지표:", c["매출액"].drop("매출액").sort_values(ascending=False).round(2).head(3).to_dict())
    plt.figure(figsize=(8, 6.5))
    sns.heatmap(c, annot=True, fmt=".2f", cmap="RdBu_r", vmin=-1, vmax=1)
    plt.title("지표 사이의 상관계수 (최근 분기, 행정동 기준)")
    save("q6_상관히트맵")


if __name__ == "__main__":
    main()
