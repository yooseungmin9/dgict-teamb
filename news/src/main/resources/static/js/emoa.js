document.addEventListener("DOMContentLoaded", async () => {
  const box = document.querySelector("#panel-today-sentiment .card__body");
  if (!box) return;
  try {
    const r = await fetch("http://127.0.0.1:8000/emoa/score");
    const d = await r.json();
    box.innerHTML = `
      <p>${d.date} (${d.weekday})</p>
      <p>평균 감성점수: <strong>${fmt(d.avg)}</strong></p>
      <p>전일 대비: <strong>${d.delta == null ? "-" : fmt(d.delta)}</strong></p>
    `;
  } catch (e) {
    box.innerHTML = `<p>불러오기 실패: ${e.message}</p>`;
  }
});

function fmt(v) { return v == null ? "-" : Number(v).toFixed(2); }