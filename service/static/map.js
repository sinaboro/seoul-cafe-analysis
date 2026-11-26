/* map.js - Leaflet 으로 '행정동 추천 점수 색칠 지도' 와 '커피숍 위치 점' 을 그린다 (9장)
   ── 전체 흐름 ──
   ① 지도를 만들고 바탕 지도(OpenStreetMap 타일)를 깐다
   ② 행정동 경계선(/api/dong-geo)을 한 번 받아 지도에 올린다
   ③ 동마다 추천 점수(/api/map)를 받아 색을 칠한다 → 슬라이더를 움직이면 다시 칠한다
   ④ 커피숍 위치(/api/stores)를 작은 동그라미로 찍는다 → 자치구를 바꾸면 그 구만 찍고 확대한다
   app.js 는 건드리지 않고, 같은 자치구 상자·슬라이더에 이 파일이 따로 이벤트를 붙인다. */

const SEOUL_CENTER = [37.5665, 126.978];      // 서울시청 (위도, 경도) - Leaflet 은 항상 [위도, 경도] 순서
const guBox = document.getElementById("gu-select");
const storeCheck = document.getElementById("show-stores");

// ① 지도 만들기. preferCanvas: 점 1만 개도 빠르게 그리도록 SVG 대신 캔버스에 그린다
//               zoomSnap: 0.5 → 확대 단계를 반 칸씩 (자치구에 딱 맞게 확대하려고)
const map = L.map("map", { preferCanvas: true, zoomSnap: 0.5 }).setView(SEOUL_CENTER, 11);   // 11 = 확대 정도(클수록 가까이)
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> 기여자',  // 저작권 표시는 지우면 안 된다
}).addTo(map);

let dongLayer = null;      // 행정동 경계 층 (② 에서 만든다)
let storeLayer = null;     // 커피숍 점 층 (④ 에서 만든다)
let scores = {};           // { "11110515": {순위, 추천점수, 점포수, 매출_억원}, ... }

// 가게 이름에 < > 같은 글자가 있어도 화면이 깨지지 않게 바꿔 준다
function esc(text) {
  return String(text).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// 점수 → 색. 높을수록 진한 커피색. 점수가 없는 동(점포 10곳 미만)은 회색
// 구간은 점수 분포를 보고 정했다: 서울 동들의 점수는 대략 30~60점에 몰려 있다
const STEPS = [
  { min: 60, color: "#4a2c17", label: "60점 이상" },
  { min: 50, color: "#7b4a2a", label: "50 ~ 60" },
  { min: 40, color: "#b0763f", label: "40 ~ 50" },
  { min: 30, color: "#d9a86c", label: "30 ~ 40" },
  { min: 0,  color: "#f3dcb8", label: "30점 미만" },
];
function colorOf(score) {
  if (score === undefined) return "#cccccc";
  return STEPS.find(s => score >= s.min).color;
}

// 동 하나(feature)를 어떤 모양으로 그릴지: 안쪽 색, 테두리 색·두께, 투명도
// 자치구를 골랐으면 다른 구의 동은 흐리게(0.15) 해서 고른 구가 눈에 띄게 한다
function dongStyle(feature) {
  const s = scores[feature.properties["행정동코드"]];
  const gu = guBox.value;
  const mine = !gu || feature.properties["자치구"] === gu;
  return { fillColor: colorOf(s && s["추천점수"]), fillOpacity: mine ? 0.65 : 0.15, color: "#ffffff", weight: 1 };
}

// 동을 눌렀을 때 뜨는 말풍선 내용
function dongPopup(feature) {
  const p = feature.properties;
  const s = scores[p["행정동코드"]];
  if (!s) return `<b>${p["자치구"]} ${p["행정동"]}</b><br>커피 점포가 10곳 미만이라 점수 없음`;
  return `<b>${p["자치구"]} ${p["행정동"]}</b><br>
    추천 점수 <b>${s["추천점수"]}</b>점 (서울 ${s["순위"]}위)<br>
    점포 ${s["점포수"]}곳 · 매출 ${s["매출_억원"]}억 원`;
}

// ② 행정동 경계선 올리기 (처음 한 번)
async function loadDongs() {
  const geo = await getJSON("/api/dong-geo");          // getJSON 은 app.js 에 있는 함수
  dongLayer = L.geoJSON(geo, {
    style: dongStyle,
    onEachFeature: (feature, layer) => layer.bindPopup(() => dongPopup(feature)),  // 누를 때마다 최신 점수로
  }).addTo(map);
}

// ③ 점수 받아서 다시 칠하기. 가중치는 app.js 와 같은 슬라이더 값
async function loadScores() {
  const w = id => document.getElementById(id).value;
  const url = `/api/map?w_sales=${w("w-sales")}&w_demand=${w("w-demand")}` +
              `&w_growth=${w("w-growth")}&w_stable=${w("w-stable")}`;
  try {
    scores = await getJSON(url);
  } catch (e) {
    scores = {};                                       // 가중치가 모두 0 이면 모두 회색
  }
  dongLayer.setStyle(dongStyle);                       // 모든 동의 색을 새 점수로 다시 칠한다
}

// ④ 커피숍 점 찍기. 서울 전체는 점이 많아 색칠을 가리므로 아주 작고 흐린 점, 자치구 하나는 또렷한 점
async function loadStores() {
  if (storeLayer) map.removeLayer(storeLayer);         // 전에 찍은 점은 지운다
  storeLayer = null;
  const count = document.getElementById("store-count");
  if (!storeCheck.checked) { count.textContent = ""; return; }

  const gu = guBox.value;
  const rows = await getJSON(`/api/stores?gu=${encodeURIComponent(gu)}`);
  const look = gu
    ? { radius: 4, color: "#ffffff", weight: 1, fillColor: "#1f8f74", fillOpacity: 0.9 }   // 자치구 하나
    : { radius: 1.5, stroke: false, fillColor: "#1f8f74", fillOpacity: 0.5 };              // 서울 전체
  storeLayer = L.layerGroup(rows.map(r =>
    L.circleMarker([r["위도"], r["경도"]], look).bindPopup(`<b>${esc(r["상호"])}</b><br>${esc(r["주소"])}<br>개업 ${esc(r["개업일"])}`)
  )).addTo(map);
  count.textContent = `(${rows.length.toLocaleString()}곳)`;
}

// 자치구를 고르면 그 구에 속한 동들이 화면에 꽉 차게 확대한다. 서울 전체면 처음 위치로
function zoomToGu() {
  const gu = guBox.value;
  if (!gu) { map.setView(SEOUL_CENTER, 11); return; }
  const parts = dongLayer.getLayers().filter(l => l.feature.properties["자치구"] === gu);
  map.fitBounds(L.featureGroup(parts).getBounds());
}

// 오른쪽 아래 범례(색 설명)
const legend = L.control({ position: "bottomright" });
legend.onAdd = () => {
  const div = L.DomUtil.create("div", "legend");
  div.innerHTML = "<b>추천 점수</b><br>" +
    STEPS.map(s => `<i style="background:${s.color}"></i>${s.label}`).join("<br>") +
    '<br><i style="background:#cccccc"></i>점수 없음<br>' +
    '<i style="background:#1f8f74;border-radius:50%"></i>커피숍';
  return div;
};
legend.addTo(map);

// 처음 한 번: 경계 → 점수 → 점 순서로
async function initMap() {
  await loadDongs();
  await loadScores();
  await loadStores();
}

guBox.addEventListener("change", () => { dongLayer.setStyle(dongStyle); zoomToGu(); loadStores(); });
storeCheck.addEventListener("change", loadStores);
document.querySelectorAll(".sliders input").forEach(input => input.addEventListener("change", loadScores));
initMap();
