// /static/js/news.js — 좌측 썸네일 카드 + 모달(본문 전체 노출)
(function () {
  // ----- 0) 설정값 -----
  const pageEl   = document.getElementById("news-page");
  const API_BASE = (pageEl && pageEl.dataset.apiBase) ? pageEl.dataset.apiBase : "http://127.0.0.1:8000";
  const NEWS_API = `${API_BASE}/news?limit=10`;
  const BRIEFING_API = `${API_BASE}/briefing/yesterday`;

  // ----- 1) DOM 캐시 -----
  const $list    = document.getElementById("news-list");
  const $loading = document.getElementById("news-loading");
  const $error   = document.getElementById("news-error");

  // 모달 요소
  const $modal      = document.getElementById("news-modal");
  const $modalClose = $modal?.querySelector(".modal-close");
  const $modalBack  = $modal?.querySelector(".modal-backdrop");
  const $mTitle   = document.getElementById("modal-title");
  const $mUpdated = document.getElementById("modal-updated");
  const $mImg     = document.getElementById("modal-image");
  const $mContent = document.getElementById("modal-content");
  const $mToggle  = document.getElementById("modal-toggle");
  const $mLink    = document.getElementById("modal-link");
  const $mPress  = document.getElementById("modal-press");

  // ----- 2) 유틸 -----
  const PLACEHOLDER =
    'data:image/svg+xml;utf8,' +
    encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80"><rect width="100%" height="100%" fill="#f3f4f6"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#9ca3af" font-size="12">no image</text></svg>');

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function ellipsis(t, n = 150) {
    if (!t) return "";
    t = String(t).trim();
    return t.length > n ? t.slice(0, n) + "…" : t;
  }
  // ----- 안정형 fetchJson (AbortSignal 제거 버전) -----
  async function fetchJson(url) {
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      console.log("[DEBUG] fetchJson ok:", url, data);
      return data;
    } catch (err) {
      console.error("[fetchJson] error:", err);
      throw err;
    }
  }

  function formatDate(iso) {
    if (!iso) return "";
    const s = String(iso);
    return s.includes("T") ? s.split("T")[0] : s.substring(0, 10);
  }
  function lockScroll(lock) {
    document.documentElement.style.overflow = lock ? "hidden" : "";
    document.body.style.overflow = lock ? "hidden" : "";
  }

  // ----- 3) 카드 렌더러 (좌측 썸네일 + 우측 텍스트) -----
  function renderCard(item) {
    const card = el("div", "news-card");
    card.dataset.id = item._id || "";
    card.tabIndex = 0;

    const wrap = el("div", "news-wrap");

    // 썸네일
    const img = el("img", "news-thumb");
    img.src = item.image || PLACEHOLDER;
    img.alt = item.title || "thumbnail";
    img.onerror = () => { img.src = PLACEHOLDER; };
    wrap.appendChild(img);

    // 텍스트
    const body   = el("div", "news-body");
    const title  = el("span", "news-title", item.title || "(제목 없음)");
    const meta   = el("div", "news-meta", formatDate(item.published_at || ""));
    const p      = el("p", "news-summary", ellipsis(item.summary || "", 150));

    body.appendChild(title);
    if (meta.textContent) body.appendChild(meta);
    body.appendChild(p);

    wrap.appendChild(body);
    card.appendChild(wrap);            // ⚠️ 중요: 카드에 wrap을 붙여야 화면에 보입니다.

    // 카드/Enter → 모달 열기
    const openIfId = () => {
      const id = card.dataset.id;
      if (id) openModal(id);
    };
    card.addEventListener("click", openIfId);
    card.addEventListener("keydown", (e) => { if (e.key === "Enter") openIfId(); });

    return card;
  }

  // ----- 4) 뉴스 목록 로드 -----
// ----- 4) 뉴스 목록 로드 (페이지네이션 포함) -----
let currentPage = 1;    // 현재 페이지
const limit = 10;       // 페이지당 기사 수

async function loadNews(page = 1) {
  currentPage = page;
  const skip = (page - 1) * limit;
  const apiUrl = `${API_BASE}/news?limit=${limit}&skip=${skip}`;

  $loading.style.display = "block";
  $error.style.display   = "none";
  $list.innerHTML = "";

  try {
    const items = await fetchJson(apiUrl, 8000);
    $loading.style.display = "none";

    if (!Array.isArray(items) || items.length === 0) {
      $list.appendChild(el("p", "muted", "표시할 뉴스가 없습니다."));
      return;
    }
    items.forEach(it => $list.appendChild(renderCard(it)));

    // 페이지 네비게이션 표시
    renderPagination();
  } catch (e) {
    console.error("[news] load error:", e);
    $loading.style.display = "none";
    $error.style.display = "block";
    $error.textContent = "뉴스를 불러오지 못했습니다.";
  }
}

// ----- 페이지 버튼 렌더링 -----
function renderPagination() {
  const $pagination = document.getElementById("pagination");
  if (!$pagination) return;
  $pagination.innerHTML = "";

  const prevBtn = el("button", "page-btn", "이전");
  const nextBtn = el("button", "page-btn", "다음");

  prevBtn.disabled = currentPage === 1;
  prevBtn.onclick = () => loadNews(currentPage - 1);
  nextBtn.onclick = () => loadNews(currentPage + 1);

  $pagination.appendChild(prevBtn);
  $pagination.appendChild(el("span", "page-info", `${currentPage} 페이지`));
  $pagination.appendChild(nextBtn);
}
// ----- 5) 전일 브리핑 로드 (카테고리별 표시) -----
async function loadBriefing() {
  const card = document.querySelector(".briefing-card");
  if (!card) return;

  const container = card.querySelector(".briefing-content");
  if (!container) return;

  try {
    const data = await fetchJson(BRIEFING_API, 8000);
    console.log("[DEBUG] briefing data:", data); // ✅ 실제 데이터 확인용

    // 기존 내용 초기화
    container.innerHTML = "";

    // 날짜 표시
    const datePrefix = data.date ? `(${data.date})` : "";
    const dateEl = el("p", "briefing-date", `${datePrefix} 전일 카테고리별 요약`);
    container.appendChild(dateEl);

    // 카테고리 검증
    if (!data.categories || !Array.isArray(data.categories) || data.categories.length === 0) {
      container.appendChild(el("p", "muted", "전일 기사 요약이 없습니다."));
      return;
    }

    // ✅ 카테고리별 박스 렌더링
    for (const cat of data.categories) {
      const box = el("div", "briefing-box");

      const title = el("h5", "briefing-title", `📌 ${cat.category || "분류 없음"}`);
      box.appendChild(title);

      const summary = el("p", "briefing-summary", cat.summary || "요약 없음");
      box.appendChild(summary);

      // 하이라이트(태그)
      const tagWrap = el("div", "briefing-highlights");
      if (Array.isArray(cat.highlights) && cat.highlights.length > 0) {
        for (const tag of cat.highlights) {
          const span = el("span", "highlight", tag);
          tagWrap.appendChild(span);
        }
      }
      box.appendChild(tagWrap);

      // box → container
      container.appendChild(box);
    }

  } catch (e) {
    console.warn("[briefing] load error:", e);
    container.innerHTML = `<p class="error">요약 데이터를 불러오지 못했습니다.</p>`;
  }
}


  // ----- 6) 모달 동작 -----
  function showModal() {
    if (!$modal) return;
    $modal.classList.add("open");
    $modal.setAttribute("aria-hidden", "false");
    lockScroll(true);
  }
  function hideModal() {
    if (!$modal) return;
    $modal.classList.remove("open");
    $modal.setAttribute("aria-hidden", "true");
    lockScroll(false);
  }
  $modalClose?.addEventListener("click", hideModal);
  $modalBack?.addEventListener("click", hideModal);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hideModal(); });

  // ----- 7) 상세 열기 -----
  async function openModal(id) {
    try {
      const data = await fetchJson(`${API_BASE}/news/${encodeURIComponent(id)}`, 8000);

      $mTitle.textContent   = data.title || "(제목 없음)";
      $mUpdated.textContent = formatDate(data.updated_at) || "";

      if (data.image) {
        $mImg.src = data.image;
        $mImg.alt = data.title || "article image";
        $mImg.style.display = "block";
        $mImg.onerror = () => { $mImg.style.display = "none"; };
      } else {
        $mImg.removeAttribute("src");
        $mImg.style.display = "none";
      }

      $mContent.textContent = data.content || "";
      if ($mToggle) $mToggle.style.display = "none";

      if (data.url) { $mLink.href = data.url; $mLink.style.display = "inline-block"; }
      else { $mLink.removeAttribute("href"); $mLink.style.display = "none"; }

      $mPress.textContent = data.press ? `출처: ${data.press}` : "";
      showModal();
    } catch (e) {
      console.error("[modal] load detail error:", e);
      alert("상세를 불러오지 못했습니다.");
    }
  }

  // ----- 8) 시작 -----
  document.addEventListener("DOMContentLoaded", async () => {
    await loadNews();
    await loadBriefing();
  });
})();