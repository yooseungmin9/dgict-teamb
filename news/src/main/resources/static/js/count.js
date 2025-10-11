(function () {
  const API = "http://127.0.0.1:8011/count";
  const panel = document.querySelector("#panel-news-count .card__body");
  if (!panel) return;

  function fmt(n) {
    return n.toLocaleString("ko-KR");
  }

  function render(data) {
    panel.innerHTML = `
      <div style="text-align:center;font-size:36px;font-weight:600;color:#000">
        ${fmt(data.total)}개
      </div>
      <div class="muted" style="margin-top:4px;font-size:12px;">
        업데이트: ${new Date(data.updated_at).toLocaleString("ko-KR")}
      </div>
    `;
  }

  async function load() {
    try {
      const r = await fetch(API, { cache: "no-store" });
      if (!r.ok) throw new Error(r.statusText);
      const data = await r.json();
      if (data && data.ok) render(data);
      else panel.textContent = "데이터 없음";
    } catch (e) {
      panel.textContent = "불러오기 실패";
      console.error(e);
    }
  }

  load();
})();