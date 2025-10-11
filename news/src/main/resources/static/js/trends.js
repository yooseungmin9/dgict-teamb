// /js/trends.js — 핫토픽/랭킹 모두 스프링 BFF 경유
(function DB_trendsWidgets(){
  // ===== 공통 fetch 유틸 =====
  const fetchJSON = async (url, params = {}) => {
    const q = new URLSearchParams(params).toString();
    const final = q ? (url + (url.includes('?') ? '&' : '?') + q) : url;
    const r = await fetch(final);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  };

  // ======================================================
  // (A) 핫토픽 라인차트  → BFF: /api/dashboard/trends/category-trends
  // ======================================================
  let DB_trendChart;

  async function DB_initCategoryTrends(){
    const elDays = document.getElementById('DB_trendDays');
    if (!elDays) return;
    const days = elDays.value;

    // ✅ FastAPI 직접 호출 제거, BFF 경유
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
        fill: false,
        tension: 0.3,
        borderWidth: 2,
        pointRadius: 2
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

  // ======================================================
  // (B) 키워드 랭킹  → BFF: /api/dashboard/keywords/ranking
  // ======================================================
  const CATEGORY_TABS = ['금융', '부동산', '산업', '글로벌경제', '일반'];
  let DB_KW_MODE = 'category';
  let DB_CURRENT_CAT = '금융';
  let DB_KW_RAW = [];

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
        await DB_loadKeywordRanking();
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
    DB_loadKeywordRanking();
  }

  async function DB_loadKeywordRanking(){
    const days = document.getElementById('DB_kwDays')?.value || '30';
    let rows = [];

    if (DB_KW_MODE === 'category') {
      const categoryParam = DB_CURRENT_CAT; // '금융','부동산','산업','글로벌경제','일반'
      rows = await fetchJSON('/api/dashboard/keywords/ranking', { category: categoryParam, days });
      DB_KW_RAW = (rows || []).map(r => ({ ...r, category: categoryParam }));
    } else {
      // 통합 모드: 각 카테고리를 조회해 합산
      const allRows = [];
      for (const cat of CATEGORY_TABS) {
        const part = await fetchJSON('/api/dashboard/keywords/ranking', { category: cat, days });
        allRows.push(...(part || []));
      }
      const byWord = new Map();
      for (const r of allRows) {
        byWord.set(r.keyword, (byWord.get(r.keyword) || 0) + (r.count || 0));
      }
      rows = Array.from(byWord.entries())
          .map(([keyword, count]) => ({ keyword, count }))
          .sort((a, b) => b.count - a.count)
          .slice(0, 50)
          .map((r, idx) => ({ rank: idx + 1, keyword: r.keyword, count: r.count, category: '-' }));
      DB_KW_RAW = rows;
    }

    DB_renderKwTable();
  }

  function DB_renderKwTable(){
    const tbody = document.getElementById('DB_keywordRankingBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    const topN = 10;
    const rows = (DB_KW_RAW || []).slice(0, topN);

    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="3" style="text-align:center;color:#888">데이터 없음</td></tr>`;
      return;
    }

    for (const r of rows) {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${r.rank ?? ''}</td>
        <td>${r.keyword ?? '-'}</td>
        <td class="right">${(r.count ?? 0).toLocaleString()}</td>
      `;
      tbody.appendChild(tr);
    }
  }

  // 이벤트 바인딩
  document.getElementById('DB_kwDays')?.addEventListener('change', DB_loadKeywordRanking);
  document.querySelectorAll('input[name="DB_kwMode"]')
      .forEach(r => r.addEventListener('change', e => DB_setKwMode(e.target.value)));

  // 초기 실행
  (async function init(){
    await DB_initCategoryTrends(); // 핫토픽(BFF)
    DB_buildKwTabs();              // 탭
    await DB_loadKeywordRanking(); // 랭킹(BFF)
    DB_setKwMode('category');      // 기본 모드
  })();
})();
