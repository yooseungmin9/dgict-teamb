// /static/js/news.js
(function () {
  if (window.__newsInitOnce) return;
  window.__newsInitOnce = true;

  const pageEl  = document.getElementById("news-page");
  const API_BASE = (pageEl && pageEl.dataset.apiBase) ? pageEl.dataset.apiBase : "";
  const BRIEFING_KEY = "briefing:yesterday:v1";

  // -----------------------
  // A. 전일 브리핑 (탭당 1회)
  // -----------------------
  function mapCategory(name){ if(!name) return '일반'; if(name==='증권') return '금융'; return name; }
  function normalizeCategories(arr){
    const ORDER = ['금융','부동산','산업','글로벌경제','일반'];
    const byCat = new Map();
    (arr||[]).forEach(src=>{
      const cat = mapCategory(src.category || '일반');
      if(!byCat.has(cat)) byCat.set(cat, { category:cat, summary:'', highlights:[] });
      const dst = byCat.get(cat);
      const s = (src.summary||'').trim();
      if(s && !dst.summary.includes(s)) dst.summary = (dst.summary ? dst.summary+' ' : '') + s;
      const hs = Array.isArray(src.highlights) ? src.highlights : [];
      const set = new Set(dst.highlights.concat(hs));
      dst.highlights = Array.from(set).slice(0,12);
    });
    const out=[];
    ORDER.forEach(cat=>{
      if(byCat.has(cat)) out.push(byCat.get(cat));
      else out.push({ category:cat, summary:'해당 카테고리의 전일 기사가 없습니다.', highlights:[] });
    });
    return out;
  }
  function makeBriefingItem(cat){
    const wrap = document.createElement('div'); wrap.className = `briefing-item C${cat.category}`;
    const bar = document.createElement('div');  bar.className='briefing-bar';
    const body = document.createElement('div'); body.className='briefing-body';
    const h = document.createElement('h5'); h.className='briefing-title';
    const chip = document.createElement('span'); chip.className='cat-chip';
    const dot = document.createElement('span'); dot.className='dot';
    const lbl = document.createElement('span'); lbl.textContent = cat.category;
    chip.append(dot,lbl); h.append(chip);
    const p = document.createElement('p'); p.className='briefing-summary'; p.textContent = cat.summary || '요약 없음';
    const tags = document.createElement('div'); tags.className='briefing-tags';
    (cat.highlights || []).forEach(t=>{ const s=document.createElement('span'); s.className='tag'; s.textContent=t; tags.appendChild(s); });
    body.append(h,p,tags); wrap.append(bar,body); return wrap;
  }
  function renderBriefing(payload){
    const listEl = document.getElementById('briefing-list');
    const dateEl = document.querySelector('.briefing-date');
    if (!listEl || !dateEl) return;
    const cats = normalizeCategories(payload?.categories || []);
    listEl.innerHTML = '';
    dateEl.textContent = (payload?.date ? `(${payload.date}) ` : '') + '전일 카테고리별 요약';
    cats.forEach(c => listEl.appendChild(makeBriefingItem(c)));
  }
  async function initBriefingOnce(){
    const dateEl = document.querySelector('.briefing-date');
    const listEl = document.getElementById('briefing-list');
    if (!dateEl || !listEl) return;

    // 1) 캐시 우선
    try {
      const cached = sessionStorage.getItem(BRIEFING_KEY);
      if (cached) { renderBriefing(JSON.parse(cached)); return; }
    } catch {}

    // 2) 캐시 없으면 1회 네트워크 (봉인 스크립트가 이미 탭당 1회로 제한)
    try {
      dateEl.textContent = '불러오는 중…';
      listEl.innerHTML = '';
      const res = await fetch(`${API_BASE}/briefing/yesterday`, { headers:{'Accept':'application/json'} });
      if (!res.ok) { dateEl.textContent = '전일 기사 요약이 없습니다.'; return; }
      const raw = await res.json();
      try { sessionStorage.setItem(BRIEFING_KEY, JSON.stringify(raw)); } catch {}
      renderBriefing(raw);
    } catch (e) {
      console.warn(e);
      dateEl.textContent = '요약 데이터를 불러오지 못했습니다.';
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initBriefingOnce, { once:true });
  } else { initBriefingOnce(); }

  // -----------------------
  // B. 뉴스 카드 UX
  // -----------------------
  const list = document.getElementById('news-list');
  if (list) {
    list.addEventListener('click', (e)=>{
      const btn = e.target.closest('.more-toggle'); if(!btn) return;
      e.preventDefault(); e.stopPropagation();
      const card = btn.closest('.news-card');
      const expanded = card.getAttribute('data-expanded') === 'true';
      card.setAttribute('data-expanded', expanded ? 'false' : 'true');
      btn.textContent = expanded ? '더 보기' : '접기';
    }, {passive:false});

    // 모달
    const modal = document.getElementById('news-modal');
    if (modal) {
      const closeBtn = modal.querySelector('.modal-close');
      const backdrop = modal.querySelector('.modal-backdrop');
      const $mTitle   = document.getElementById('modal-title');
      const $mUpdated = document.getElementById('modal-updated');
      const $mImg     = document.getElementById('modal-image');
      const $mContent = document.getElementById('modal-content');
      const $mLink    = document.getElementById('modal-link');
      const $mPress   = document.getElementById('modal-press');

      const lockScroll = (lock)=>{ document.documentElement.style.overflow=document.body.style.overflow=lock?'hidden':''; };
      const showModal = ()=>{ modal.classList.add('open'); modal.setAttribute('aria-hidden','false'); lockScroll(true); };
      const hideModal = ()=>{ modal.classList.remove('open'); modal.setAttribute('aria-hidden','true'); lockScroll(false); };
      closeBtn?.addEventListener('click', hideModal);
      backdrop?.addEventListener('click', hideModal);
      document.addEventListener('keydown', (e)=>{ if(e.key==='Escape') hideModal(); });

      async function openModalById(id){
        try{
          const res = await fetch(`/pages/news/${encodeURIComponent(id)}`);
          if(!res.ok) throw new Error('HTTP '+res.status);
          const data = await res.json();
          $mTitle.textContent = data.title || '(제목 없음)';
          const updated = data.updated_at || data.publishedAt || data.published_at;
          $mUpdated.textContent = updated ? String(updated).substring(0,10) : '';
          if (data.image) {
            $mImg.src = data.image; $mImg.alt = data.title || 'article image';
            $mImg.style.display = 'block'; $mImg.onerror = ()=>{ $mImg.style.display='none'; };
          } else { $mImg.removeAttribute('src'); $mImg.style.display = 'none'; }
          $mContent.textContent = data.content || data.summary || '';
          if (data.url) { $mLink.href=data.url; $mLink.style.display='inline-block'; $mLink.rel='noopener noreferrer'; $mLink.target='_blank'; }
          else { $mLink.removeAttribute('href'); $mLink.style.display='none'; }
          $mPress.textContent = data.press ? ('출처: '+data.press) : '';
          showModal();
        }catch(e){ console.error(e); alert('상세를 불러오지 못했습니다.'); }
      }
      list.addEventListener('click', (e)=>{ const card=e.target.closest('.news-card'); if(!card || e.target.closest('.more-toggle')) return; const id=card.getAttribute('data-id'); if(id) openModalById(id); });
    }
  }

  // -----------------------
  // C. SPA 페이지네이션
  // -----------------------
  async function fetchNews(page, size) {
    const url = `/pages/news/json?page=${encodeURIComponent(page)}&size=${encodeURIComponent(size)}`;
    const res = await fetch(url, { headers: { "Accept": "application/json" } });
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.json(); // [{...}] or {items:[...]}
  }

  function renderNews(items) {
    const arr = Array.isArray(items) ? items : (items.items || []);
    const $list = document.getElementById("news-list");
    if (!$list) return;
    $list.innerHTML = arr.map(it => `
      <div class="news-card" data-id="${it.id || it._id || ""}" tabindex="0">
        <img class="news-thumb" src="${it.image || '/img/placeholder-120x80.png'}" alt="${(it.title||'').replace(/"/g,'&quot;')}" />
        <div class="news-body">
          <span class="news-title">${it.title || ''}</span>
          <div class="news-meta">${(it.publishedAt || it.published_at) ? String(it.publishedAt || it.published_at).substring(0,16) : ''}</div>
          <div class="summary-wrap">
            <p class="news-summary">${it.summary || ''}</p>
            <button type="button" class="more-toggle">더 보기</button>
          </div>
        </div>
      </div>
    `).join("");
  }

  async function goPage(page, size) {
    try {
      const data = await fetchNews(page, size);
      renderNews(data);
    } catch (e) {
      console.warn("[paging] SPA 실패 → 기본 이동", e);
      window.location.href = `/pages/news?page=${encodeURIComponent(page)}&size=${encodeURIComponent(size)}`;
    }
  }

  let __pagingBusy = false;
  window.addEventListener("click", (e) => {
    const a = e.target.closest("a.page-btn");
    if (!a) return;

    const u = new URL(a.href, location.origin);
    if (u.origin !== location.origin) return; // 외부 링크는 SPA 제외

    e.preventDefault();
    e.stopPropagation();
    if (e.stopImmediatePropagation) e.stopImmediatePropagation();
    if (__pagingBusy) return;
    __pagingBusy = true;

    try {
      const page = u.searchParams.get("page") || "1";
      const size = u.searchParams.get("size") || "10";
      history.pushState({ page, size }, "", `${location.pathname}?page=${page}&size=${size}`);
      Promise.resolve()
        .then(() => goPage(page, size))
        .finally(() => { __pagingBusy = false; });
    } catch (err) {
      __pagingBusy = false;
      console.error("[paging] error", err);
      window.location.href = a.href; // 폴백
    }
  }, { capture: true, passive: false });

  window.addEventListener("popstate", (e) => {
    const page = (e.state && e.state.page) || new URLSearchParams(location.search).get("page") || "1";
    const size = (e.state && e.state.size) || new URLSearchParams(location.search).get("size") || "10";
    goPage(page, size);
  });

})();