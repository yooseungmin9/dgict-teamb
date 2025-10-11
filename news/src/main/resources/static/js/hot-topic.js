(() => {
  const API = 'http://localhost:8007/keywords/top';
  const TOP_N_FETCH = 20; // 내부 유지 개수
  const TOP_N_VIEW = 5; // 화면 노출 개수
  const POLL_MS = 10_000;
  const MAX_BACKOFF_MS = 5 * 60_000;

  const $root = document.getElementById('hot-topic-body');
  if (!$root) return; // 루트 없으면 종료

  const $wrap = $root.querySelector('.hot-topic__list') || $root;

  let running = false;
  let backoff = 0;
  let timerId = null;
  let aborter = null;

  // ===== DOM 유틸 =====
  const qRowsAll = () => Array.from($wrap.children || []);

  const keyOf = (row) => row?.dataset?.key || '';
  const pickKeyEl = (row) => row.querySelector('.hot-key');
  const pickMetaBox = (row) => row.querySelector('.hot-meta');
  const pickCountEl = (row) => row.querySelector('.hot-meta > span');

  // ===== 숫자 카운트업 =====
  function animateCountText($el, to, ms = 600) {
    if (!$el) return;
    const nowAttr = Number($el.dataset.value ?? '');
    const from = Number.isFinite(nowAttr)
      ? nowAttr
      : Number(($el.textContent || '').replace(/\D/g, '')) || 0;
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

  // ===== 비교/정렬 =====
  function computeCompared(today, yesterday) {
    const yMap = new Map(
      yesterday.map((k) => [String(k.keyword), Number(k.count) || 0]),
    );
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
    return [...list].sort(
      (a, b) =>
        b.change - a.change || b.count - a.count || a.keyword.localeCompare(b.keyword),
    );
  }

  // ===== 행 생성(한 번만 생성, 이후 재사용) =====
  function ensureRow(item) {
    const key = item.keyword;
    let row = qRowsAll().find((r) => keyOf(r) === key);
    if (row) return row;

    // 신규 행 DOM 생성
    row = document.createElement('div');
    row.className = 'hot-row';
    row.dataset.key = key;

    const rankEl = document.createElement('div');
    rankEl.className = 'hot-rank';
    rankEl.textContent = '-';

    const mainEl = document.createElement('div');
    mainEl.className = 'hot-main';

    const keyEl = document.createElement('div');
    keyEl.className = 'hot-key';
    keyEl.textContent = key;

    const metaEl = document.createElement('div');
    metaEl.className = 'hot-meta';

    const countEl = document.createElement('span');
    countEl.textContent = `언급 ${item.count}건`;

    const deltaEl = document.createElement('span');
    deltaEl.className = 'hot-delta';
    deltaEl.textContent = '변동없음';

    metaEl.appendChild(countEl);
    metaEl.appendChild(deltaEl);
    mainEl.appendChild(keyEl);
    mainEl.appendChild(metaEl);

    row.appendChild(rankEl);
    row.appendChild(mainEl);

    // 최초에는 숨김(필요 시 표시)
    row.classList.add('hot-hidden');

    $wrap.appendChild(row);
    return row;
  }

  // ===== 색/이모지 갱신 =====
  function colorOf(change) {
    if (change > 0) return '#e74c3c'; // 상승(레드)
    if (change < 0) return '#3498db'; // 하락(블루)
    return '#95a5a6'; // 보합(그레이)
  }
  function emojiOf(change) {
    if (change > 0) return '🔥';
    if (change < 0) return '📉';
    return '➖';
  }

  // ===== TOP5 반영: EXIT → FLIP → ENTER =====
  async function applyWithAnimations(models, rawData) {
    const topN = models.slice(0, TOP_N_FETCH);
    const top5 = models.slice(0, TOP_N_VIEW);
    const newKeys = top5.map((m) => m.keyword);

    // 0) 모든 모델에 대한 행을 보장(6위 이후는 숨김 상태 유지)
    topN.forEach((m) => ensureRow(m));

    // 1) EXIT: 현재 노출되던 TOP5 중 새 TOP5에 없는 항목은 exit 후 숨김 처리
    const currVisible = qRowsAll()
      .filter((r) => !r.classList.contains('hot-hidden'))
      .slice(0, TOP_N_VIEW);
    const toExit = currVisible
      .map((r) => keyOf(r))
      .filter((k) => !newKeys.includes(k));
    for (const k of toExit) {
      const row = qRowsAll().find((r) => keyOf(r) === k);
      if (!row) continue;
      row.style.setProperty('--row-h', `${row.getBoundingClientRect().height}px`);
      row.classList.add('hot-exit');
    }
    if (toExit.length) {
      await Promise.allSettled(
        toExit.map(
          (k) =>
            new Promise((res) => {
              const row = qRowsAll().find((r) => keyOf(r) === k);
              if (!row) return res();
              row.addEventListener(
                'animationend',
                () => {
                  row.classList.remove('hot-exit');
                  row.classList.add('hot-hidden'); // DOM 보존 + 비가시화
                  res();
                },
                { once: true },
              );
            }),
        ),
      );
    }

    // 2) FLIP 준비: 새로 유지될 키들 중 현재 화면에 있던 것의 first rect 측정
    const firstRects = new Map();
    const toKeep = newKeys.filter((k) => currVisible.some((r) => keyOf(r) === k));
    toKeep.forEach((k) => {
      const r = qRowsAll().find((x) => keyOf(x) === k);
      if (r) firstRects.set(k, r.getBoundingClientRect());
    });

    // 3) 랭크·텍스트 최신화 + ENTER 표시 준비
    top5.forEach((m, idx) => {
      const row = ensureRow(m);
      const color = colorOf(m.change);
      const rankEl = row.querySelector('.hot-rank');
      const keyEl = pickKeyEl(row);
      const metaEl = pickMetaBox(row);
      const countEl = pickCountEl(row);
      const deltaEl = metaEl?.querySelector('.hot-delta');

      row.style.borderLeftColor = color;
      if (rankEl) {
        rankEl.textContent = String(idx + 1);
        rankEl.style.color = color;
      }
      if (keyEl) keyEl.textContent = m.keyword;
      if (countEl) countEl.textContent = `언급 ${m.count}건`;
      if (deltaEl) {
        deltaEl.style.color = color;
        deltaEl.textContent = m.isNew
          ? `${emojiOf(m.change)} 신규`
          : m.change > 0
          ? `${emojiOf(m.change)} +${m.change}건 (↑${m.changePercent}%)`
          : m.change < 0
          ? `${emojiOf(m.change)} ${m.change}건 (↓${Math.abs(m.changePercent)}%)`
          : '변동없음';
      }

      // 숨겨져 있었다면 ENTER로 표시
      if (row.classList.contains('hot-hidden')) {
        row.classList.remove('hot-hidden');
        row.classList.add('hot-enter');
        row.addEventListener('animationend', () => row.classList.remove('hot-enter'), {
          once: true,
        });
      }
    });

    // 4) 표시 순서 재정렬: 래퍼 안에서 top5를 위로, 나머지는 뒤로
    //    DOM은 모두 유지하되, 6위 이후는 hot-hidden으로 비가시화
    const frag = document.createDocumentFragment();
    top5.forEach((m) => {
      const row = qRowsAll().find((r) => keyOf(r) === m.keyword);
      if (row) frag.appendChild(row);
    });
    // 나머지 TOP_N_FETCH(6위~)는 뒤쪽에 보관(숨김)
    qRowsAll()
      .filter((r) => !newKeys.includes(keyOf(r)))
      .forEach((r) => frag.appendChild(r));
    $wrap.innerHTML = '';
    $wrap.appendChild(frag);

    // 5) FLIP 실행: 유지된 항목 위치 변화만 부드럽게
    const anims = [];
    toKeep.forEach((k) => {
      const row = qRowsAll().find((r) => keyOf(r) === k);
      if (!row || !firstRects.has(k)) return;
      const first = firstRects.get(k);
      const last = row.getBoundingClientRect();
      const dx = first.left - last.left;
      const dy = first.top - last.top;

      row.classList.add('hot-flipping');
      row.style.transform = `translate(${dx}px, ${dy}px)`;
      const anim = row.animate(
        [
          { transform: `translate(${dx}px, ${dy}px)`, opacity: 0.9 },
          { transform: 'translate(0,0)', opacity: 1 },
        ],
        { duration: 500, easing: 'cubic-bezier(.2,.8,.2,1)' },
      );
      anim.addEventListener('finish', () => {
        row.style.transform = '';
        row.classList.remove('hot-flipping');
      });
      anims.push(anim);
    });
    await Promise.allSettled(anims.map((a) => a.finished));

    // 6) 숫자 카운트업: 노출 중인 TOP5만 처리
    const tMap = new Map(top5.map((m) => [m.keyword, m.count]));
    qRowsAll()
      .filter((r, i) => i < TOP_N_VIEW && !r.classList.contains('hot-hidden'))
      .forEach((row) => {
        const key = keyOf(row);
        const $cnt = pickCountEl(row);
        if ($cnt && tMap.has(key)) animateCountText($cnt, tMap.get(key));
      });

    // 7) 외부 통지 이벤트 유지
    window.dispatchEvent(new CustomEvent('hot:realtime:data', { detail: rawData }));
  }

  // ===== 폴링(fetch) =====
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
      if (!Array.isArray(data.today) || !Array.isArray(data.yesterday))
        throw new Error('데이터 구조 오류');

      const models = sortCompared(computeCompared(data.today, data.yesterday));
      await applyWithAnimations(models, data);

      backoff = 0;
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('[hot-realtime-plus]', e);
      backoff = Math.min(backoff ? backoff * 2 : 5_000, MAX_BACKOFF_MS);
    } finally {
      running = false;
    }
  }

  // ===== 스케줄러 =====
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

  // ===== MOCK 테스트(선택): 임의 데이터로 재배치 확인 =====
  window.addEventListener('hot:realtime:mock', () => {
    const sample = Array.from({ length: TOP_N_FETCH }, (_, i) => ({
      keyword: `키워드${i + 1}`,
      count: Math.floor(Math.random() * 500 + 10),
    }));
    const yesterday = sample.map((d) => ({
      keyword: d.keyword,
      count: Math.max(0, d.count - Math.floor(Math.random() * 100)),
    }));
    const models = sortCompared(computeCompared(sample, yesterday));
    applyWithAnimations(models, { today: sample, yesterday });
  });

  // 시작
  schedule();
})();