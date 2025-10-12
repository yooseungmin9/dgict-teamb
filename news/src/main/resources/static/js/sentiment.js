(() => {
  'use strict';

  /** DOM */
  const card = document.getElementById('sentiment-card');
  if (!card) return;

  const API_BASE = (card.dataset.api || '').trim();
  const ctx = document.getElementById('sentiment-chart')?.getContext('2d');

  const $btnCount = document.getElementById('btn-mode-count');
  const $btnRatio = document.getElementById('btn-mode-ratio');
  const $btnDay = document.getElementById('btn-g-day');
  const $btnWeek = document.getElementById('btn-g-week');
  const $btnMonth = document.getElementById('btn-g-month');
  const $sep = card.querySelector('.controls span');
  const $status = document.getElementById('sentiment-status');

  /** 상태 */
  const state = {
    mode: 'count', // 'count' | 'ratio'
    group: 'day',  // 'day' | 'week' | 'month'
    raw: [],       // [{date, 부정, 중립, 긍정}]
  };

  /** 유틸: 주차/월 키 */
  const toWeekKey = (d) => {
    const dt = new Date(`${d}T00:00:00`);
    const monday = new Date(dt);
    monday.setDate(dt.getDate() - ((dt.getDay() + 6) % 7));
    const y = monday.getFullYear();
    const jan1 = new Date(y, 0, 1);
    const w = Math.floor(((monday - jan1) / 86400000 + ((jan1.getDay() + 6) % 7)) / 7) + 1;
    return `${y}-W${String(w).padStart(2, '0')}`;
  };
  const toMonthKey = (d) => d.slice(0, 7);

  const groupRecords = (rows, g) => {
    if (g === 'day') return rows;
    const acc = {};
    for (const r of rows) {
      const k = g === 'week' ? toWeekKey(r.date) : toMonthKey(r.date);
      acc[k] ??= { date: k, 부정: 0, 중립: 0, 긍정: 0 };
      acc[k].부정 += +r.부정 || 0;
      acc[k].중립 += +r.중립 || 0;
      acc[k].긍정 += +r.긍정 || 0;
    }
    return Object.values(acc).sort((a, b) => a.date.localeCompare(b.date));
  };

  /** 색상: 기존 유지 */
  const colors = {
    neg: { bg: 'rgba(235,16,0,0.9)', bd: 'rgba(235,16,0,1)' },   // 부정
    neu: { bg: 'rgba(201,203,207,0.9)', bd: 'rgba(201,203,207,1)' }, // 중립
    pos: { bg: 'rgba(37,99,235,0.9)', bd: 'rgba(37,99,235,1)' }, // 긍정 (#2563eb)
  };

  /** 차트 인스턴스 */
  let chart = null;

  /** 공통 옵션: 애니메이션만 사용, 시각 속성은 유지 */
  const barOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 600, easing: 'easeOutQuart' },
    scales: {
      x: { stacked: true, grid: { display: false } },
      y: { stacked: true, beginAtZero: true },
    },
    plugins: {
      legend: { position: 'top' },
      datalabels: { display: false }, // 바차트 라벨은 기본 감춤
    },
  };

  const pieOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 600, easing: 'easeOutQuart' },
    plugins: {
      legend: { position: 'right' },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const label = ctx.label || '';
            const val = ctx.parsed || 0;
            const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
            const pct = total ? ((val / total) * 100).toFixed(1) : '0.0';
            return `${label}: ${val}건 (${pct}%)`;
          },
        },
      },
      datalabels: {
        color: '#fff',
        font: { weight: 'bold' },
        formatter: (value, ctx) => {
          const sum = ctx.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
          return sum ? `${((value / sum) * 100).toFixed(1)}%` : '0%';
        },
      },
    },
  };

  /** 데이터 → 차트데이터 빌드 */
  const buildBarData = (rows) => ({
    labels: rows.map((d) => d.date),
    datasets: [
      { label: '부정(<0)', data: rows.map((d) => +d.부정 || 0), stack: 's', backgroundColor: colors.neg.bg },
      { label: '중립(=0)', data: rows.map((d) => +d.중립 || 0), stack: 's', backgroundColor: colors.neu.bg },
      { label: '긍정(>0)', data: rows.map((d) => +d.긍정 || 0), stack: 's', backgroundColor: colors.pos.bg },
    ],
  });

  const buildPieData = (rows) => {
    let n = 0; let z = 0; let p = 0;
    for (const r of rows) { n += +r.부정 || 0; z += +r.중립 || 0; p += +r.긍정 || 0; }
    return {
      labels: ['부정(<0)', '중립(=0)', '긍정(>0)'],
      datasets: [{
        data: [n, z, p],
        backgroundColor: [colors.neg.bg, colors.neu.bg, colors.pos.bg],
        borderColor: [colors.neg.bd, colors.neu.bd, colors.pos.bd],
        borderWidth: 2,
      }],
    };
  };

  /** 차트 생성 또는 재사용 */
  const ensureChart = (type, data) => {
    if (chart && chart.config.type === type) return; // 동일 타입이면 재사용
    if (chart) chart.destroy(); // 타입이 바뀔 때만 파괴
    const opts = type === 'pie' ? pieOptions : barOptions;
    const plugins = type === 'pie' ? [ChartDataLabels] : [];
    chart = new Chart(ctx, { type, data, options: opts, plugins });
  };

  /** 동일 타입에서 데이터만 교체 후 update() */
  const updateChartData = (next) => {
    if (!chart) return;
    chart.data.labels = next.labels;
    const byLabel = new Map(chart.data.datasets.map((d) => [d.label, d]));
    next.datasets.forEach((nd) => {
      const cur = byLabel.get(nd.label);
      if (cur) cur.data = nd.data;         // 객체 재사용 → 애니메이션
      else chart.data.datasets.push(nd);   // 새 시리즈 추가
    });
    chart.data.datasets = chart.data.datasets.filter((d) => next.datasets.some((nd) => nd.label === d.label));
    chart.update();
  };

  /** 상태 기반 렌더 */
  const renderNow = () => {
    // chip 활성 토글
    const toggle = (el, on) => { if (!el) return; el.classList.toggle('active', on); el.setAttribute('aria-pressed', String(on)); };
    toggle($btnCount, state.mode === 'count');
    toggle($btnRatio, state.mode === 'ratio');
    toggle($btnDay, state.group === 'day');
    toggle($btnWeek, state.group === 'week');
    toggle($btnMonth, state.group === 'month');

    // 비율 모드에서는 그룹 선택 숨김
    const hideGroup = state.mode === 'ratio';
    [$btnDay, $btnWeek, $btnMonth].forEach((b) => {
      if (!b) return;
      b.style.display = hideGroup ? 'none' : '';
      b.tabIndex = hideGroup ? -1 : 0;
    });
    if ($sep) $sep.style.display = hideGroup ? 'none' : '';

    // 차트 타입 결정
    const grouped = groupRecords(state.raw, state.group);
    const needPie = state.mode === 'ratio';
    const type = needPie ? 'pie' : 'bar';

    if (!chart) {
      ensureChart(type, needPie ? buildPieData(grouped) : buildBarData(grouped));
    } else if (chart.config.type === type) {
      updateChartData(needPie ? buildPieData(grouped) : buildBarData(grouped));
    } else {
      ensureChart(type, needPie ? buildPieData(grouped) : buildBarData(grouped));
    }

    // 상태 텍스트
    if ($status) $status.textContent = needPie ? '표시: 비율(파이차트)' : `표시: 건수(막대차트) / ${state.group}`;
  };

  /** 데이터 로드 */
  const filterSort = (arr) => {
    const out = arr.filter((r) => ((+r.부정 || 0) + (+r.중립 || 0) + (+r.긍정 || 0)) > 0);
    out.sort((a, b) => String(a.date).localeCompare(String(b.date)));
    return out;
  };

  // 목업 생성기: data-api="mock" 일 때 사용
  const mockFetchRows = async () => {
    const today = new Date();
    const days = 10;
    const seq = [...Array(days)].map((_, i) => {
      const d = new Date(today); d.setDate(today.getDate() - (days - 1 - i));
      const date = d.toISOString().slice(0, 10);
      const base = 200 + Math.sin(i / 2) * 50;
      const neg = Math.max(0, Math.round(base * 0.3 + (Math.random() - 0.5) * 20));
      const neu = Math.max(0, Math.round(base * 0.5 + (Math.random() - 0.5) * 30));
      const pos = Math.max(0, Math.round(base * 0.6 + (Math.random() - 0.5) * 25));
      return { date, 부정: neg, 중립: neu, 긍정: pos };
    });
    return filterSort(seq);
  };

  const fetchRows = async () => {
    if (API_BASE.toLowerCase() === 'mock') return mockFetchRows();
    const url = `${API_BASE}?mode=${state.mode}`;
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    if (!Array.isArray(json)) throw new Error('응답이 배열이 아님');
    return filterSort(json);
  };

  /** 폴링 */
  let timer = null;
  let baseInterval = 10_000;
  let intervalMs = baseInterval;
  let backoff = 0;

  const tick = async () => {
    if (document.visibilityState !== 'visible') return;
    try {
      if ($status) $status.textContent = '갱신 중...';
      state.raw = await fetchRows();
      renderNow();
      backoff = 0;
      if (intervalMs !== baseInterval) { intervalMs = baseInterval; restart(); }
    } catch {
      // 실패 시 더미 유지 없이 직전 데이터로 렌더 지속. 간단 백오프.
      if ($status) $status.textContent = '네트워크 오류. 재시도 대기...';
      backoff = Math.min(backoff + 1, 5);
      const next = baseInterval * 2 ** backoff;
      if (intervalMs !== next) { intervalMs = next; restart(); }
    }
  };

  const start = () => { if (!timer) timer = setInterval(tick, intervalMs); };
  const stop = () => { if (timer) clearInterval(timer); timer = null; };
  const restart = () => { stop(); start(); };
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') start(); else stop(); });

  /** 초기화 */
  const initial = async () => {
    try {
      if ($status) $status.textContent = '로딩중...';
      state.raw = await fetchRows();
    } catch {
      // 초기 실패 시 목업 2점만 표시해 시각 피드백
      const today = new Date();
      const fmt = (d) => d.toISOString().slice(0, 10);
      const y = new Date(today); y.setDate(today.getDate() - 1);
      state.raw = [{ date: fmt(y), 부정: 120, 중립: 260, 긍정: 220 }, { date: fmt(today), 부정: 80, 중립: 200, 긍정: 300 }];
      if ($status) $status.textContent = '로딩 오류. 임시 데이터 표시 중';
    }
    renderNow();
    start();
  };

  // 이벤트
  $btnCount?.addEventListener('click', async () => {
    if (state.mode === 'count') return;
    state.mode = 'count';
    await initial(); // 모드가 바뀌면 초기 로드로 동기화
  });
  $btnRatio?.addEventListener('click', async () => {
    if (state.mode === 'ratio') return;
    state.mode = 'ratio';
    await initial();
  });
  $btnDay?.addEventListener('click', () => { if (state.group !== 'day') { state.group = 'day'; renderNow(); } });
  $btnWeek?.addEventListener('click', () => { if (state.group !== 'week') { state.group = 'week'; renderNow(); } });
  $btnMonth?.addEventListener('click', () => { if (state.group !== 'month') { state.group = 'month'; renderNow(); } });

  // 시작
  initial();
})();
