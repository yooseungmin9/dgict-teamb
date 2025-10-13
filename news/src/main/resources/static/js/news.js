// /static/js/news.js
(function () {
  if (window.__newsInitOnce) return;
  window.__newsInitOnce = true;

  const pageEl   = document.getElementById("news-page");
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

  // -----------------------
  // B. 뉴스 카드 UX (+ 더 보기 자동 토글)
  // -----------------------
  const list = document.getElementById('news-list');

  // 핵심: 요약이 실제로 잘렸는지 검사해서 '더 보기' 버튼을 보이거나 숨김
  function refreshMoreToggles(root = document) {
    const wraps = root.querySelectorAll('.summary-wrap');
    wraps.forEach(wrap => {
      const p   = wrap.querySelector('.news-summary');
      const btn = wrap.querySelector('.more-toggle');
      if (!p || !btn) return;

      const card = wrap.closest('.news-card');
      const expanded = card?.getAttribute('data-expanded') === 'true';

      // 펼친 상태면 '접기' 버튼은 항상 노출
      if (expanded) {
        btn.style.display = 'inline';
        btn.textContent = '접기';
        return;
      }

      // (접힘 상태) line-clamp 적용 상태에서 잘림 여부 체크
      const isOverflow = p.scrollHeight > p.clientHeight + 1;
      btn.style.display = isOverflow ? 'inline' : 'none';
      btn.textContent = '더 보기';
    });
  }

  if (list) {
    // 더 보기/접기 클릭
    list.addEventListener('click', (e)=>{
      const btn = e.target.closest('.more-toggle'); if(!btn) return;
      e.preventDefault(); e.stopPropagation();
      const card = btn.closest('.news-card');
      const expanded = card.getAttribute('data-expanded') === 'true';
      card.setAttribute('data-expanded', expanded ? 'false' : 'true');
      btn.textContent = expanded ? '더 보기' : '접기';

      // 상태 변경 이후 가시성 재계산 (접기 → 짧으면 버튼 사라지도록)
      refreshMoreToggles(card);
    }, {passive:false});

    // 카드 클릭 시 모달
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
      list.addEventListener('click', (e)=>{
        const card=e.target.closest('.news-card');
        if(!card || e.target.closest('.more-toggle')) return;
        const id=card.getAttribute('data-id'); if(id) openModalById(id);
      });
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

    // 새로 그린 카드들 대상 ‘더 보기’ 가시성 재계산
    refreshMoreToggles($list);
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

  // -----------------------
  // D. 초기화 & 리사이즈 대응
  // -----------------------
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ()=>{
      initBriefingOnce();
      refreshMoreToggles(document);
    }, { once:true });
  } else {
    initBriefingOnce();
    refreshMoreToggles(document);
  }

  // 반응형에서 줄 수 변동 시 재계산
  let __moResizeTimer;
  window.addEventListener('resize', ()=>{
    clearTimeout(__moResizeTimer);
    __moResizeTimer = setTimeout(()=>refreshMoreToggles(document), 150);
  });

  // (선택) 페이지네이션 버튼에 goPage 연결하고 싶으면 아래 유틸 활용
  // window.goNewsPage = (p, s)=>goPage(p, s);

})();
