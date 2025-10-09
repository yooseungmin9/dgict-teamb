// /static/js/hot-topic.js
(function() {
  console.log("[hot-topic.js] loaded");

  const $body = document.getElementById("hot-topic-body");
  if (!$body) {
    console.warn("[hot-topic.js] hot-topic-body 없음");
    return;
  }

  const API = "http://localhost:8007/keywords/top";

  async function loadHotTopics() {
    try {
      $body.innerHTML = '<p style="text-align:center;">로딩 중...</p>';

      const res = await fetch(`${API}?top_n=10`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      console.log("[hot-topic.js] 데이터:", data);

      if (!data.today || !data.yesterday) {
        throw new Error("데이터 구조 오류");
      }

      renderHotTopics(data.today, data.yesterday);

    } catch (e) {
      console.error("[hot-topic.js] 실패:", e);
      $body.innerHTML = `<p style="color:red; text-align:center;">로딩 실패: ${e.message}</p>`;
    }
  }

  function renderHotTopics(today, yesterday) {
    const yesterdayMap = new Map(yesterday.map(k => [k.keyword, k.count]));

    const compared = today.map(k => {
      const prevCount = yesterdayMap.get(k.keyword) || 0;
      const change = k.count - prevCount;
      const changePercent = prevCount > 0
        ? ((change / prevCount) * 100).toFixed(1)
        : "신규";

      return {
        keyword: k.keyword,
        count: k.count,
        change: change,
        changePercent: changePercent,
        isNew: prevCount === 0
      };
    });

    compared.sort((a, b) => b.change - a.change);

    let html = '<div style="display:flex; flex-direction:column; gap:10px;">';

    compared.slice(0, 5).forEach((item, idx) => {
      const emoji = item.change > 0 ? '🔥' : item.change < 0 ? '📉' : '➖';
      const color = item.change > 0 ? '#e74c3c' : item.change < 0 ? '#3498db' : '#95a5a6';

      html += `
        <div style="display:flex; align-items:center; gap:12px; padding:10px; background:#f8f9fa; border-radius:6px; border-left:4px solid ${color};">
          <div style="font-size:20px; font-weight:bold; color:${color}; min-width:30px;">${idx + 1}</div>
          <div style="flex:1;">
            <div style="font-size:15px; font-weight:600; margin-bottom:4px;">${item.keyword}</div>
            <div style="font-size:12px; color:#666;">
              <span>언급 ${item.count}건</span>
              <span style="margin-left:8px; color:${color};">
                ${emoji} ${item.isNew ? '신규' :
                  item.change > 0 ? `+${item.change}건 (↑${item.changePercent}%)` :
                  item.change < 0 ? `${item.change}건 (↓${Math.abs(item.changePercent)}%)` :
                  '변동없음'}
              </span>
            </div>
          </div>
        </div>
      `;
    });

    html += '</div>';
    $body.innerHTML = html;
  }

  loadHotTopics();
  setInterval(loadHotTopics, 5 * 60 * 1000);
})();