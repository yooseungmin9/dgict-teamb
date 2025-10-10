// app.js — 통합본 (app.js + app2.js)
// [입문자 주석] 이 파일은 "공통 초기화 + 감성차트"까지만 담당합니다.
// 트렌드 차트 로직은 trends.js가 'page:show' 이벤트를 받아 그립니다.

// -------------------------------------------------------------
// 0) 전역 데이터/상태
// -------------------------------------------------------------
window.appData = window.appData || {}; // 서버에서 주입하지 않아도 에러 안 나도록 안전 가드
let sentimentChart = null;             // 감성 차트 핸들

// -------------------------------------------------------------
// 1) 부트스트랩
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', function () {
  initializeApp();          // 네비/뉴스/추천/챗봇/모달 등 공통 초기화
  setActiveNavByLocation(); // URL과 내비 active 동기화  :contentReference[oaicite:5]{index=5}
  createSentimentChart();   // 감성차트만 여기서 렌더 (트렌드는 trands.js 위임)

  // [테스트] 초기 로딩 후 대시보드/감성/트렌드 탭 전환 테스트:
  // 1) 상단 네비에서 "감성" 클릭 → 원형차트 보이면 OK
  // 2) "트렌드" 클릭 → trends.js가 page:show 이벤트를 받아 라인차트 생성되면 OK
});

// -------------------------------------------------------------
// 2) 페이지 전환 (SPA & 정적 경로 겸용)
// -------------------------------------------------------------
function showPage(pageId) {
  // 모든 페이지 숨김
  document.querySelectorAll('.page').forEach(p => {
    p.classList.remove('active');
    p.style.display = 'none';
  });

  // 대상 표시
  const target = document.getElementById(pageId);
  if (!target) {
    console.error('Page not found:', pageId);
    return;
  }
  target.classList.add('active');
  target.style.display = 'block';

  // 감성 페이지 → 감성 차트(로컬) 렌더
  if (pageId === 'sentiment' || pageId === 'sentiment.html') {
    setTimeout(() => createSentimentChart(), 100);
  }

  // 트렌드 페이지 → 신호만 보냄(실제 그리기는 trends.js가 담당)  :contentReference[oaicite:6]{index=6}
  if (pageId === 'trends' || pageId === 'trends.html') {
    const evt = new CustomEvent('page:show', { detail: { id: 'trends' } });
    window.dispatchEvent(evt);
  }
}

// -------------------------------------------------------------
// 3) 내비게이션 (URL 기반 활성화 + 해시(SPA) 지원)  :contentReference[oaicite:7]{index=7}
/** 경로 정규화 */
function normalizePath(path) {
  try {
    const p = path.replace(window.location.origin, '').replace(/\/+$/, '');
    const base = p === '' ? '/' : p;
    const alias = { '/': '/', '/index': '/', '/dashboard': '/' };
    return alias[base] || base;
  } catch (_) {
    return '/';
  }
}
/** 요소에서 이동 URL 추출 (a[href] > data-url > #page) */
function getNavUrl(el) {
  const href = el.getAttribute('href');
  if (href && href.trim() !== '') return href;
  const dataUrl = el.getAttribute('data-url');
  if (dataUrl && dataUrl.trim() !== '') return dataUrl;
  const dataPage = el.getAttribute('data-page');
  if (dataPage && dataPage.trim() !== '') return `#${dataPage}`;
  return null;
}
/** 현재 위치와 내비 버튼 활성화 동기화 */
function setActiveNavByLocation() {
  const current = normalizePath(window.location.pathname);
  document.querySelectorAll('.nav-btn').forEach((btn) => {
    const url = getNavUrl(btn);
    if (!url || url.startsWith('#')) return btn.classList.remove('active');
    const target = normalizePath(url);
    if (target === current) btn.classList.add('active');
    else btn.classList.remove('active');
  });
}
/** 내비/카드 바인딩 */
function setupNavigation() {
  const navBtns = document.querySelectorAll('.nav-btn');
  navBtns.forEach((btn) => {
    // 키보드 접근성
    btn.setAttribute('tabindex', '0');
    btn.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); btn.click(); }
    });

    // 클릭 처리
    btn.addEventListener('click', (e) => {
      const url = getNavUrl(btn);
      if (!url) return;

      // SPA(#pageId): showPage로 전환
      if (url.startsWith('#')) {
        e.preventDefault();
        const pageId = url.slice(1);
        if (pageId) {
          showPage(pageId);
          updateActiveNav(btn);
        }
        return;
      }
      // 정적 라우팅: 버튼이면 JS로 이동, <a>는 기본 동작
      if (btn.tagName !== 'A') {
        e.preventDefault();
        window.location.href = url;
      }
    });
  });

  // 대시보드 카드 (data-url 사용)
  document.querySelectorAll('.dashboard-card').forEach((card) => {
    const url = card.getAttribute('data-url');
    if (!url) return;
    card.style.cursor = 'pointer';
    card.addEventListener('click', () => (window.location.href = url));
    card.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); window.location.href = url; }
    });
  });

  // 초기 대시보드 active
  const dashboardNav = document.querySelector('[data-page="dashboard"]');
  if (dashboardNav) dashboardNav.classList.add('active');
}
function updateActiveNav(activeBtn) {
  const navBtns = document.querySelectorAll('.nav-btn');
  navBtns.forEach(btn => btn.classList.remove('active'));
  if (activeBtn) activeBtn.classList.add('active');
}

// -------------------------------------------------------------
// 4) 뉴스 리스트 렌더 (감성칩/별점/escape 포함)  :contentReference[oaicite:8]{index=8}
function renderNewsData() {
  const newsList = document.getElementById('news-list');
  if (!newsList || !Array.isArray(appData.news_summary)) return;

  newsList.innerHTML = '';
  appData.news_summary.forEach((news, index) => {
    const label = toSentimentLabel(news);          // 'pos' | 'neg' | 'neu'
    const arrow = sentimentArrow(label);           // ▲ / ▼ / —
    const score = sentimentScoreText(news);        // " 0.42" (있을 때만)
    const stars = '★'.repeat(news.importance || 0) + '☆'.repeat(5 - (news.importance || 0));

    const item = document.createElement('div');
    item.className = 'news-item';
    item.setAttribute('data-news-id', index);
    item.innerHTML = `
      <div class="news-header">
        <h4 class="news-title">
          <span class="title-text">${escapeHtml(news.title)}</span>
          <span class="sentiment-chip ${label}" title="감성: ${label}${score}">${arrow}</span>
        </h4>
        <div class="news-meta">
          <span class="news-category">${escapeHtml(news.category)}</span>
          <span class="news-time">${escapeHtml(news.time)}</span>
        </div>
      </div>
      <p class="news-summary">${escapeHtml(news.summary)}</p>
      <div class="news-importance">
        <span>중요도:</span>
        <span class="stars" aria-label="중요도 ${news.importance || 0}/5">${stars}</span>
      </div>
    `;
    item.addEventListener('click', () => openNewsModal(news));
    newsList.appendChild(item);
  });

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  }
}
function toSentimentLabel(news) {
  if (typeof news.sentiment === 'string') {
    const s = news.sentiment.toLowerCase();
    if (s.startsWith('pos')) return 'pos';
    if (s.startsWith('neg')) return 'neg';
    return 'neu';
  }
  if (typeof news.score === 'number') {
    if (news.score >= 0.15) return 'pos';
    if (news.score <= -0.15) return 'neg';
    return 'neu';
  }
  const t = (news.title || '') + ' ' + (news.summary || '');
  const posK = /(호조|호재|증가|상승|회복|상회|개선|선전|확대|급등|강세)/;
  const negK = /(부진|악화|감소|하락|둔화|우려|급락|약세|경고|참사|적자)/;
  if (posK.test(t) && !negK.test(t)) return 'pos';
  if (negK.test(t) && !posK.test(t)) return 'neg';
  return 'neu';
}
function sentimentArrow(label){ return label === 'pos' ? '▲' : label === 'neg' ? '▼' : '—'; }
function sentimentScoreText(news){ return typeof news.score === 'number' ? ` ${news.score.toFixed(2)}` : ''; }

// -------------------------------------------------------------
// 5) 글로벌 데이터/추천/챗봇/모달  :contentReference[oaicite:9]{index=9}
function renderGlobalData() {
  const ticker = document.getElementById('headlines-ticker');
  if (ticker && Array.isArray(appData.global_headlines)) {
    ticker.innerHTML = appData.global_headlines.map(h => `<span class="headline-item">${h}</span>`).join('');
  }
  const tableBody = document.querySelector('#indicators-table tbody');
  if (tableBody && Array.isArray(appData.economic_indicators)) {
    tableBody.innerHTML = '';
    appData.economic_indicators.forEach(ind => {
      const row = document.createElement('tr');
      row.innerHTML = `<td>${ind.country}</td><td>${ind.gdp}</td><td>${ind.inflation}</td><td>${ind.unemployment}</td>`;
      tableBody.appendChild(row);
    });
  }
}
function renderRecommendations() {
  const booksGrid = document.getElementById('books-grid');
  if (booksGrid && Array.isArray(appData.book_recommendations)) {
    booksGrid.innerHTML = '';
    appData.book_recommendations.forEach(book => {
      const ratingStars = '★'.repeat(Math.floor(book.rating)) +
                          (book.rating % 1 >= 0.5 ? '☆' : '') +
                          '☆'.repeat(5 - Math.ceil(book.rating));
      const card = document.createElement('div');
      card.className = 'book-card';
      card.innerHTML = `
        <div class="book-title">${book.title}</div>
        <div class="book-author">저자: ${book.author}</div>
        <div class="book-description">${book.description}</div>
        <div class="book-rating"><span class="rating-stars">${ratingStars}</span><span>${book.rating}</span></div>
      `;
      booksGrid.appendChild(card);
    });
  }
  const videosGrid = document.getElementById('videos-grid');
  if (videosGrid && Array.isArray(appData.video_recommendations)) {
    videosGrid.innerHTML = '';
    appData.video_recommendations.forEach(video => {
      const card = document.createElement('div');
      card.className = 'video-card';
      card.innerHTML = `
        <div class="video-thumbnail">📺</div>
        <div class="video-info">
          <div class="video-title">${video.title}</div>
          <div class="video-meta"><span>${video.channel}</span><span>${video.duration}</span></div>
          <div class="video-meta"><span>조회수: ${video.views}</span></div>
        </div>`;
      videosGrid.appendChild(card);
    });
  }
}
function setupChatbot() {
  const chatInput = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');
  const faqItems = document.querySelectorAll('.faq-item');

  if (sendBtn) sendBtn.addEventListener('click', sendMessage);
  if (chatInput) chatInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendMessage(); });
  faqItems.forEach(item => {
    item.addEventListener('click', () => {
      const question = item.getAttribute('data-question');
      simulateUserMessage(question);
      setTimeout(() => sendBotResponse(question), 500);
    });
  });

  function sendMessage() {
    const msg = (chatInput?.value || '').trim();
    if (!msg) return;
    addMessage(msg, 'user');
    chatInput.value = '';
    setTimeout(() => addMessage(generateBotResponse(msg), 'bot'), 600);
  }
  function simulateUserMessage(message) { addMessage(message, 'user'); }
  function sendBotResponse(q) { addMessage(generateBotResponse(q), 'bot'); }
  function addMessage(content, sender) {
    const wrap = document.getElementById('chat-messages');
    if (!wrap) return;
    const div = document.createElement('div');
    div.className = `message ${sender}-message`;
    div.innerHTML = `<div class="message-content">${content}</div>`;
    wrap.appendChild(div);
    wrap.scrollTop = wrap.scrollHeight;
  }
  function generateBotResponse(message) {
    const m = message.toLowerCase();
    if (m.includes('금리')) return '현재 한국의 기준금리는 3.5%로 동결되었습니다.';
    if (m.includes('주식') || m.includes('증시')) return '반도체 회복 영향으로 긍정 흐름입니다.';
    if (m.includes('부동산')) return '최근 거래량이 전월 대비 증가했습니다.';
    if (m.includes('환율')) return '원달러 환율은 1,350원대 후반에서 거래 중입니다.';
    return '죄송합니다. 다른 질문도 시도해보세요.';
  }
}
function setupModal() {
  const modal = document.getElementById('news-modal');
  const closeBtn = document.querySelector('.modal-close');
  if (closeBtn) closeBtn.addEventListener('click', closeNewsModal);
  if (modal) {
    modal.addEventListener('click', (e) => { if (e.target === modal) closeNewsModal(); });
  }
}
function openNewsModal(news) {
  const modal = document.getElementById('news-modal');
  const modalTitle = document.getElementById('modal-title');
  const modalCategory = document.getElementById('modal-category');
  const modalTime = document.getElementById('modal-time');
  const modalSummary = document.getElementById('modal-summary');
  const modalStars = document.getElementById('modal-stars');
  if (modal && modalTitle && modalCategory && modalTime && modalSummary && modalStars) {
    modalTitle.textContent = news.title;
    modalCategory.textContent = news.category;
    modalTime.textContent = news.time;
    modalSummary.textContent = news.summary;
    modalStars.textContent = '★'.repeat(news.importance || 0) + '☆'.repeat(5 - (news.importance || 0));
    modal.classList.remove('hidden');
  }
}
function closeNewsModal() {
  const modal = document.getElementById('news-modal');
  if (modal) modal.classList.add('hidden');
}

// -------------------------------------------------------------
// 6) 감성 차트 (도넛)  :contentReference[oaicite:10]{index=10} :contentReference[oaicite:11]{index=11}
function createSentimentChart() {
  const ctx = document.getElementById('sentimentChart');
  if (!ctx) return;
  if (sentimentChart) sentimentChart.destroy();

  const s = appData.sentiment_data || { positive:0, neutral:0, negative:0 };
  sentimentChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['긍정', '중립', '부정'],
      datasets: [{
        data: [s.positive, s.neutral, s.negative],
        backgroundColor: ['#1FB8CD', '#FFC185', '#B4413C'],
        borderWidth: 2,
        borderColor: '#ffffff'
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom', labels: { padding: 20, font: { size: 12 } } } }
    }
  });
}

// -------------------------------------------------------------
// 8) 앱 초기화 엔트리
// -------------------------------------------------------------
function initializeApp() {
  setupNavigation();
  renderNewsData();
  renderGlobalData();
  renderRecommendations();
  setupChatbot();
  setupModal();
}