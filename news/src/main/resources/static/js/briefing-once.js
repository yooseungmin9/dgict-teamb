// /static/js/briefing-once.js
(function () {
  if (window.__briefingSealInstalled) return;
  window.__briefingSealInstalled = true;

  const BRIEFING_KEY = "briefing:yesterday:v1";
  const origFetch = window.fetch;

  function isBriefingEndpoint(input) {
    try {
      const url = (typeof input === "string")
        ? new URL(input, location.origin)
        : (input && input.url) ? new URL(input.url, location.origin)
        : null;
      if (!url) return false;
      // path가 정확히 /briefing/yesterday 로 끝날 때만
      return /\/briefing\/yesterday\/?$/.test(url.pathname);
    } catch {
      return false;
    }
  }

  window.fetch = async function(input, init) {
    try {
      if (!isBriefingEndpoint(input)) {
        return origFetch.apply(this, arguments);
      }

      // 캐시가 있으면 즉시 응답(네트워크 차단)
      const cached = sessionStorage.getItem(BRIEFING_KEY);
      if (cached) {
        return new Response(cached, { status: 200, headers: { "Content-Type": "application/json" } });
      }

      // 최초 1회만 네트워크 허용
      const res = await origFetch.apply(this, arguments);
      try {
        const ct = res.headers.get("content-type") || "";
        if (res.ok && ct.includes("application/json")) {
          const text = await res.clone().text();
          sessionStorage.setItem(BRIEFING_KEY, text);
        }
      } catch {}
      return res;
    } catch {
      return origFetch.apply(this, arguments);
    }
  };
})();
