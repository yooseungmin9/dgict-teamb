(() => {
  const API = 'http://127.0.0.1:8011/count'; // 서버 계약: { ok, total, updated_at }
  const panel = document.querySelector('#panel-news-count .card__body');
  if (!panel) return;

  const POLL_MS = 10_000;           // 10초마다 폴링
  const MAX_BACKOFF_MS = 5 * 60_000; // 최대 백오프 5분
  let backoff = 0;
  let timerId = null;
  let running = false;
  let aborter = null;

  // 숫자 포맷터(로케일 한국)
  const fmt = (n) => Number(n).toLocaleString('ko-KR');

  // 초기 DOM 구성(한 번만)
  function ensureScaffold() {
    if (panel.dataset.scaffold === '1') return;
    panel.innerHTML = `
      <div class="count__value" id="count-value">-</div>
      <div class="count__meta" id="count-meta">업데이트: -</div>
    `;
    panel.dataset.scaffold = '1';
  }

  // 카운트업 애니메이션
  function animateNumber($el, to, ms = 700) {
    if (!$el) return;
    const nowAttr = Number($el.dataset.value ?? '');
    const from = Number.isFinite(nowAttr) ? nowAttr : Number(($el.textContent || '').replace(/\D/g, '')) || 0;
    const target = Math.max(0, Number(to) || 0);
    if (from === target) return;

    $el.dataset.value = String(target);
    const start = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - start) / ms);
      const ease = 1 - Math.pow(1 - k, 3); // cubic ease-out
      const val = Math.round(from + (target - from) * ease);
      $el.textContent = `${fmt(val)}개`;
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  // 렌더러: 성공 케이스
  function renderOk(data) {
    ensureScaffold();
    const $val = document.getElementById('count-value');
    const $meta = document.getElementById('count-meta');

    animateNumber($val, data.total);
    const when = data.updated_at ? new Date(data.updated_at).toLocaleString('ko-KR') : '-';
    $meta.textContent = `업데이트: ${when}`;
  }

  // 상태 텍스트 렌더링
  function renderState(text, cls) {
    panel.innerHTML = `<div class="${cls}" role="status">${text}</div>`;
    panel.dataset.scaffold = '0';
  }

  // fetch + 적용
  async function fetchAndApply() {
    if (running) return;
    running = true;
    if (aborter) aborter.abort();
    aborter = new AbortController();

    try {
      // 캐시 무효화를 위해 ts 파라미터 사용
      const url = `${API}?ts=${Date.now()}`;
      const r = await fetch(url, { signal: aborter.signal, cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();

      if (data && data.ok) renderOk(data);
      else renderState('데이터 없음', 'count__error');

      backoff = 0; // 성공 시 백오프 초기화
    } catch (e) {
      // 에러 표시
      renderState('불러오기 실패', 'count__error');
      // eslint-disable-next-line no-console
      console.error('[count-realtime-plus]', e);
      // 지수 백오프(최대 5분)
      backoff = Math.min(backoff ? backoff * 2 : 5_000, MAX_BACKOFF_MS);
    } finally {
      running = false;
    }
  }

  // 스케줄러: 탭 가시성 반영
  function schedule() {
    clearTimeout(timerId);
    if (document.hidden) {
      // 비가시 상태에서는 과한 네트워크 호출 방지
      timerId = setTimeout(schedule, 3_000);
      return;
    }
    const delay = backoff || 0;
    timerId = setTimeout(async () => {
      await fetchAndApply();
      timerId = setTimeout(schedule, backoff || POLL_MS);
    }, delay);
  }

  // 탭 전환 이벤트: 숨길 때 fetch 취소, 복귀 시 재스케줄
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && aborter) aborter.abort();
    schedule();
  });

  // 초기 로딩 상태 안내 후 시작
  renderState('로딩 중…', 'count__loading');
  schedule();

  // === MOCK 테스트: 버튼 클릭 시 임의 데이터로 카운트업 확인 ===
  window.addEventListener('count:mock', () => {
    renderOk({
      ok: true,
      total: Math.floor(Math.random() * 200000) + 1000,
      updated_at: new Date().toISOString(),
    });
  });
})();