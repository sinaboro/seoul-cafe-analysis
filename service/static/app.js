/* app.js - API 에서 데이터를 받아 카드·차트·표를 채운다
   ── 전체 흐름 ──
   ① 처음 열릴 때: 자치구 목록을 채우고, 화면 전체를 그린다 (loadAll)
   ② 자치구를 바꾸면: 카드·추이·시간대·추천 표를 그 자치구로 다시 그린다
   ③ 슬라이더를 움직이면: /api/score 를 다시 불러 추천 표만 바꾼다
   차트는 Chart.js 로 그리고, 다시 그릴 때는 이전 차트를 지운다(destroy). */

const charts = {};                       // 만든 차트를 이름으로 보관 (다시 그릴 때 지우려고)
const guSelect = document.getElementById("gu-select");

// API 한 곳을 불러 JSON 을 돌려준다. 실패하면 오류를 던진다
async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} 요청 실패: ${res.status}`);
  return res.json();
}

// 차트 그리기: 같은 이름의 차트가 있으면 지우고 새로 만든다
function drawChart(name, type, labels, values, color) {
  if (charts[name]) charts[name].destroy();
  charts[name] = new Chart(document.getElementById(name), {
    type: type,
    data: { labels: labels, datasets: [{ data: values, backgroundColor: color, borderColor: color }] },
    options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } },
  });
}

// ② 카드 4개
async function loadSummary(gu) {
  const s = await getJSON(`/api/summary?gu=${encodeURIComponent(gu)}`);
  document.getElementById("c-quarter").textContent = s["분기"];
  document.getElementById("c-sales").textContent = s["매출_억원"].toLocaleString() + " 억 원";
  document.getElementById("c-stores").textContent = s["점포수"].toLocaleString() + " 곳";
  document.getElementById("c-frc").textContent = s["프랜차이즈비율"] + " %";
}

// 자치구별 매출 막대 (항상 서울 전체). 고른 자치구는 진한 색으로 표시
async function loadGu(gu) {
  const rows = await getJSON("/api/gu");
  const colors = rows.map(r => (r["자치구"] === gu ? "#6F4E37" : "#d9c2a7"));
  drawChart("chart-gu", "bar", rows.map(r => r["자치구"]), rows.map(r => r["매출_억원"]), colors);
  return rows;
}

async function loadTrend(gu) {
  const rows = await getJSON(`/api/trend?gu=${encodeURIComponent(gu)}`);
  drawChart("chart-trend", "line", rows.map(r => r["분기"]), rows.map(r => r["매출_억원"]), "#6F4E37");
}

async function loadTime(gu) {
  const rows = await getJSON(`/api/timezone?gu=${encodeURIComponent(gu)}`);
  drawChart("chart-time", "bar", rows.map(r => r["시간대"]), rows.map(r => r["비중"]), "#C08552");
}

// ③ 추천 표: 슬라이더 값 4개를 주소에 붙여 보낸다
async function loadScore() {
  const w = id => document.getElementById(id).value;
  const url = `/api/score?w_sales=${w("w-sales")}&w_demand=${w("w-demand")}` +
              `&w_growth=${w("w-growth")}&w_stable=${w("w-stable")}&gu=${encodeURIComponent(guSelect.value)}`;
  const body = document.getElementById("score-body");
  try {
    const rows = await getJSON(url);
    body.innerHTML = rows.map((r, i) => `
      <tr><td>${i + 1}</td><td>${r["자치구"]}</td><td>${r["행정동"]}</td>
        <td class="score">${r["추천점수"]}</td><td>${r["매출점수"]}</td><td>${r["수요점수"]}</td>
        <td>${r["성장점수"]}</td><td>${r["안정점수"]}</td><td>${r["점포수"]}</td></tr>`).join("");
  } catch (e) {
    body.innerHTML = `<tr><td colspan="9">가중치를 하나 이상 0 보다 크게 해 주세요.</td></tr>`;
  }
}

// ① 처음 한 번: 자치구 목록 채우기
async function init() {
  const rows = await loadGu("");
  rows.map(r => r["자치구"]).sort().forEach(name => {
    guSelect.insertAdjacentHTML("beforeend", `<option value="${name}">${name}</option>`);
  });
  await loadAll();
}

// 자치구에 따라 바뀌는 것 모두 다시 그리기
async function loadAll() {
  const gu = guSelect.value;
  await Promise.all([loadSummary(gu), loadGu(gu), loadTrend(gu), loadTime(gu), loadScore()]);
}

guSelect.addEventListener("change", loadAll);
// 슬라이더: 움직이는 동안 옆 숫자를 바꾸고, 손을 떼면(change) 표를 다시 불러온다
document.querySelectorAll(".sliders input").forEach(input => {
  input.addEventListener("input", () => { input.nextElementSibling.textContent = input.value; });
  input.addEventListener("change", loadScore);
});
init();
