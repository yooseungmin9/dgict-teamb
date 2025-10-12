// /js/trends.js — 키워드 랭킹: 실시간 폴링 + 애니메이션 [PEP8? → JS는 Airbnb 가이드][입문자 주석 포함]
/* 글로벌 IIFE 유지 */
(function DB_trendsWidgets(){
  // ===== 공통 fetch 유틸 =====
  const fetchJSON = async (url, params = {}) => {
    const q = new URLSearchParams(params).toString();
    const final = q ? (url + (url.includes('?') ? '&' : '?') + q) : url;
    const r = await fetch(final, { signal: DB_kwFetchCtrl?.signal });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  };

  // ====== (A) 기존: 카테고리 트렌드 (변경 없음) ======
  let DB_trendChart;
  async function DB_initCategoryTrends(){
    const elDays = document.getElementById('DB_trendDays');
    if (!elDays) return;
    const days = elDays.value;
    const data = await fetchJSON('/api/dashboard/trends/category-trends', { days });
    const ctx = document.getElementById('DB_categoryTrendChart');
    if (!ctx) return;

    const colorMap = {
      '증권':'#1f77b4','금융':'#ff7f0e','부동산':'#2ca02c',
      '산업':'#d62728','글로벌경제':'#9467bd','일반':'#8c564b'
    };
    const labels = data.dates || [];
    const datasets = Object.keys(data.categories || {}).map(cat => {
      const color = colorMap[cat] || 'gray';
      return {
        label: cat,
        data: data.categories[cat] || [],
        borderColor: color,
        backgroundColor: `${color}55`,
        fill: false, tension: 0.3, borderWidth: 2, pointRadius: 2
      };
    });

    if (DB_trendChart) DB_trendChart.destroy();
    DB_trendChart = new Chart(ctx, {
      type: 'line',
      data: { labels, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'top' } },
        interaction: { mode: 'nearest', axis: 'x', intersect: false },
        scales: {
          x: { ticks: { autoSkip: true, maxTicksLimit: 8 } },
          y: { beginAtZero: true, title: { display: true, text: '언급량(건)' } }
        }
      }
    });
  }
  document.getElementById('DB_trendDays')?.addEventListener('change', DB_initCategoryTrends);

  // ====== (B) 키워드 랭킹: 실시간 + 애니메이션 ======
  const CATEGORY_TABS = ['금융','부동산','산업','글로벌경제','일반'];
  let DB_KW_MODE = 'category';
  let DB_CURRENT_CAT = '금융';
  let DB_KW_RAW = [];
  let DB_kwTimer = null;
  let DB_kwFetchCtrl = null;
  const POLL_MS = 10_000;      // 폴링 주기(밀리초)
  const ANIM_MS = 600;         // 행 이동 애니메이션 시간
  const HILITE_MS = 1000;      // 상승/하락 하이라이트 유지 시간

  function DB_buildKwTabs(){
    const wrap = document.getElementById('DB_kwTabs');
    if (!wrap) return;
    wrap.style.display = (DB_KW_MODE === 'category') ? 'flex' : 'none';
    wrap.innerHTML = '';
    CATEGORY_TABS.forEach(cat => {
      const btn = document.createElement('button');
      btn.className = 'chip' + (cat === DB_CURRENT_CAT ? ' active' : '');
      btn.textContent = cat;
      btn.addEventListener('click', async () => {
        DB_CURRENT_CAT = cat;
        DB_buildKwTabs();
        await DB_loadKeywordRanking(true); // 즉시 갱신
      });
      wrap.appendChild(btn);
    });
  }

  function DB_toggleCategoryColumn(show){
    const table = document.getElementById('DB_kwTable');
    if (!table) return;
    if (show) table.classList.remove('hide-category');
    else table.classList.add('hide-category');
  }

  function DB_setKwMode(mode){
    DB_KW_MODE = mode;
    DB_toggleCategoryColumn(mode === 'global');
    const tabs = document.getElementById('DB_kwTabs');
    if (tabs) tabs.style.display = (mode === 'category') ? 'flex' : 'none';
    DB_buildKwTabs();
    DB_loadKeywordRanking(true); // 즉시 갱신
  }

  // ===== 핵심: FLIP 애니메이션 렌더러 =====
  function DB_diffRenderKwTable(){
    const tbody = document.getElementById('DB_keywordRankingBody');
    if (!tbody) return;

    const topN = 10;
    const nextRows = (DB_KW_RAW || []).slice(0, topN);

    // 1) 기존 위치 측정(First)
    const oldPos = new Map();       // key=keyword, val=DOMRect.top
    const oldCount = new Map();     // 이전 count
    const oldMap = new Map();       // key=keyword, val=<tr>
    Array.from(tbody.children).forEach(tr => {
      const key = tr.dataset.key;
      if (!key) return;
      oldMap.set(key, tr);
      oldPos.set(key, tr.getBoundingClientRect().top);
      const cnt = Number(tr.querySelector('[data-cell="count"]')?.dataset.value || '0');
      oldCount.set(key, cnt);
    });

    // 2) 새 DOM 생성(Last)
    const frag = document.createDocumentFragment();
    nextRows.forEach((r, idx) => {
      const tr = document.createElement('tr');
      tr.dataset.key = r.keyword ?? `__${idx}`;
      tr.innerHTML = `
        <td data-cell="rank" class="rank">${r.rank ?? (idx+1)}</td>
        <td data-cell="kw">${r.keyword ?? '-'}</td>
        <td data-cell="count" class="right" data-value="${r.count ?? 0}">${(r.count ?? 0).toLocaleString()}</td>
      `;
      frag.appendChild(tr);
    });

    // 3) 교체 후 위치 측정
    tbody.innerHTML = '';
    tbody.appendChild(frag);

    const newPos = new Map();
    Array.from(tbody.children).forEach(tr => {
      const key = tr.dataset.key;
      newPos.set(key, tr.getBoundingClientRect().top);
    });

    // 4) Invert + Play
    Array.from(tbody.children).forEach(tr => {
      const key = tr.dataset.key;
      const was = oldPos.get(key);
      const now = newPos.get(key);
      const deltaY = (was != null && now != null) ? (was - now) : 0;

      // 위치 애니메이션
      if (deltaY !== 0) {
        tr.animate(
          [
            { transform: `translateY(${deltaY}px)` },
            { transform: 'translateY(0px)' }
          ],
          { duration: ANIM_MS, easing: 'ease' }
        );
      } else if (!oldMap.has(key)) {
        // 신규 진입: 살짝 위에서 페이드인
        tr.animate(
          [
            { transform: 'translateY(-6px)', opacity: 0 },
            { transform: 'translateY(0)',    opacity: 1 }
          ],
          { duration: ANIM_MS, easing: 'ease' }
        );
      }

      // 숫자 트윈 + 상승/하락 하이라이트
      const countEl = tr.querySelector('[data-cell="count"]');
      const newVal = Number(countEl?.dataset.value || '0');
      const prevVal = oldCount.get(key);
      if (Number.isFinite(prevVal) && prevVal !== newVal) {
        const up = newVal > prevVal;
        tr.classList.remove('up','down');
        tr.classList.add(up ? 'up' : 'down');
        setTimeout(() => tr.classList.remove('up','down'), HILITE_MS);

        // 텍스트 트윈(입문자용: requestAnimationFrame으로 자연스럽게 숫자 변경)
        const start = performance.now();
        const dur = Math.min(ANIM_MS, 900);
        const from = prevVal;
        const to = newVal;

        function step(t){
          const k = Math.min(1, (t - start) / dur);
          const v = Math.round(from + (to - from) * k);
          if (countEl) countEl.textContent = v.toLocaleString();
          if (k < 1) requestAnimationFrame(step);
          else if (countEl) countEl.textContent = to.toLocaleString();
        }
        requestAnimationFrame(step);
      }
    });
  }

  // ===== 데이터 로드 후 렌더 =====
  async function DB_loadKeywordRanking(immediate = false){
    // 겹치는 요청 방지
    if (DB_kwFetchCtrl) DB_kwFetchCtrl.abort();
    DB_kwFetchCtrl = new AbortController();

    const days = document.getElementById('DB_kwDays')?.value || '30';
    let rows = [];

    if (DB_KW_MODE === 'category') {
      const categoryParam = DB_CURRENT_CAT;
      rows = await fetchJSON('/api/dashboard/keywords/ranking', { category: categoryParam, days });
      // rank 보정
      rows = (rows || [])
        .sort((a,b)=> (b.count||0) - (a.count||0))
        .map((r, i)=> ({ ...r, rank: i+1, category: categoryParam }));
      DB_KW_RAW = rows;
    } else {
      // 통합 모드: 각 카테고리 합산
      const allRows = [];
      for (const cat of CATEGORY_TABS) {
        const part = await fetchJSON('/api/dashboard/keywords/ranking', { category: cat, days });
        allRows.push(...(part || []));
      }
      const byWord = new Map();
      for (const r of allRows) byWord.set(r.keyword, (byWord.get(r.keyword)||0) + (r.count||0));
      rows = Array.from(byWord.entries())
        .map(([keyword, count]) => ({ keyword, count }))
        .sort((a,b)=> b.count - a.count)
        .slice(0, 50)
        .map((r, idx) => ({ rank: idx + 1, keyword: r.keyword, count: r.count, category: '-' }));
      DB_KW_RAW = rows;
    }

    DB_diffRenderKwTable();

    if (immediate) {
      // 즉시 호출 시 타이머를 재설정하여 간격을 유지
      DB_stopKwPolling();
      DB_startKwPolling();
    }
  }

  // ===== 폴링 제어 =====
  function DB_startKwPolling(){
    if (DB_kwTimer) return;
    DB_kwTimer = setInterval(() => {
      if (document.hidden) return; // 비가시 시 정지
      DB_loadKeywordRanking(false).catch(console.error);
    }, POLL_MS);
  }
  function DB_stopKwPolling(){
    if (DB_kwTimer) clearInterval(DB_kwTimer);
    DB_kwTimer = null;
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) DB_stopKwPolling();
    else DB_startKwPolling();
  });

  // ===== UI 이벤트 바인딩 =====
  document.getElementById('DB_kwDays')?.addEventListener('change', () => DB_loadKeywordRanking(true));
  document.querySelectorAll('input[name="DB_kwMode"]')
    .forEach(r => r.addEventListener('change', e => DB_setKwMode(e.target.value)));

  // ===== 초기 실행 =====
  (async function init(){
    await DB_initCategoryTrends();
    DB_buildKwTabs();
    await DB_loadKeywordRanking(true);
    DB_setKwMode('category'); // 기본
    DB_startKwPolling();
  })();

  // ===== 간단 테스트(개발용): 목업 데이터로 강제 렌더 =====
  // 콘솔에서 window.DB_kwMock() 호출 → 애니메이션 확인
  window.DB_kwMock = function(){
    DB_KW_MODE = 'category';
    DB_CURRENT_CAT = '금융';
    DB_KW_RAW = Array.from({length:12}).map((_,i)=>({
      rank: i+1, keyword: 'KW'+(i+1), count: Math.round(Math.random()*500+50), category:'금융'
    })).sort((a,b)=> b.count-a.count).map((r,i)=>({...r, rank:i+1}));
    DB_diffRenderKwTable();
  };
})();
