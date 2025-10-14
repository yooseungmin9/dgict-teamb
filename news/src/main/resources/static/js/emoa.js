(() => {
  document.addEventListener("DOMContentLoaded", () => initEmoaRealtime());

  function initEmoaRealtime() {
    const box = document.querySelector("#panel-today-sentiment #emoa-summary");
    if (!box) return;

    const endpoint = "http://localhost:8009/emoa/score"; // FastAPI 8009
    const SCALE_MAX = 50; // ✅ 화면 표시는 0~50 스케일

    let retryMs = 0, timer = null, aborter = null;
    ensureMarkup(box);
    schedule();
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stopPolling(); else schedule();
    });

    function stopPolling(){ if(timer){clearTimeout(timer); timer=null;} if(aborter){aborter.abort(); aborter=null;} }
    function schedule(){ stopPolling(); if(document.hidden) return; timer=setTimeout(()=>tick(), retryMs||5000); }

    async function tick(){
      try{
        if (aborter) aborter.abort();
        aborter = new AbortController();
        const r = await fetch(withTs(endpoint), { signal: aborter.signal, headers:{Accept:"application/json"}, cache:"no-store" });
        if(!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();
        apply(box, d);
        retryMs = 0;
      }catch(e){
        showError(box, `불러오기 실패: ${e.message}`);
        retryMs = Math.min(retryMs ? retryMs * 2 : 30000, 30000);
      }finally{ schedule(); }
    }

    function ensureMarkup(container){
      container.innerHTML = `
        <div class="sentiment-header" style="gap:8px; margin-bottom:8px; flex-wrap:wrap;">
          <p style="margin:6px 0;">오늘 평균: <strong id="emoa-avg">-</strong></p>
          <p style="margin:6px 0;">전체 평균: <strong id="emoa-overall">-</strong></p>
        </div>

        <div id="emoa-gauge" class="emoa-gauge">
          <div class="emoa-track"></div>

          <!-- 마커(세로선). 라벨은 텍스트만(숫자 X) -->
          <div class="emoa-marker emoa-marker--today"><span class="emoa-label">오늘</span></div>
          <div class="emoa-marker emoa-marker--overall"><span class="emoa-label">전체</span></div>

          <!-- 가까우면 합쳐진 배지 -->
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

        <!-- 평가 문구 -->
        <p id="emoa-judge" class="emoa-judge muted" style="margin:6px 0 0;"></p>

        <!-- 간결한 계산 방식 안내 -->
        <small id="emoa-note" class="muted" style="display:block; margin-top:6px;">
          기사별 감성점수를 0–100으로 표준화한 뒤 평균합니다.<br>표시 바는 0–50 구간만 보여줍니다.
        </small>

        <p class="emoa-error" style="display:none; color:#c0392b; text-align:center; margin-top:6px;"></p>
      `;
    }

    function apply(container, d){
      const $avg     = container.querySelector("#emoa-avg");
      const $overall = container.querySelector("#emoa-overall");
      const $judge   = container.querySelector("#emoa-judge");
      const $gauge   = container.querySelector("#emoa-gauge");

      const today   = Number(d?.today_avg ?? d?.avg ?? NaN);
      const overall = Number(d?.overall_avg ?? NaN);

      if ($avg)     $avg.textContent = Number.isFinite(today)   ? today.toFixed(2)   : "-";
      if ($overall) $overall.textContent = Number.isFinite(overall) ? overall.toFixed(2) : "-";
      if ($judge)   $judge.innerHTML = renderJudgement(today, overall);
      if ($gauge)   drawGauge($gauge, today, overall);
    }

    function renderJudgement(today, overall){
      if (!Number.isFinite(today) || !Number.isFinite(overall)) return "";
      const diff = +(today - overall).toFixed(2);
      const sign = diff > 0 ? "+" : diff < 0 ? "-" : "";           // ✅ 부호
      const adiff = Math.abs(diff);

      let tone;
      if (adiff < 1) tone = "전체 평균과 거의 같습니다.";
      else if (adiff < 5) tone = diff > 0 ? "조금 더 높습니다." : "조금 더 낮습니다.";
      else if (adiff < 15) tone = diff > 0 ? "뚜렷하게 높습니다." : "뚜렷하게 낮습니다.";
      else tone = diff > 0 ? "매우 높습니다." : "매우 낮습니다.";

      const color = diff > 0 ? "#e74c3c" : diff < 0 ? "#3498db" : "#555";
      return `<span style="color:#000000">오늘은 전체 대비 <b>${sign}${adiff.toFixed(2)}</b>, ${tone}</span>`;
    }

    function drawGauge($gauge, today, overall){
      const clamp = v => Math.max(0, Math.min(SCALE_MAX, Number(v))); // 0~50
      const hasT = Number.isFinite(today), hasO = Number.isFinite(overall);

      const $t = $gauge.querySelector(".emoa-marker--today");
      const $o = $gauge.querySelector(".emoa-marker--overall");
      const $b = $gauge.querySelector(".emoa-bubble-merged");
      const $track = $gauge.querySelector(".emoa-track");
      const W = $track.clientWidth;

      // 마커(세로선)는 항상 보이게
      $t.style.display = hasT ? "block" : "none";
      $o.style.display = hasO ? "block" : "none";
      $b.style.display = "none";

      if (!hasT && !hasO) return;

      const xT = hasT ? (clamp(today)/SCALE_MAX)*W : null;
      const xO = hasO ? (clamp(overall)/SCALE_MAX)*W : null;

      if (hasT && hasO){
        const todayIsLeft = xT <= xO; // ✅ 작은 값 = 왼쪽
        // 개별 라벨도 크기에 맞춰 좌/우로 고정
        placeMarker($t, xT, "오늘",  todayIsLeft ? "left"  : "right");
        placeMarker($o, xO, "전체",  todayIsLeft ? "right" : "left");

        const dist = Math.abs(xT - xO);
        const THRESH = 80; // px 가까우면 합쳐진 배지로 전환
        if (dist < THRESH){
          $t.classList.add("hide-label");
          $o.classList.add("hide-label");
          const mid = Math.min(Math.max((xT + xO)/2, 16), W - 16);
          $b.style.left = `${mid}px`;
          // 합쳐진 배지도 '왼쪽=작은 값, 오른쪽=큰 값' 순서로 라벨
          if (todayIsLeft) {
            $b.innerHTML = `
              <span class="dot dot--today"></span><span class="kv kv-left">오늘</span>
              <span class="sep">|</span>
              <span class="dot"></span><span class="kv kv-right">전체</span>
              <i class="stem"></i>
            `;
          } else {
            $b.innerHTML = `
              <span class="dot"></span><span class="kv kv-left">전체</span>
              <span class="sep">|</span>
              <span class="dot dot--today"></span><span class="kv kv-right">오늘</span>
              <i class="stem"></i>
            `;
          }
          $b.style.display = "flex";
        } else {
          $t.classList.remove("hide-label");
          $o.classList.remove("hide-label");
          $b.style.display = "none";
        }
      } else {
        // 하나만 있을 때는 기본 방향으로
        if (hasT) placeMarker($t, xT, "오늘", "left");
        if (hasO) placeMarker($o, xO, "전체", "right");
      }
    }

    function placeMarker($m, px, label, side){
      const labelEl = $m.querySelector(".emoa-label");
      $m.style.left = `${px}px`;
      labelEl.textContent = label;           // 숫자 없이 라벨만
      $m.style.transform = side === "left" ? "translateX(-100%)" : "translateX(0%)";
    }

    function showError(container, msg){
      const $err = container.querySelector(".emoa-error");
      if ($err){ $err.textContent = msg; $err.style.display = "block"; }
    }
    function withTs(url){
      const u = new URL(url, location.origin);
      u.searchParams.set("ts", Date.now().toString());
      return u.toString();
    }
  }
})();
