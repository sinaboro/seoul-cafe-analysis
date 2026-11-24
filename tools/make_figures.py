"""make_figures.py - 교안의 개념 그림(프로젝트 흐름)을 그린다 → guide/images/fig_flow.png"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

plt.rcParams["font.family"] = "Malgun Gothic"
OUT = Path(__file__).resolve().parent.parent / "guide" / "images"
OUT.mkdir(parents=True, exist_ok=True)

# (x, 제목, 설명, 색) - 왼쪽에서 오른쪽으로 다섯 단계
STEPS = [(2, "① 데이터 받기", "Open API\nrequests\n→ data/raw", "#e3ebf5"),
         (22, "② 정리", "pandas\n병합 · 계산\n→ data/clean", "#f3e9e2"),
         (42, "③ 분석", "seaborn 그래프\nNumPy 점수\n→ images", "#e6f4ea"),
         (62, "④ API", "FastAPI\n/api/...\nJSON", "#fff1dc"),
         (82, "⑤ 화면", "HTML·CSS·JS\nfetch\nChart.js", "#fdecea")]

fig, ax = plt.subplots(figsize=(10, 2.6), dpi=150)
ax.set_xlim(0, 100); ax.set_ylim(0, 26); ax.axis("off")
for x, title, desc, color in STEPS:
    ax.add_patch(FancyBboxPatch((x, 3), 16, 18, boxstyle="round,pad=0.4,rounding_size=1.5", fc=color, ec="#6F4E37"))
    ax.text(x + 8, 17.5, title, ha="center", va="center", fontsize=10.5, fontweight="bold", color="#2b2118")
    ax.text(x + 8, 9.5, desc, ha="center", va="center", fontsize=8.8, color="#2b2118", linespacing=1.4)
for x, *_ in STEPS[:-1]:                                   # 단계 사이 화살표
    ax.add_patch(FancyArrowPatch((x + 16.6, 12), (x + 19.6, 12), arrowstyle="-|>", mutation_scale=12, color="#6F4E37"))
ax.text(50, 24.5, "프로젝트 흐름 - 공공데이터에서 웹 대시보드까지", ha="center", fontsize=11.5, fontweight="bold", color="#6F4E37")
fig.savefig(OUT / "fig_flow.png", bbox_inches="tight", facecolor="white")
print("그림: guide/images/fig_flow.png")
