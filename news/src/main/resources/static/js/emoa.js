(() => {
  document.addEventListener("DOMContentLoaded", () => initEmoaRealtime());

  function pickContainer() {
    // 프로젝트 구조를 고려한 후보 선택(우선순위)
    return (
      document.querySelector("#panel-today-sentiment .card__body") ||
      document.querySelector("#panel-today-sentiment [data-ssr]") ||
      document.querySelector("#panel-today-sentiment") ||
      null
    );
  }

  async function initEmoaRealtime() {
    const box = pickContainer();
    if (!box) {
      console.warn("[emoa] 컨테이너 미발견: #panel-today-sentiment");
      return;
    }

    const endpoint =
      document.body?.dataset?.emoaApi ||
      (window.API_ENDPOINTS && window.API_ENDPOINTS.emoaScore) ||
      "/emoa/score";

    let retryMs = 0;
    let timer = null;
    let aborter = null;

    ensureMarkup(box);
    schedule();

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stopPolling();
      else schedule();
    });

    function stopPolling() {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      if (aborter) {
        aborter.abort();
        aborter = null;
      }
    }

    function schedule() {
      stopPolling();
      if (document.hidden) return;
      timer = setTimeout(() => tick(), retryMs || 5000);
    }

    async function tick() {
      try {
        if (aborter) aborter.abort();
        aborter = new AbortController();

        const r = await fetch(withTs(endpoint), {
          signal: aborter.signal,
          headers: { Accept: "application/json" },
          cache: "no-store",
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);

        const d = await r.json();
        apply(box, d); // 성공시에만 DOM 갱신
        retryMs = 0;
      } catch (e) {
        console.error("[emoa] fetch failed:", e);
        showError(box, `불러오기 실패: ${e.message}`); // 오류만 표시, DOM 값 변경 안 함
        retryMs = Math.min(retryMs ? retryMs * 2 : 3000, 30000);
      } finally {
        schedule();
      }
    }

    function ensureMarkup(container) {
      // 이미 존재하면 유지, 없으면 생성
      if (container.querySelector("#emoa-avg") && container.querySelector("#emoa-delta")) return;
      container.innerHTML = `
        <p style="margin:6px 0;">평균 감성점수: <strong id="emoa-avg">-</strong></p>
        <p style="margin:6px 0;">전일 대비: <strong id="emoa-delta">-</strong></p>
        <p class="emoa-error" style="display:none; color:red; text-align:center;"></p>
      `;
    }

    function apply(container, d) {
      ensureMarkup(container); // 매 호출 시 보증

      const $avg = container.querySelector("#emoa-avg");
      const $delta = container.querySelector("#emoa-delta");
      const $date = container.querySelector("#emoa-date");
      const $err = container.querySelector(".emoa-error");

      if ($err) $err.style.display = "none";

      const date = d?.date ?? "-";
      const weekday = d?.weekday ?? "-";
      const avg = Number.isFinite(d?.avg) ? Number(d.avg) : null;
      const delta = Number.isFinite(d?.delta) ? Number(d.delta) : null;

      if ($avg) animNumber($avg, avg);
      if ($delta) {
        animNumber($delta, delta);
        const color =
          delta == null ? "#666" : delta > 0 ? "#e74c3c" : delta < 0 ? "#3498db" : "#95a5a6";
        $delta.style.color = color;
      }
      if ($date) $date.textContent = `${date} (${weekday})`;
    }

    function animNumber(node, to) {
      if (!node) return;
      const fmt = (v) => (v == null || Number.isNaN(v) ? "-" : Number(v).toFixed(2));
      if (to == null || Number.isNaN(Number(to))) {
        node.textContent = "-";
        return;
      }
      const from = Number(node.textContent.replace(/[^\d.-]/g, "")) || 0;
      const start = performance.now();
      const dur = 600;
      function step(t) {
        const k = Math.min(1, (t - start) / dur);
        const ease = 1 - Math.pow(1 - k, 3);
        node.textContent = fmt(from + (to - from) * ease);
        if (k < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    }

    function showError(container, msg) {
      ensureMarkup(container);
      const $err = container.querySelector(".emoa-error");
      if ($err) {
        $err.textContent = msg;
        $err.style.display = "block";
      }
    }

    function withTs(url) {
      const u = new URL(url, location.origin);
      u.searchParams.set("ts", Date.now().toString());
      return u.toString();
    }
  }
})();
