// /static/js/news.js — 뉴스 카드 디자인 유지 + 전일 브리핑 기능 추가
(function () {
  const list = document.getElementById("news-list");

  // --- 카드 "더 보기" 토글 ---
  list.addEventListener("click", (e) => {
    const btn = e.target.closest(".more-toggle");
    if (!btn) return;
    e.stopPropagation();
    e.preventDefault();
    const card = btn.closest(".news-card");
    const expanded = card.getAttribute("data-expanded") === "true";
    card.setAttribute("data-expanded", expanded ? "false" : "true");
    btn.textContent = expanded ? "더 보기" : "접기";
  });

  // --- 뉴스 클릭 → 모달 열기 ---
  const modal = document.getElementById("news-modal");
  if (modal) {
    const closeBtn = modal.querySelector(".modal-close");
    const backdrop = modal.querySelector(".modal-backdrop");
    const $mTitle = document.getElementById("modal-title");
    const $mUpdated = document.getElementById("modal-updated");
    const $mImg = document.getElementById("modal-image");
    const $mContent = document.getElementById("modal-content");
    const $mLink = document.getElementById("modal-link");
    const $mPress = document.getElementById("modal-press");

    const lockScroll = (lock) => {
      document.documentElement.style.overflow = lock ? "hidden" : "";
      document.body.style.overflow = lock ? "hidden" : "";
    };
    const showModal = () => {
      modal.classList.add("open");
      modal.setAttribute("aria-hidden", "false");
      lockScroll(true);
    };
    const hideModal = () => {
      modal.classList.remove("open");
      modal.setAttribute("aria-hidden", "true");
      lockScroll(false);
    };

    closeBtn.addEventListener("click", hideModal);
    backdrop.addEventListener("click", hideModal);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") hideModal();
    });

    async function openModalById(id) {
      try {
        const res = await fetch(`/pages/news/${encodeURIComponent(id)}`);
        if (!res.ok) throw new Error("HTTP " + res.status);
        const data = await res.json();

        $mTitle.textContent = data.title || "(제목 없음)";
        const updated = data.updated_at || data.publishedAt || data.published_at;
        $mUpdated.textContent = updated ? String(updated).substring(0, 10) : "";

        if (data.image) {
          $mImg.src = data.image;
          $mImg.alt = data.title || "article image";
          $mImg.style.display = "block";
          $mImg.onerror = () => {
            $mImg.style.display = "none";
          };
        } else {
          $mImg.removeAttribute("src");
          $mImg.style.display = "none";
        }

        $mContent.textContent = data.content || data.summary || "";
        if (data.url) {
          $mLink.href = data.url;
          $mLink.style.display = "inline-block";
        } else {
          $mLink.removeAttribute("href");
          $mLink.style.display = "none";
        }

        $mPress.textContent = data.press ? "출처: " + data.press : "";
        showModal();
      } catch (e) {
        console.error(e);
        alert("상세를 불러오지 못했습니다.");
      }
    }

    // 카드 클릭 시 모달 열기
    list.addEventListener("click", (e) => {
      const card = e.target.closest(".news-card");
      if (!card || e.target.closest(".more-toggle")) return;
      const id = card.getAttribute("data-id");
      if (id) openModalById(id);
    });
  }

  // ✅ 전일 브리핑 요약 로드
  async function loadBriefing() {
    const wrap = document.querySelector(".briefing-content");
    if (!wrap) return;

    // 1) 우선 스프링 경로 시도 → 실패하면 FastAPI 경로(API_BASE)로 폴백
    const pageEl   = document.getElementById("news-page");
    const API_BASE = (pageEl && pageEl.dataset.apiBase) ? pageEl.dataset.apiBase : "";
    const candidates = [
      "/pages/news/api/briefing/yesterday",              // Spring(DB 직결) 우선:contentReference[oaicite:3]{index=3}
      API_BASE ? `${API_BASE}/briefing/yesterday` : null // FastAPI 폴백:contentReference[oaicite:4]{index=4}
    ].filter(Boolean);

    // 관대한 파서: 다양한 필드명을 지원
    const parseBriefing = (data) => {
      if (!data || typeof data !== "object") return { date: "", categories: [] };

      // date 후보
      const date = data.date || data.yesterday || data.briefingDate || data.dt || "";

      // categories 후보
      let cats = data.categories || data.cats || data.items || data.data || [];
      if (!Array.isArray(cats) && typeof cats === "object") {
        // 객체 맵 형태면 값 배열로
        cats = Object.values(cats);
      }
      // 각 항목 키 보정
      cats = Array.isArray(cats) ? cats.map(c => ({
        category: c.category || c.cat || c.name || c.title || "분류 없음",
        summary:  c.summary  || c.desc || c.text  || c.overview || "",
        highlights: Array.isArray(c.highlights) ? c.highlights :
            Array.isArray(c.tags)       ? c.tags :
                typeof c.keywords === "string" ? c.keywords.split(/[,|]/).map(s=>s.trim()).filter(Boolean) :
                    Array.isArray(c.keywords) ? c.keywords : []
      })) : [];

      return { date, categories: cats };
    };

    // 실제 호출
    try {
      let ok = false, payload = null, lastErr = null;

      for (const url of candidates) {
        try {
          const res = await fetch(url, { headers: { "Accept": "application/json" }});
          console.debug("[briefing] try:", url, "→", res.status);
          if (!res.ok) { lastErr = new Error("HTTP " + res.status); continue; }

          // JSON만 받도록 (HTML 응답 대비)
          const ct = res.headers.get("content-type") || "";
          if (!ct.includes("application/json")) {
            lastErr = new Error("Not JSON: " + ct);
            continue;
          }
          const raw = await res.json();
          const parsed = parseBriefing(raw);
          payload = parsed;
          ok = true;
          break;
        } catch (e) {
          lastErr = e;
        }
      }

      // 렌더링
      wrap.innerHTML = "";
      if (!ok || !payload) {
        console.warn("[briefing] load failed:", lastErr);
        wrap.innerHTML = `<p class="error">요약 데이터를 불러오지 못했습니다.</p>`;
        return;
      }

      const datePrefix = payload.date ? `(${payload.date}) ` : "";
      const dateEl = document.createElement("p");
      dateEl.className = "briefing-date";
      dateEl.textContent = `${datePrefix}전일 카테고리별 요약`;
      wrap.appendChild(dateEl);

      if (!Array.isArray(payload.categories) || payload.categories.length === 0) {
        wrap.innerHTML += `<p class="muted">전일 기사 요약이 없습니다.</p>`;
        return;
      }

      for (const cat of payload.categories) {
        const box = document.createElement("div");
        box.className = "briefing-box";

        const h5 = document.createElement("h5");
        h5.className = "briefing-title";
        h5.textContent = `📌 ${cat.category || "분류 없음"}`;

        const p = document.createElement("p");
        p.className = "briefing-summary";
        p.textContent = cat.summary || "요약 없음";

        const tags = document.createElement("div");
        tags.className = "briefing-highlights";
        if (Array.isArray(cat.highlights)) {
          for (const t of cat.highlights) {
            const span = document.createElement("span");
            span.className = "highlight";
            span.textContent = t;
            tags.appendChild(span);
          }
        }

        box.append(h5, p, tags);
        wrap.appendChild(box);
      }
    } catch (e) {
      console.warn("[briefing] unexpected error:", e);
      wrap.innerHTML = `<p class="error">요약 데이터를 불러오지 못했습니다.</p>`;
    }
  }
})();
