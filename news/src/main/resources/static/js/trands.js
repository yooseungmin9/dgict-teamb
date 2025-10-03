(function DB_trendsWidgets(){
  // ---- 공통 fetch 유틸 ----
  const fetchJSON = async (primaryUrl, fallbackUrl, params = {}) => {
    const add = (u) => {
      const q = new URLSearchParams(params).toString();
      return q ? (u + (u.includes('?') ? '&' : '?') + q) : u;
    };
    try {
      const r = await fetch(add(primaryUrl));
      if (!r.ok) throw new Error(r.statusText);
      return await r.json();
    } catch (e) {
      if (!fallbackUrl) throw e;
      const r2 = await fetch(add(fallbackUrl));
      if (!r2.ok) throw new Error(r2.statusText);
      return await r2.json();
    }
  };

  // ===== (A) 데이터랩 라인차트 =====
  let DB_trendChart;
  async function DB_initCategoryTrends(){
    const elDays = document.getElementById('DB_trendDays');
    if (!elDays) return;
    const days = elDays.value;

    const data = await fetchJSON('/api/trends/category-trends', '/api/category-trends', { days });
    const ctx = document.getElementById('DB_categoryTrendChart');
    if (!ctx) return;

    const colorMap = { "증권":"#1f77b4","금융":"#ff7f0e","부동산":"#2ca02c","산업":"#d62728","글로벌경제":"#9467bd","기타":"#8c564b","일반":"#8c564b" };
    const labels = data.dates;
    const datasets = Object.keys(data.categories).map(cat => {
      const key = (cat === '일반' ? '기타' : cat);
      const color = colorMap[key] || 'gray';
      return { label:key, data:data.categories[cat], borderColor:color, backgroundColor:color+'55', fill:false, tension:0.3, borderWidth:2, pointRadius:2 };
    });

    if (DB_trendChart) DB_trendChart.destroy();
    DB_trendChart = new Chart(ctx, {
      type:'line',
      data:{ labels, datasets },
      options:{
        responsive:true, maintainAspectRatio:false,
        plugins:{ legend:{ position:'top' } },
        interaction:{ mode:'nearest', axis:'x', intersect:false },
        scales:{ x:{ ticks:{ autoSkip:true, maxTicksLimit:8 } }, y:{ beginAtZero:true, title:{ display:true, text:'언급량(건)'} } }
      }
    });
  }
  document.getElementById('DB_trendDays')?.addEventListener('change', DB_initCategoryTrends);

  // ===== (B) 키워드 랭킹 테이블 =====
  const DB_groupBy = (arr, key) => arr.reduce((m, x) => ((m[x[key]] ??= []).push(x), m), {});
  let DB_KW_RAW = [], DB_KW_BY_CAT = {}, DB_KW_CATEGORIES = [], DB_KW_MODE = 'category', DB_KW_CURRENT_CAT = '';

  async function DB_loadKeywordRanking(){
    const days = document.getElementById('DB_kwDays')?.value || '30';
    try{
      const res = await fetch('/api/trends/keyword-ranking?days='+encodeURIComponent(days));
      DB_KW_RAW = await res.json();
    }catch{
      const res = await fetch('/api/trends/keyword-ranking');
      DB_KW_RAW = await res.json();
    }
    DB_KW_BY_CAT = DB_groupBy(DB_KW_RAW, 'category');
    DB_KW_CATEGORIES = Object.keys(DB_KW_BY_CAT).sort();
    if (!DB_KW_CURRENT_CAT) DB_KW_CURRENT_CAT = DB_KW_CATEGORIES[0] || '';
    DB_buildKwTabs();
    DB_buildKwSelect();
    DB_renderKwTable();
  }

  function DB_buildKwTabs(){
    const wrap = document.getElementById('DB_kwTabs');
    if (!wrap) return;
    wrap.style.display = (DB_KW_MODE === 'category') ? 'flex' : 'none';
    wrap.innerHTML = '';
    DB_KW_CATEGORIES.forEach(cat => {
      const btn = document.createElement('button');
      btn.textContent = cat;
      btn.className = 'chip' + (cat === DB_KW_CURRENT_CAT ? ' active' : '');
      btn.addEventListener('click', () => {
        DB_KW_CURRENT_CAT = cat;
        const sel = document.getElementById('DB_kwCategorySelect');
        if (sel) sel.value = cat;
        DB_buildKwTabs();
        DB_renderKwTable();
      });
      wrap.appendChild(btn);
    });
  }

  function DB_buildKwSelect(){
    const sel = document.getElementById('DB_kwCategorySelect');
    if (!sel) return;
    sel.style.display = (DB_KW_MODE === 'category') ? 'inline-block' : 'none';
    sel.innerHTML = '';
    DB_KW_CATEGORIES.forEach(cat => {
      const opt = document.createElement('option');
      opt.value = cat; opt.textContent = cat;
      sel.appendChild(opt);
    });
    sel.value = DB_KW_CURRENT_CAT || DB_KW_CATEGORIES[0] || '';
  }

  function DB_toggleCategoryColumn(show){
    const table = document.getElementById('DB_kwTable');
    if (!table) return;
    if (show) table.classList.remove('hide-category');
    else table.classList.add('hide-category');
  }

  function DB_setKwMode(mode){
    DB_KW_MODE = mode;
    const showCategoryCol = (mode === 'global'); // 통합=표시
    DB_toggleCategoryColumn(showCategoryCol);
    const sel = document.getElementById('DB_kwCategorySelect');
    const tabs = document.getElementById('DB_kwTabs');
    if (sel) sel.style.display = (mode === 'category') ? 'inline-block' : 'none';
    if (tabs) tabs.style.display = (mode === 'category') ? 'flex' : 'none';
    if (!DB_KW_CURRENT_CAT && DB_KW_CATEGORIES.length) DB_KW_CURRENT_CAT = DB_KW_CATEGORIES[0];
    DB_buildKwTabs(); DB_buildKwSelect(); DB_renderKwTable();
  }

  function DB_renderKwTable(){
    const tbody = document.getElementById('DB_keywordRankingBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    const topN = parseInt(document.getElementById('DB_kwTopN')?.value || '10', 10);
    let rows = [];
    if (DB_KW_MODE === 'category'){
      const src = (DB_KW_BY_CAT[DB_KW_CURRENT_CAT] || []).slice(0, topN);
      rows = src.map((r, idx) => ({ rank:idx+1, keyword:r.keyword, category:r.category||'', count:r.count||0 }));
    }else{
      const byWord = new Map();
      for (const r of DB_KW_RAW){ byWord.set(r.keyword, (byWord.get(r.keyword)||0)+(r.count||0)); }
      rows = [...byWord.entries()].map(([keyword,count])=>({keyword,count}))
        .sort((a,b)=>b.count-a.count).slice(0, topN)
        .map((r,idx)=>({rank:idx+1, keyword:r.keyword, category:'-', count:r.count}));
    }
    for(const r of rows){
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${r.rank}</td><td>${r.keyword}</td><td class="col-category">${r.category}</td><td class="right">${(r.count??0).toLocaleString()}</td>`;
      tbody.appendChild(tr);
    }
  }

  // 이벤트 바인딩
  document.getElementById('DB_kwTopN')?.addEventListener('change', DB_renderKwTable);
  document.getElementById('DB_kwDays')?.addEventListener('change', DB_loadKeywordRanking);
  document.getElementById('DB_kwCategorySelect')?.addEventListener('change', (e)=>{ DB_KW_CURRENT_CAT=e.target.value; DB_buildKwTabs(); DB_renderKwTable(); });
  document.querySelectorAll('input[name="DB_kwMode"]').forEach(r=> r.addEventListener('change',(e)=> DB_setKwMode(e.target.value)));

  // 부트스트랩
  (async function(){
    await DB_initCategoryTrends();
    await DB_loadKeywordRanking();
    DB_setKwMode('category');
  })();
})();