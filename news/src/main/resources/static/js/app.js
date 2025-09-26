// Application data

const appData = {
  news_summary: [
    {
      title: "한국은행 기준금리 동결, 3.5% 유지 결정",
      summary: "한국은행이 기준금리를 3.5%로 동결했다. 물가 안정과 경제성장 사이의 균형을 고려한 결정으로 풀이된다.",
      importance: 5,
      category: "금융정책",
      time: "2시간 전"
    },
    {
      title: "삼성전자 3분기 실적 시장 기대치 상회",
      summary: "삼성전자가 발표한 3분기 실적이 시장 예상을 웃돌았다. 메모리 반도체 가격 회복세가 주효했다.",
      importance: 4,
      category: "기업실적",
      time: "4시간 전"
    },
    {
      title: "부동산 거래량 전월 대비 15% 증가",
      summary: "9월 부동산 거래량이 전월 대비 15% 증가했다. 정부의 부동산 정책 완화 기대감이 반영된 것으로 보인다.",
      importance: 3,
      category: "부동산",
      time: "6시간 전"
    },
    {
      title: "원달러 환율 1,350원대 후반 거래",
      summary: "원달러 환율이 1,350원대 후반에서 거래되고 있다. 미국의 금리 정책 불확실성이 주요 변수로 작용하고 있다.",
      importance: 4,
      category: "환율",
      time: "1시간 전"
    },
    {
      title: "소비자물가 상승률 3개월 연속 둔화",
      summary: "9월 소비자물가 상승률이 전년 동월 대비 3.7%로 3개월 연속 둔화세를 보였다.",
      importance: 4,
      category: "물가",
      time: "8시간 전"
    }
  ],
  sentiment_data: {
    positive: 35,
    neutral: 45,
    negative: 20
  },
  global_headlines: [
    "Fed 11월 금리 동결 가능성 높아져",
    "중국 3분기 GDP 성장률 4.9% 기록",
    "유럽중앙은행 인플레이션 타겟 근접",
    "일본 엔화 약세 지속, 개입 우려 확산",
    "원유가격 배럴당 85달러선 회복"
  ],
  economic_indicators: [
    {"country": "한국", "gdp": "1.4%", "inflation": "3.7%", "unemployment": "2.8%"},
    {"country": "미국", "gdp": "2.1%", "inflation": "3.2%", "unemployment": "3.8%"},
    {"country": "중국", "gdp": "4.9%", "inflation": "2.1%", "unemployment": "5.3%"},
    {"country": "일본", "gdp": "0.8%", "inflation": "2.8%", "unemployment": "2.6%"}
  ],
  book_recommendations: [
    {
      title: "경제학 콘서트",
      author: "팀 하포드",
      description: "일상 속 경제 원리를 쉽고 재미있게 설명한 베스트셀러",
      rating: 4.5
    },
    {
      title: "부의 대이동",
      author: "오건영",
      description: "글로벌 경제 흐름과 투자 전략을 분석한 화제작",
      rating: 4.3
    },
    {
      title: "돈의 속성",
      author: "김승호",
      description: "부자들의 돈에 대한 생각과 투자 철학을 담은 실용서",
      rating: 4.7
    }
  ],
  video_recommendations: [
    {
      title: "2024년 경제전망과 투자전략",
      channel: "한경TV",
      duration: "45:30",
      views: "125,000"
    },
    {
      title: "금리 인상이 부동산에 미치는 영향",
      channel: "부동산학개론",
      duration: "32:15",
      views: "89,000"
    },
    {
      title: "반도체 산업의 미래 전망",
      channel: "테크인사이드",
      duration: "28:45",
      views: "156,000"
    }
  ]
};

// Chat responses for FAQ and basic queries
const chatResponses = {
  "기준금리가 오르면 어떤 영향이 있나요?": "기준금리가 오르면 대출금리가 상승하여 개인과 기업의 자금조달 비용이 증가합니다. 이로 인해 소비와 투자가 위축되어 경제성장률이 둔화될 수 있습니다. 반면 예금금리도 상승하여 저축 유인이 커지고, 물가 상승 압력을 완화하는 효과가 있습니다.",
  "인플레이션이란 무엇인가요?": "인플레이션은 물가가 지속적으로 상승하는 현상을 말합니다. 화폐의 구매력이 감소하여 같은 돈으로 더 적은 양의 상품을 구매할 수 있게 됩니다. 적정 수준의 인플레이션(2-3%)은 경제성장에 도움이 되지만, 과도한 인플레이션은 경제에 부정적인 영향을 미칩니다.",
  "환율이 경제에 미치는 영향은?": "환율 상승(원화 약세)은 수출 증가와 수입 감소로 이어져 무역수지 개선에 도움이 되지만, 수입물가 상승으로 인한 인플레이션 압력이 커집니다. 반대로 환율 하락(원화 강세)은 수입물가 하락으로 물가 안정에 도움이 되지만 수출 경쟁력이 약화될 수 있습니다."
};

// Global variable to track charts
let sentimentChart = null;
let trendsChart = null;

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
  initializeApp();
  createSentimentChart();
  createTrendsChart();
});

function initializeApp() {
  setupNavigation();
  renderNewsData();
  renderGlobalData();
  renderRecommendations();
  setupChatbot();
  setupModal();

  // Set initial active nav for dashboard
  const dashboardNav = document.querySelector('[data-page="dashboard"]');
  if (dashboardNav) {
    dashboardNav.classList.add('active');
  }
}

// Navigation setup
function setupNavigation() {
  const navBtns = document.querySelectorAll('.nav-btn');
  const dashboardCards = document.querySelectorAll('.dashboard-card');

  // Navigation button event listeners
  navBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const targetPage = btn.getAttribute('data-page');
      console.log('Nav clicked:', targetPage); // Debug log
      showPage(targetPage);
      updateActiveNav(btn);
    });
  });

  // Dashboard card event listeners
  dashboardCards.forEach(card => {
    card.addEventListener('click', (e) => {
      e.preventDefault();
      const feature = card.getAttribute('data-feature');
      console.log('Card clicked:', feature); // Debug log
      showPage(feature);

      // Update corresponding nav button
      const correspondingNav = document.querySelector(`[data-page="${feature}"]`);
      updateActiveNav(correspondingNav);
    });
  });
}

function showPage(pageId) {
  console.log('Showing page:', pageId); // Debug log

  // Hide all pages
  const pages = document.querySelectorAll('.page');
  pages.forEach(page => {
    page.classList.remove('active');
    page.style.display = 'none';
  });

  // Show target page
  const targetPage = document.getElementById(pageId);
  if (targetPage) {
    targetPage.classList.add('active');
    targetPage.style.display = 'block';
    console.log('Page shown:', pageId); // Debug log

    // Initialize charts when sentiment or trends page is shown
    if (pageId === 'sentiment' || pageId === 'sentiment.html') {
      setTimeout(() => createSentimentChart(), 100);
    } else if (pageId === 'trends' || pageId === 'trends.html') {
      setTimeout(() => createTrendsChart(), 100);
    }
  } else {
    console.error('Page not found:', pageId); // Debug log
  }
}

// /static/js/app.js 변경: URL 기반 활성화 + 버튼 내비게이션 지원:contentReference[oaicite:2]{index=2}
// 1) 경로 정규화
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

// 2) 요소에서 이동 URL 추출 (a[href] 우선, 없으면 data-url, 없다면 SPA data-page)
function getNavUrl(el) {
  const href = el.getAttribute('href');
  if (href && href.trim() !== '') return href;
  const dataUrl = el.getAttribute('data-url');
  if (dataUrl && dataUrl.trim() !== '') return dataUrl;
  const dataPage = el.getAttribute('data-page'); // SPA 대비
  if (dataPage && dataPage.trim() !== '') return `#${dataPage}`;
  return null;
}

// 3) 현재 위치와 내비 버튼을 매칭하여 .active 토글
function setActiveNavByLocation() {
  const current = normalizePath(window.location.pathname);
  document.querySelectorAll('.nav-btn').forEach((btn) => {
    const url = getNavUrl(btn);
    // 해시(SPA)나 null은 비활성 처리
    if (!url || url.startsWith('#')) {
      btn.classList.remove('active');
      return;
    }
    const target = normalizePath(url);
    if (target === current) btn.classList.add('active');
    else btn.classList.remove('active');
  });
}

// 4) 클릭/키보드 내비게이션: 버튼은 location.href로 이동, a는 기본 동작 허용
function setupNavigation() {
  const navBtns = document.querySelectorAll('.nav-btn');
  navBtns.forEach((btn) => {
    // 버튼/앵커 공통: 키보드 접근성
    btn.setAttribute('tabindex', '0');
    btn.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        btn.click();
      }
    });

    // 클릭 처리
    btn.addEventListener('click', (e) => {
      const url = getNavUrl(btn);
      // SPA 모드(#pageId): 기존 showPage 로직 활용
      if (url && url.startsWith('#')) {
        e.preventDefault();
        const pageId = url.slice(1);
        if (pageId) {
          showPage(pageId);          // 기존 함수
          updateActiveNav(btn);      // 기존 함수
        }
        return;
      }
      // 정적 라우팅: 버튼이면 JS로 이동, 앵커면 브라우저 기본 동작
      if (btn.tagName !== 'A') {
        e.preventDefault();
        if (url) window.location.href = url;
      }
    });
  });

  // 대시보드 카드도 동일 정책 유지(이미 data-url 사용):contentReference[oaicite:3]{index=3}
  document.querySelectorAll('.dashboard-card').forEach((card) => {
    const url = card.getAttribute('data-url');
    if (!url) return;
    card.style.cursor = 'pointer';
    card.addEventListener('click', () => (window.location.href = url));
    card.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        window.location.href = url;
      }
    });
  });
}

// 5) 초기화 시 URL 기반 활성화 호출 추가
document.addEventListener('DOMContentLoaded', function () {
  initializeApp();           // 기존 로직 호출 유지:contentReference[oaicite:4]{index=4}
  setActiveNavByLocation();  // URL → .active 동기화
});

function updateActiveNav(activeBtn) {
  const navBtns = document.querySelectorAll('.nav-btn');
  navBtns.forEach(btn => btn.classList.remove('active'));
  if (activeBtn) {
    activeBtn.classList.add('active');
  }
}

// renderNewsData() — "제목 바로 오른쪽"에 칩이 붙도록 교체
function renderNewsData() {
  const newsList = document.getElementById('news-list');
  if (!newsList) return;

  newsList.innerHTML = '';

  appData.news_summary.forEach((news, index) => {
    const label = toSentimentLabel(news);     // 'pos' | 'neg' | 'neu'
    const arrow = sentimentArrow(label);      // ▲ / ▼ / —
    const score = sentimentScoreText(news);   // " 0.42" 등 (없으면 빈문자)

    const stars = '★'.repeat(news.importance) + '☆'.repeat(5 - news.importance);

    const item = document.createElement('div');
    item.className = 'news-item';
    item.setAttribute('data-news-id', index);

    item.innerHTML = `
      <div class="news-header">
        <h4 class="news-title">
          <span class="title-text">${escapeHtml(news.title)}</span>
          <!-- 🔽 제목 바로 오른쪽에 배치되는 칩 -->
          <span class="sentiment-chip ${label}" title="감성: ${label}${score}">
            ${arrow}
          </span>
        </h4>
        <div class="news-meta">
          <span class="news-category">${escapeHtml(news.category)}</span>
          <span class="news-time">${escapeHtml(news.time)}</span>
        </div>
      </div>
      <p class="news-summary">${escapeHtml(news.summary)}</p>
      <div class="news-importance">
        <span>중요도:</span>
        <span class="stars" aria-label="중요도 ${news.importance}/5">${stars}</span>
      </div>
    `;

    item.addEventListener('click', () => openNewsModal(news));
    newsList.appendChild(item);
  });

  function escapeHtml(s){
    return String(s||'').replace(/[&<>"']/g, m => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[m]));
  }
}

function toSentimentLabel(news){
  // 1) 명시적 라벨 우선
  if (typeof news.sentiment === 'string') {
    const s = news.sentiment.toLowerCase();
    if (s.startsWith('pos')) return 'pos';
    if (s.startsWith('neg')) return 'neg';
    return 'neu';
  }
  // 2) 점수(-1~1) 기준
  if (typeof news.score === 'number') {
    if (news.score >= 0.15) return 'pos';
    if (news.score <= -0.15) return 'neg';
    return 'neu';
  }
  // 3) 아주 간단한 키워드 휴리스틱 (없으면 중립)
  const t = (news.title||'') + ' ' + (news.summary||'');
  const posK = /(호조|호재|증가|상승|회복|상회|개선|선전|확대|급등|강세)/;
  const negK = /(부진|악화|감소|하락|둔화|우려|급락|약세|경고|참사|적자)/;
  if (posK.test(t) && !negK.test(t)) return 'pos';
  if (negK.test(t) && !posK.test(t)) return 'neg';
  return 'neu';
}

/** 라벨 → 표시 문자 */
function sentimentArrow(label){
  return label === 'pos' ? '▲' : label === 'neg' ? '▼' : '—';
}

/** 화살표 옆에 점수(있을 때만) */
function sentimentScoreText(news){
  return typeof news.score === 'number' ? ` ${news.score.toFixed(2)}` : '';
}

// Render global data
function renderGlobalData() {
  // Headlines ticker
  const ticker = document.getElementById('headlines-ticker');
  if (ticker) {
    ticker.innerHTML = appData.global_headlines.map(headline =>
      `<span class="headline-item">${headline}</span>`
    ).join('');
  }

  // Economic indicators table
  const tableBody = document.querySelector('#indicators-table tbody');
  if (tableBody) {
    tableBody.innerHTML = '';
    appData.economic_indicators.forEach(indicator => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${indicator.country}</td>
        <td>${indicator.gdp}</td>
        <td>${indicator.inflation}</td>
        <td>${indicator.unemployment}</td>
      `;
      tableBody.appendChild(row);
    });
  }
}

// Render recommendations
function renderRecommendations() {
  // Books
  const booksGrid = document.getElementById('books-grid');
  if (booksGrid) {
    booksGrid.innerHTML = '';
    appData.book_recommendations.forEach(book => {
      const bookCard = document.createElement('div');
      bookCard.className = 'book-card';

      const ratingStars = '★'.repeat(Math.floor(book.rating)) +
                         (book.rating % 1 >= 0.5 ? '☆' : '') +
                         '☆'.repeat(5 - Math.ceil(book.rating));

      bookCard.innerHTML = `
        <div class="book-title">${book.title}</div>
        <div class="book-author">저자: ${book.author}</div>
        <div class="book-description">${book.description}</div>
        <div class="book-rating">
          <span class="rating-stars">${ratingStars}</span>
          <span>${book.rating}</span>
        </div>
      `;

      booksGrid.appendChild(bookCard);
    });
  }

  // Videos
  const videosGrid = document.getElementById('videos-grid');
  if (videosGrid) {
    videosGrid.innerHTML = '';
    appData.video_recommendations.forEach(video => {
      const videoCard = document.createElement('div');
      videoCard.className = 'video-card';

      videoCard.innerHTML = `
        <div class="video-thumbnail">📺</div>
        <div class="video-info">
          <div class="video-title">${video.title}</div>
          <div class="video-meta">
            <span>${video.channel}</span>
            <span>${video.duration}</span>
          </div>
          <div class="video-meta">
            <span>조회수: ${video.views}</span>
          </div>
        </div>
      `;

      videosGrid.appendChild(videoCard);
    });
  }
}

// Setup chatbot
function setupChatbot() {
  const chatInput = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');
  const faqItems = document.querySelectorAll('.faq-item');

  if (sendBtn) {
    sendBtn.addEventListener('click', sendMessage);
  }

  if (chatInput) {
    chatInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        sendMessage();
      }
    });
  }

  faqItems.forEach(item => {
    item.addEventListener('click', () => {
      const question = item.getAttribute('data-question');
      simulateUserMessage(question);
      setTimeout(() => sendBotResponse(question), 500);
    });
  });
}

function sendMessage() {
  const chatInput = document.getElementById('chat-input');
  const message = chatInput.value.trim();

  if (message) {
    addMessage(message, 'user');
    chatInput.value = '';

    setTimeout(() => {
      const response = generateBotResponse(message);
      addMessage(response, 'bot');
    }, 1000);
  }
}

function simulateUserMessage(message) {
  addMessage(message, 'user');
}

function sendBotResponse(question) {
  const response = chatResponses[question] || generateBotResponse(question);
  addMessage(response, 'bot');
}

function addMessage(content, sender) {
  const chatMessages = document.getElementById('chat-messages');
  const messageDiv = document.createElement('div');
  messageDiv.className = `message ${sender}-message`;

  messageDiv.innerHTML = `
    <div class="message-content">${content}</div>
  `;

  chatMessages.appendChild(messageDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function generateBotResponse(message) {
  const lowercaseMessage = message.toLowerCase();

  if (lowercaseMessage.includes('금리')) {
    return '현재 한국의 기준금리는 3.5%로 동결되었습니다. 금리 정책은 인플레이션 관리와 경제 성장의 균형을 고려하여 결정됩니다.';
  } else if (lowercaseMessage.includes('주식') || lowercaseMessage.includes('증시')) {
    return '최근 주식시장은 삼성전자의 양호한 실적 발표와 반도체 업계의 회복세로 긍정적인 흐름을 보이고 있습니다.';
  } else if (lowercaseMessage.includes('부동산')) {
    return '9월 부동산 거래량이 전월 대비 15% 증가했습니다. 정부의 부동산 정책 완화 기대감이 시장에 반영되고 있는 상황입니다.';
  } else if (lowercaseMessage.includes('환율')) {
    return '원달러 환율은 현재 1,350원대 후반에서 거래되고 있습니다. 미국의 금리 정책 불확실성이 주요 변수로 작용하고 있습니다.';
  } else {
    return '죄송합니다. 해당 질문에 대한 구체적인 정보를 찾지 못했습니다. 경제 관련된 다른 질문이나 FAQ를 이용해보세요.';
  }
}

// Modal setup
function setupModal() {
  const modal = document.getElementById('news-modal');
  const closeBtn = document.querySelector('.modal-close');

  if (closeBtn) {
    closeBtn.addEventListener('click', closeNewsModal);
  }

  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        closeNewsModal();
      }
    });
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
    modalStars.textContent = '★'.repeat(news.importance) + '☆'.repeat(5 - news.importance);

    modal.classList.remove('hidden');
  }
}

function closeNewsModal() {
  const modal = document.getElementById('news-modal');
  if (modal) {
    modal.classList.add('hidden');
  }
}

// Create charts
function createSentimentChart() {
  const ctx = document.getElementById('sentimentChart');
  if (!ctx) return;

  // Destroy existing chart if it exists
  if (sentimentChart) {
    sentimentChart.destroy();
  }

  sentimentChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['긍정', '중립', '부정'],
      datasets: [{
        data: [appData.sentiment_data.positive, appData.sentiment_data.neutral, appData.sentiment_data.negative],
        backgroundColor: ['#1FB8CD', '#FFC185', '#B4413C'],
        borderWidth: 2,
        borderColor: '#ffffff'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            padding: 20,
            font: {
              size: 12
            }
          }
        }
      }
    }
  });
}

function createTrendsChart() {
  const ctx = document.getElementById('trendsChart');
  if (!ctx) return;

  // Destroy existing chart if it exists
  if (trendsChart) {
    trendsChart.destroy();
  }

  trendsChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: ['10월', '11월', '12월'],
      datasets: [{
        label: '소비 전망 지수',
        data: [98, 102, 105],
        borderColor: '#1FB8CD',
        backgroundColor: 'rgba(31, 184, 205, 0.1)',
        fill: true,
        tension: 0.4
      }, {
        label: '투자 심리 지수',
        data: [95, 98, 101],
        borderColor: '#FFC185',
        backgroundColor: 'rgba(255, 193, 133, 0.1)',
        fill: true,
        tension: 0.4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: false,
          min: 90,
          max: 110
        }
      },
      plugins: {
        legend: {
          position: 'top'
        }
      }
    }
  });
}