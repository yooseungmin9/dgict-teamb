const API = "http://127.0.0.1:8008"; // FastAPI 서버 주소

function byId(id) { return document.getElementById(id); }
function fmtNum(x) { return x ? x.toLocaleString() : "0"; }

// ====================
// 워드클라우드
// ====================
function renderWordCloud(pairs) {
  const canvas = byId("wordCloud");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (!pairs || pairs.length === 0 || (pairs.length === 1 && pairs[0].text === "댓글없음")) {
    ctx.font = "16px Arial";
    ctx.fillStyle = "#666";
    ctx.fillText("워드클라우드 데이터가 없습니다.", 20, 50);
    return;
  }

  if (typeof WordCloud !== "function") {
    ctx.font = "16px Arial";
    ctx.fillStyle = "#c00";
    ctx.fillText("wordcloud2.js 로드 실패", 20, 50);
    return;
  }

  WordCloud(canvas, {
    list: pairs.map(d => [d.text, d.count]),
    gridSize: 10,
    weightFactor: 5,
    minSize: 12,
    maxRotation: 0,
    fontFamily: "Arial",
    color: "random-dark",
    backgroundColor: "#fafafa",
    rotateRatio: 0
  });
}

// ====================
// 메인 영상 업데이트
// ====================
function updateMain(d) {
  byId("mainTitle").textContent = d.title || "제목 없음";
  byId("mainDate").textContent = `업로드: ${d.published_at || "-"}`;
  byId("mainViews").textContent = `조회수: ${fmtNum(d.views)}`;
  byId("mainComments").textContent = `댓글: ${fmtNum(d.comments)}`;
  byId("videoFrame").src = d.video_url || "";
}

// ====================
// 감정 분포 차트
// ====================
let pieChart;
function renderPieChart(sentiment) {
  const ctx = byId("pieChart").getContext("2d");
  if (pieChart) pieChart.destroy();
  pieChart = new Chart(ctx, {
    type: "pie",
    data: {
      labels: Object.keys(sentiment),
      datasets: [{
        data: Object.values(sentiment),
        backgroundColor: ["#4caf50","#2196f3","#f44336","#ff9800","#9e9e9e","#8bc34a","#9c27b0"],
      }],
    },
    options: { responsive: true, plugins: { legend: { position: "top" } } },
  });
}

// ====================
// 분석 데이터 로드
// ====================
function loadAnalysis(video_id) {
  fetch(`${API}/analysis/${encodeURIComponent(video_id)}?topn=100`)
    .then(res => res.json())
    .then(data => {
      renderPieChart(data.sentiment || {});
      renderWordCloud(data.wordcloud || []);

      // 분석 요약
      byId("analysisText").textContent = data.summary || "분석 결과 없음";

      // 댓글 샘플
      const commentsDiv = byId("commentList");
      commentsDiv.innerHTML = "";
      (data.comments || []).forEach(c => {
        const div = document.createElement("div");
        div.className = "comment";
        div.textContent = `${c.text} (${c.emotion || "Unknown"})`;
        commentsDiv.appendChild(div);
      });
    })
    .catch(err => {
      console.error("분석 데이터 불러오기 실패:", err);
      byId("analysisText").textContent = "분석 결과 로딩 실패";
    });
}

// ====================
// 썸네일 리스트 로드
// ====================
function loadVideos() {
  fetch(`${API}/videos`)
    .then(res => res.json())
    .then(videos => {
      const list = byId("thumbnailList");
      list.innerHTML = "";

      videos.forEach(v => {
        const div = document.createElement("div");
        div.className = "thumbnail-box";
        div.innerHTML = `
          <img src="${v.thumbnail || "https://via.placeholder.com/280x160"}" alt="썸네일">
          <div class="thumbnail-title">${v.title || ""}</div>
        `;
        div.addEventListener("click", () => {
          fetch(`${API}/videos/${encodeURIComponent(v.video_id)}`)
            .then(r => r.json())
            .then(detail => {
              updateMain(detail);
              loadAnalysis(v.video_id);
            });
        });
        list.appendChild(div);
      });

      // 첫 번째 영상 자동 로드
      if (videos.length > 0) {
        fetch(`${API}/videos/${encodeURIComponent(videos[0].video_id)}`)
          .then(r => r.json())
          .then(detail => {
            updateMain(detail);
            loadAnalysis(videos[0].video_id);
          });
      }
    })
    .catch(err => {
      console.error("영상 목록 불러오기 실패:", err);
    });
}

// ====================
// 초기 실행
// ====================
window.addEventListener("DOMContentLoaded", loadVideos);
