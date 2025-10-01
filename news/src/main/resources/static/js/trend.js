// /static/js/trends.js
// [입문자용] 트렌드 차트 + 키워드 랭킹

let trendChart = null;

// 🔹 카테고리별 트렌드 데이터 로딩
async function loadTrends() {
  const days = document.getElementById("trendDays").value;

  try {
    const res = await fetch(`/api/trends/category-trends?days=${days}`);
    const json = await res.json();

    const ctx = document.getElementById("categoryTrendChart");
    if (!ctx) return;

    // 이전 차트 제거
    if (trendChart) {
      trendChart.destroy();
      trendChart = null;
    }

    const labels = json.dates;
    const datasets = Object.entries(json.categories).map(([cat, vals]) => {
      const colors = {
        "증권": "#1f77b4",
        "금융": "#ff7f0e",
        "부동산": "#2ca02c",
        "산업": "#d62728",
        "글로벌경제": "#9467bd",
        "일반": "#8c564b"
      };
      return {
        label: cat,
        data: vals,
        borderColor: colors[cat] || "gray",
        backgroundColor: (colors[cat] || "gray") + "55",
        tension: 0.3,
        fill: false
      };
    });

    trendChart = new Chart(ctx, {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "top" } },
        scales: { y: { beginAtZero: true } }
      }
    });
  } catch (err) {
    console.error("트렌드 데이터 불러오기 실패:", err);
  }

  // 키워드 랭킹도 같이 로드
  loadKeywordRanking(days);
}

// 🔹 키워드 랭킹 로딩
async function loadKeywordRanking(days = 30) {
  try {
    const res = await fetch(`/api/trends/keyword-ranking?days=${days}&topn=20`);
    const data = await res.json();

    const tbody = document.getElementById("keywordRankingBody");
    tbody.innerHTML = "";

    data.slice(0, 20).forEach((row, idx) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${idx + 1}</td>
        <td>${row.keyword}</td>
        <td>${row.count}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("키워드 랭킹 불러오기 실패:", err);
  }
}

// 🔹 이벤트 바인딩
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("trendDays").addEventListener("change", () => loadTrends());
});