const API = "http://127.0.0.1:8012";

async function loadSummary() {
  const url = `${API}/api/clusters/summary?top=60&min_size=3`;
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    const j = await r.json();
    return j.items || [];
  } catch (e) {
    console.error("[clusters] fetch error:", e);
    document.getElementById("treemap").innerHTML =
      `<div style="color:#999;font-size:13px">요청 실패: ${url}</div>`;
    return [];
  }
}

function cleanLabel(s) {
  if (!s) return s;
    s = String(s).replace(/^요약[:：]?\s*/i, "");
  return s
    ? s.replace(/(?:^|[\s\-\|,;])(?:이슈\s*요약|대표\s*이슈명|이슈명)\s*[:：]?\s*/gi, " ")
        .replace(/["“”‘’]+/g, "")
        .replace(/\s{2,}/g, " ")
        .trim()
    : s;
}

function wrap2Lines(name, width=14) {
  const words = (name||"").split(/\s+/);
  const lines = [];
  let cur = "";
  for (const w of words) {
    const t = (cur?cur+" ":"")+w;
    if (t.length <= width) cur = t;
    else { lines.push(cur); cur = w; if (lines.length===1) break; }
  }
  if (lines.length<2 && cur) lines.push(cur);
  if (words.join(" ").length > (lines.join(" ").length)) lines[lines.length-1] += "…";
  return lines.join("\n");
}

async function renderTreemapECharts() {
  const items = await loadSummary(); if (!items.length) return;
  const el = document.getElementById("treemap");
  const chart = echarts.init(el, null, { renderer:'canvas' });

  let overlay = document.getElementById("cluster-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "cluster-overlay";
    document.body.appendChild(overlay);   // ✅ 여기 변경
  }
  el.appendChild(overlay);

  const arr  = [...items].sort((a,b)=>b.value-a.value);
  const vals = arr.map(d=>d.value);
  const vmin = Math.min(...vals), vmax = Math.max(...vals);
  const span = Math.max(1, vmax - vmin);

  const colorOf = v => {
    const t = (v - vmin) / span;             // 0..1
    const l = 92 - t * 45;                    // 밝기: 값↑ → 더 어둡게
    return `hsl(210 80% ${l}%)`;              // 파스텔 블루 계열
  };

  const data = arr.map(d => ({
    name: cleanLabel(d.name),
    value: d.value,
    id: d.id,
    itemStyle: { color: colorOf(d.value), borderColor: '#fff', borderWidth: 1 }
  }));

  chart.setOption({
    tooltip:{
      trigger:'item',
      triggerOn:'mousemove',
      hideDelay:0,
      formatter: p => `${cleanLabel(p.data.name)}<br/>유사 주제 기사 수: ${p.value.toLocaleString()}`
    },
    backgroundColor:'#fff',
    series: [{
      type: 'treemap',
      left: 0, right: 0, top: 0, bottom: 0,
      sort: 'desc', nodeClick: false, roam: false,
      visibleMin: 18,
      data,
      label: {
        show: true,
        formatter: p => wrap2Lines(p.data.name, 14),
        overflow: 'truncate',
        width: '92%',
        lineHeight: 14,
        fontSize: 12,
        color: '#0d1b2a',
        padding: [2,2,2,2]
      },
      upperLabel: { show: false },
      breadcrumb: { show: false },
      itemStyle: { gapWidth: 2, borderColor: '#fff', borderWidth: 1 },

    }]
  }, { notMerge:true });

  window.addEventListener('resize', () => chart.resize());

chart.off('click');
chart.on('click', async (p) => {
  chart.dispatchAction({ type:'hideTip' });
  const id = p.data.id;
  const name = cleanLabel(p.data.name);

  let page = 0;
  const pageSize = 10;

  async function loadPage() {
    const res = await fetch(`${API}/api/clusters/table?cluster_id=${id}&limit=${pageSize}&skip=${page * pageSize}`);
    const data = await res.json();
    const arts = data.articles || [];

    const list = arts.map(a => `
      <li class="article-item">
        <a href="${a.url}" target="_blank">${a.title || "제목 없음"}</a>
        <span class="press">(${a.press || "언론사 미상"})</span>
      </li>
    `).join('') || `<li style="color:#999">기사가 없습니다.</li>`;

    overlay.innerHTML = `
      <div class="cluster-card">
        <button id="co-close" class="close-btn">×</button>
        <h3 class="cluster-title">${data.label_gpt || name}</h3>
        <p class="cluster-sub">총 ${data.size}개 기사</p>
        <ul class="article-list">${list}</ul>
        <div class="pagination">
          <button id="prev" class="nav-btn" ${page === 0 ? "disabled" : ""}>◀ 이전</button>
          <button id="next" class="nav-btn" ${(page + 1) * pageSize >= data.size ? "disabled" : ""}>다음 ▶</button>
        </div>
      </div>
    `;

    // 닫기 및 페이지 이벤트
    document.getElementById("co-close").onclick = () => overlay.style.display = "none";
    const prev = document.getElementById("prev");
    const next = document.getElementById("next");
    if (prev) prev.onclick = () => { if (page > 0) { page--; loadPage(); } };
    if (next) next.onclick = () => { if ((page + 1) * pageSize < data.size) { page++; loadPage(); } };
  }

  overlay.style.display = "flex";
  loadPage();
});



chart.getZr().on('click', (e) => { if (!e.target) overlay.style.display = 'none'; });

  // Top10
  const list = document.getElementById("toplist");
  const topN = arr.slice(0,10);
  list.innerHTML = topN.map((d,i)=>`<li>${cleanLabel(d.name)} — <strong>${d.value}</strong></li>`).join("");
}

// DOM 로더 교체
document.addEventListener("DOMContentLoaded", () => {
  renderTreemapECharts();
});