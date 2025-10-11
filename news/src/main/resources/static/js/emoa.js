document.addEventListener("DOMContentLoaded", async () => {
  const box = document.querySelector("#panel-today-sentiment .card__body");
  if (!box) return;

  // ① body data 우선, ② 전역 window.API_ENDPOINTS, ③ 기본값(/emoa/score)
  const endpoint =
      document.body?.dataset?.emoaApi ||
      (window.API_ENDPOINTS && window.API_ENDPOINTS.emoaScore) ||
      "/emoa/score";

  try {
    const r = await fetch(endpoint, { headers: { "Accept": "application/json" }});
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    console.log("[emoa] response", d);

    const date = d?.date ?? "-";
    const weekday = d?.weekday ?? "-";
    const avg = (typeof d?.avg === "number") ? d.avg : null;
    const delta = (typeof d?.delta === "number") ? d.delta : null;

    box.innerHTML = `
      <p style="margin:6px 0;">평균 감성점수: <strong>${fmt(avg)}</strong></p>
      <p style="margin:6px 0;">전일 대비: <strong>${delta == null ? "-" : fmt(delta)}</strong></p>
      <div style="height:220px; margin-top:8px;">
        <canvas id="emoa-pie"></canvas>
      </div>
    `;

    // dist가 오면 도넛 렌더
    if (d?.dist) {
      const ctx = document.getElementById("emoa-pie");
      const data = [d.dist.pos || 0, d.dist.neu || 0, d.dist.neg || 0];

      new Chart(ctx, {
        type: "doughnut",
        data: {
          labels: ["긍정", "중립", "부정"],
          datasets: [{ data, backgroundColor: ["#36A2EB", "#CCCCCC", "#FF6384"] }]
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { position: "bottom" }, tooltip: { enabled: true } },
          cutout: "60%"
        }
      });
    } else {
      // 분포가 없으면 도넛 영역 숨김
      const wrap = document.getElementById("emoa-pie")?.parentElement;
      if (wrap) wrap.style.display = "none";
    }
  } catch (e) {
    console.error("[emoa] fetch failed", e);
    box.innerHTML = `<p>불러오기 실패: ${e.message}</p>`;
  }
});

function fmt(v){ return v == null || Number.isNaN(v) ? "-" : Number(v).toFixed(2); }
