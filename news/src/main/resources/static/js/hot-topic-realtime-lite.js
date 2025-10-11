(() => {
  const API = 'http://localhost:8007/keywords/top';
  const TOP_N_FETCH = 20;        // 바뀜 감지를 위해 넉넉히
  const TOP_N_VIEW  = 5;         // 화면엔 TOP5
  const POLL_MS = 3_000;
  const MAX_BACKOFF_MS = 5 * 60_000;

  const $root = document.getElementById('hot-topic-body');
  if (!$root) return;

  let running = false;
  let backoff = 0;
  let timerId = null;
  let aborter = null;

  // ====== DOM 접근 헬퍼(원래 모양 가정) ======
  const rowsWrap = () => $root.firstElementChild || $root;
  const rowsList = () => Array.from(rowsWrap().children || []);

  function pickKeywordEl(row) { return row?.children?.[1]?.children?.[0] ?? null; }
  function pickMetaBox  (row) { return row?.children?.[1]?.children?.[1] ?? null; }
  function pickCountEl  (row) { return pickMetaBox(row)?.querySelector('span') || null; }

  // ====== 숫자 카운트업(모양 불변) ======
  function animateCountText($el, to, ms = 600) {
    if (!$el) return;
    const nowAttr = Number($el.dataset.value ?? '');
    const from = Number.isFinite(nowAttr) ? nowAttr : Number(($el.textContent || '').replace(/\D/g, '')) || 0;
    const target = Math.max(0, Number(to) || 0);
    if (from === target) return;
    $el.dataset.value = String(target);
    const start = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - start) / ms);
      const ease = 1 - Math.pow(1 - k, 3);
      const val = Math.round(from + (target - from) * ease);
      $el.textContent = `언급 ${val}건`;
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  // ====== 비교 모델(원래 규칙 유지: change desc) ======
  function computeCompared(today, yesterday) {
    const yMap = new Map(yesterday.map((k) => [String(k.keyword), Number(k.count) || 0]));
    return today.map((k) => {
      const prev = yMap.get(String(k.keyword)) || 0;
      const change = Number(k.count) - prev;
      return {
        keyword: String(k.keyword),
        count: Number(k.count),
        change,
        changePercent: prev > 0 ? ((change / prev) * 100).toFixed(1) : '신규',
        isNew: prev === 0,
      };
    });
  }
  function sortCompared(list) {
    return [...list].sort((a, b) => b.change - a.change || b.count - a.count || a.keyword.localeCompare(b.keyword));
  }

  function getCurrKeys() {
    return rowsList().slice(0, TOP_N_VIEW).map((r) => (pickKeywordEl(r)?.textContent || '').trim());
  }

  // ====== 원래 모양 템플릿(초기 hot-topic.js와 동일 형태) ======
  function rowHTML(item, idx) {
    const emoji = item.change > 0 ? '🔥' : item.change < 0 ? '📉' : '➖';
    const color = item.change > 0 ? '#e74c3c' : item.change < 0 ? '#3498db' : '#95a5a6';
    return `
      <div style="display:flex; align-items:center; gap:12px; padding:10px; background:#f8f9fa; border-radius:6px; border-left:4px solid ${color};">
        <div style="font-size:20px; font-weight:bold; color:${color}; min-width:30px;">${idx + 1}</div>
        <div style="flex:1;">
          <div style="font-size:15px; font-weight:600; margin-bottom:4px;">${item.keyword}</div>
          <div style="font-size:12px; color:#666;">
            <span>언급 ${item.count}건</span>
            <span style="margin-left:8px; color:${color};">
              ${item.isNew
                ? `${emoji} 신규`
                : item.change > 0
                ? `${emoji} +${item.change}건 (↑${item.changePercent}%)`
                : item.change < 0
                ? `${emoji} ${item.change}건 (↓${Math.abs(item.changePercent)}%)`
                : '변동없음'}
            </span>
          </div>
        </div>
      </div>`;
  }

  // ====== FLIP + EXIT/ENTER 적용 재배치 ======
  async function applyTop5WithAnimations(newModels, data) {
    const wrap = rowsWrap();
    const currRows = rowsList();
    const currMap  = new Map(currRows.map((r) => [(pickKeywordEl(r)?.textContent || '').trim(), r]));
    const newTop5  = newModels.slice(0, TOP_N_VIEW);
    const newKeys  = newTop5.map((m) => m.keyword);
    const currKeys = currRows.slice(0, TOP_N_VIEW).map((r) => (pickKeywordEl(r)?.textContent || '').trim());

    const toExit = currKeys.filter((k) => !newKeys.includes(k));
    const toKeep = currKeys.filter((k) => newKeys.includes(k));
    const toEnter= newKeys.filter((k) => !currKeys.includes(k));

    // 1) EXIT: 나갈 행은 높이를 미리 변수에 저장 후 collapse
    for (const k of toExit) {
      const row = currMap.get(k);
      if (!row) continue;
      row.style.setProperty('--row-h', `${row.getBoundingClientRect().height}px`);
      row.classList.add('hot-exit');
    }
    // EXIT 끝날 때까지 대기 후 제거
    if (toExit.length) {
      await Promise.allSettled(
        toExit.map((k) => new Promise((res) => {
          const row = currMap.get(k);
          if (!row) return res();
          row.addEventListener('animationend', () => { row.remove(); res(); }, { once: true });
        }))
      );
    }

    // 2) FLIP 준비: 남아있는 행들 First rect 측정
    const firstRects = new Map();
    for (const k of toKeep) {
      const r = currMap.get(k);
      if (r) firstRects.set(k, r.getBoundingClientRect());
    }

    // 3) 새 TOP5 DOM 구성: 남는 행은 재사용, 새로 들어올 행은 생성(원래 모양)
    const fragment = document.createDocumentFragment();
    newTop5.forEach((m, idx) => {
      const exist = currMap.get(m.keyword);
      if (exist) {
        // 텍스트만 최신화(순위/변화치). 숫자 span은 이후 카운트업.
        const rankEl = exist.children?.[0];
        if (rankEl) rankEl.textContent = String(idx + 1);
        const metaBox = pickMetaBox(exist);
        const countEl = pickCountEl(exist);
        if (countEl) countEl.textContent = `언급 ${m.count}건`;
        if (metaBox) {
          const color = m.change > 0 ? '#e74c3c' : m.change < 0 ? '#3498db' : '#95a5a6';
          const delta = metaBox.querySelector('span + span');
          if (delta) {
            const emoji = m.change > 0 ? '🔥' : m.change < 0 ? '📉' : '➖';
            delta.style.color = color;
            delta.textContent =
              m.isNew ? `${emoji} 신규`
              : m.change > 0 ? `${emoji} +${m.change}건 (↑${m.changePercent}%)`
              : m.change < 0 ? `${emoji} ${m.change}건 (↓${Math.abs(m.changePercent)}%)`
              : '변동없음';
          }
        }
        fragment.appendChild(exist);
      } else {
        // ENTER: 새 행 생성
        const temp = document.createElement('div');
        temp.innerHTML = rowHTML(m, idx);
        const row = temp.firstElementChild;
        row.classList.add('hot-enter'); // 등장 애니메이션
        fragment.appendChild(row);
      }
    });

    // 4) 래퍼 비우고 새 순서로 삽입
    wrap.innerHTML = '';
    wrap.appendChild(fragment);

    // 5) FLIP 실행: 남아있던 행들에만 적용
    const anims = [];
    newKeys.forEach((k) => {
      if (!firstRects.has(k)) return; // 새로 들어온 것은 FLIP 대상 아님
      const row = rowsList().find((r) => (pickKeywordEl(r)?.textContent || '').trim() === k);
      if (!row) return;
      const first = firstRects.get(k);
      const last  = row.getBoundingClientRect();
      const dx = first.left - last.left;
      const dy = first.top  - last.top;

      row.classList.add('hot-flipping');
      row.style.transformOrigin = '0 0';
      row.style.transform = `translate(${dx}px, ${dy}px)`;

      const anim = row.animate(
        [{ transform: `translate(${dx}px, ${dy}px)`, opacity: 0.9 }, { transform: 'translate(0,0)', opacity: 1 }],
        { duration: 500, easing: 'cubic-bezier(.2,.8,.2,1)' }
      );
      anim.addEventListener('finish', () => {
        row.style.transform = '';
        row.classList.remove('hot-flipping');
      });
      anims.push(anim);
    });
    await Promise.allSettled(anims.map((a) => a.finished));

    // 6) 숫자 카운트업: 남아있던 키워드는 count만 부드럽게
    const tMap = new Map(newTop5.map((m) => [m.keyword, m.count]));
    rowsList().forEach((row) => {
      const key = (pickKeywordEl(row)?.textContent || '').trim();
      const $cnt = pickCountEl(row);
      if ($cnt && tMap.has(key)) animateCountText($cnt, tMap.get(key));
    });

    // 7) 다른 모듈을 위한 이벤트(유지)
    window.dispatchEvent(new CustomEvent('hot:realtime:data', { detail: data }));
  }

  // ====== 기존 행 유지 업데이트(멤버십 동일 시) ======
  function updateExistingRows(today, yesterday) {
    const tMap = new Map(today.map((d) => [String(d.keyword), Number(d.count) || 0]));
    for (const row of rowsList()) {
      const key = (pickKeywordEl(row)?.textContent || '').trim();
      const $cnt = pickCountEl(row);
      if ($cnt && tMap.has(key)) animateCountText($cnt, tMap.get(key));
    }
  }

  // ====== 폴링 ======
  async function fetchAndApply() {
    if (running) return;
    running = true;
    if (aborter) aborter.abort();
    aborter = new AbortController();

    try {
      const url = `${API}?top_n=${TOP_N_FETCH}&ts=${Date.now()}`;
      const res = await fetch(url, { signal: aborter.signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!Array.isArray(data.today) || !Array.isArray(data.yesterday)) throw new Error('데이터 구조 오류');

      const models = sortCompared(computeCompared(data.today, data.yesterday));
      const newKeys = models.slice(0, TOP_N_VIEW).map((m) => m.keyword);
      const curKeys = getCurrKeys();

      const changed =
        newKeys.length !== curKeys.length || newKeys.some((k, i) => k !== curKeys[i]);

      if (changed) {
        await applyTop5WithAnimations(models, data); // EXIT/ENTER + FLIP
      } else {
        updateExistingRows(data.today, data.yesterday); // 숫자만
        // 이벤트 유지
        window.dispatchEvent(new CustomEvent('hot:realtime:data', { detail: data }));
      }

      backoff = 0;
    } catch (e) {
      console.error('[realtime-lite]', e);
      backoff = Math.min(backoff ? backoff * 2 : 5_000, MAX_BACKOFF_MS);
    } finally {
      running = false;
    }
  }

  function schedule() {
    clearTimeout(timerId);
    if (document.hidden) {
      timerId = setTimeout(schedule, 3_000);
      return;
    }
    const delay = backoff || 0;
    timerId = setTimeout(async () => {
      await fetchAndApply();
      timerId = setTimeout(schedule, backoff || POLL_MS);
    }, delay);
  }

  document.addEventListener('visibilitychange', () => {
    if (document.hidden && aborter) aborter.abort();
    schedule();
  });

  schedule();
})();