(() => {
  document.addEventListener("DOMContentLoaded", () => initEmoaRealtime());

  function initEmoaRealtime() {
    const box = document.querySelector("#panel-today-sentiment #emoa-summary");
    if (!box) return;

    const endpoint = "http://localhost:8009/emoa/score";
    const SCALE_MAX = 50;

    let firstRender = true;
    let retryMs = 0, timer = null, aborter = null;

    ensureMarkup(box);
    schedule();

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stopPolling(); else schedule();
    });

    function stopPolling() {
      if (timer) { clearTimeout(timer); timer = null; }
      if (aborter) { aborter.abort(); aborter = null; }
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
          cache: "no-store"
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();
        apply(box, d);        // ⬅︎ 수치 및 게이지 갱신
        retryMs = 0;
      } catch (e) {
        showError(box, `불러오기 실패: ${e.message}`);
        retryMs = Math.min(retryMs ? retryMs * 2 : 30000, 30000);
      } finally {
        schedule();
      }
    }

    function ensureMarkup(container) {
      container.innerHTML = `
        <div class="sentiment-header" style="gap:8px; margin-bottom:8px; flex-wrap:wrap;">
          <p style="margin:6px 0;">오늘 평균: <strong id="emoa-avg">-</strong></p>
          <p style="margin:6px 0;">전체 평균: <strong id="emoa-overall">-</strong></p>
        </div>

        <div id="emoa-gauge" class="emoa-gauge">
          <div class="emoa-track"></div>
          <div class="emoa-marker emoa-marker--today"><span class="emoa-label">오늘</span></div>
          <div class="emoa-marker emoa-marker--overall"><span class="emoa-label">전체</span></div>
          <div class="emoa-bubble-merged" style="display:none;">
            <span class="dot dot--today"></span><span class="kv kv-left">오늘</span>
            <span class="sep">|</span>
            <span class="dot"></span><span class="kv kv-right">전체</span>
            <i class="stem"></i>
          </div>
          <div class="emoa-scale">
            <span>0</span><span>10</span><span>20</span><span>30</span><span>40</span><span>50</span>
          </div>
        </div>

        <p id="emoa-judge" class="emoa-judge muted" style="margin:6px 0 0;">
          오늘은 전체 대비 <b id="emoa-diff">-</b>, <span id="emoa-tone"></span>
        </p>

        <small id="emoa-note" class="muted" style="display:block; margin-top:6px;">
          기사별 감성점수를 0–100으로 표준화한 뒤 평균합니다.<br>표시 바는 0–50 구간만 보여줍니다.
        </small>

        <p class="emoa-error" style="display:none; color:#c0392b; text-align:center; margin-top:6px;"></p>
      `;
    }

    function animateNumber($el, from, to, { duration = 600, signed = false } = {}) {
      if (!Number.isFinite(from)) from = 0;
      if (!Number.isFinite(to)) { $el.textContent = "-"; return; }
      const start = performance.now();
      function frame(now) {
        const t = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - t, 3);
        const val = from + (to - from) * eased;
        const s = val.toFixed(2);
        $el.textContent = signed
          ? (val > 0 ? `+${s}` : val < 0 ? s : `+0.00`)
          : s;
        if (t < 1) requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);
    }

    function apply(container, d) {
      const $avg     = container.querySelector("#emoa-avg");
      const $overall = container.querySelector("#emoa-overall");
      const $gauge   = container.querySelector("#emoa-gauge");

      const today   = Number(d?.today_avg ?? d?.avg ?? NaN);
      const overall = Number(d?.overall_avg ?? NaN);

      const prevToday   = parseFloat($avg.textContent);
      const prevOverall = parseFloat($overall.textContent);
      animateNumber($avg,     prevToday,   today);
      animateNumber($overall, prevOverall, overall);

      updateJudge(container, today, overall);

      if ($gauge) drawGauge($gauge, today, overall);
    }

    function updateJudge(container, today, overall) {
      const $diff = container.querySelector("#emoa-diff");
      const $tone = container.querySelector("#emoa-tone");
      if (!$diff || !$tone) return;

      if (!Number.isFinite(today) || !Number.isFinite(overall)) {
        $diff.textContent = "-";
        $tone.textContent = "";
        return;
      }

      const prevDiff = parseFloat(($diff.textContent || "0").replace("+",""));
      const diff = +(today - overall);

      animateNumber($diff, prevDiff, diff, { duration: 600, signed: true });

      const adiff = Math.abs(diff);
      let tone;
      if (adiff < 1) tone = "전체 평균과 거의 같습니다.";
      else if (adiff < 5) tone = diff > 0 ? "조금 더 높습니다." : "조금 더 낮습니다.";
      else if (adiff < 15) tone = diff > 0 ? "뚜렷하게 높습니다." : "뚜렷하게 낮습니다.";
      else tone = diff > 0 ? "매우 높습니다." : "매우 낮습니다.";
      $tone.textContent = tone;

      const avgEl = container.querySelector("#emoa-avg");
      if (avgEl) {
        avgEl.classList.remove("emoa-flash-up","emoa-flash-down");
        avgEl.classList.add(diff > 0 ? "emoa-flash-up" : diff < 0 ? "emoa-flash-down" : "");
        setTimeout(() => avgEl.classList.remove("emoa-flash-up","emoa-flash-down"), 500);
      }
    }

    function drawGauge($gauge, today, overall) {
      const clamp = v => Math.max(0, Math.min(SCALE_MAX, Number(v)));
      const hasT = Number.isFinite(today), hasO = Number.isFinite(overall);

      const $t = $gauge.querySelector(".emoa-marker--today");
      const $o = $gauge.querySelector(".emoa-marker--overall");
      const $b = $gauge.querySelector(".emoa-bubble-merged");
      const $track = $gauge.querySelector(".emoa-track");
      const W = $track.clientWidth;

      $t.style.display = hasT ? "block" : "none";
      $o.style.display = hasO ? "block" : "none";
      $b.style.display = "none";
      if (!hasT && !hasO) return;

      const xT = hasT ? (clamp(today)/SCALE_MAX)*W : null;
      const xO = hasO ? (clamp(overall)/SCALE_MAX)*W : null;

      if (firstRender) {
        $t.style.transition = "none";
        $o.style.transition = "none";
        $b.style.transition = "none";
      } else {
        $t.style.transition = "";
        $o.style.transition = "";
        $b.style.transition = "";
      }

      if (hasT) placeMarker($t, xT, "오늘", "left");
      if (hasO) placeMarker($o, xO, "전체", "right");

      if (hasT && hasO) {
        const dist = Math.abs(xT - xO);
        const THRESH = 80;
        if (dist < THRESH) {
          $t.classList.add("hide-label");
          $o.classList.add("hide-label");
          const mid = Math.min(Math.max((xT + xO)/2, 16), W - 16);
          $b.style.left = `${mid}px`;
          $b.style.display = "flex";
        } else {
          $t.classList.remove("hide-label");
          $o.classList.remove("hide-label");
          $b.style.display = "none";
        }
      }
      firstRender = false;
    }

    function placeMarker($m, px, label, side) {
      const labelEl = $m.querySelector(".emoa-label");
      $m.style.left = `${px}px`;
      labelEl.textContent = label;
      $m.style.transform = side === "left" ? "translateX(-100%)" : "translateX(0%)";
    }

    function showError(container, msg) {
      const $err = container.querySelector(".emoa-error");
      if ($err) { $err.textContent = msg; $err.style.display = "block"; }
    }
    function withTs(url) {
      const u = new URL(url, location.origin);
      u.searchParams.set("ts", Date.now().toString());
      return u.toString();
    }
  }
})();
