// /static/js/youtube.js
const API = "/api"; // 스프링으로 통합

function byId(id){ return document.getElementById(id); }
function fmtNum(x){ return x ? x.toLocaleString() : "0"; }

// ========== 워드클라우드 ==========
function renderWordCloud(pairs){
    const canvas = byId("wordCloud");
    if(!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0,0,canvas.width,canvas.height);

    // 유효한 항목만 필터 (text 존재 + count>0)
    const valid = Array.isArray(pairs) ? pairs.filter(p => p && p.text && Number(p.count) > 0) : [];

    if(valid.length < 2){
        ctx.font="16px Arial"; ctx.fillStyle="#666"; ctx.textAlign="center";
        ctx.fillText("워드클라우드 데이터가 없습니다.", canvas.width/2, canvas.height/2);
        return;
    }
    if(typeof WordCloud!=="function"){
        ctx.font="16px Arial"; ctx.fillStyle="#c00"; ctx.textAlign="left";
        ctx.fillText("wordcloud2.js 로드 실패",20,50); return;
    }
    WordCloud(canvas,{
        list: valid.map(d=>[String(d.text), Number(d.count)]),
        gridSize:10, weightFactor:5, minSize:12, maxRotation:0,
        fontFamily:"Arial", color:"random-dark", backgroundColor:"#fafafa", rotateRatio:0
    });
}

// ========== 메인 ==========
function updateMain(d){
    byId("mainTitle").textContent = d.title || "제목 없음";
    byId("mainDate").textContent  = `업로드: ${d.published_at || "-"}`;
    byId("mainViews").textContent = `조회수: ${fmtNum(d.views)}`;
    byId("mainComments").textContent = `댓글: ${fmtNum(d.comments)}`;
    byId("videoFrame").src = d.video_url || (d.video_id ? `https://www.youtube.com/embed/${encodeURIComponent(d.video_id)}?rel=0` : "");
}

// ========== 감정 분포 차트 ==========
let pieChart;
function renderPieChart(sentiment) {
    const container = byId("pieChart");
    if (!container) return;
    const ctx = container.getContext("2d");

    // 백엔드 라벨과 동일한 7클래스 고정 순서
    const ORDER = [
        "행복(Happiness)", "중립(Neutral)", "분노(Anger)",
        "슬픔(Sadness)", "놀람(Surprise)", "공포(Fear)", "혐오(Disgust)"
    ];

    const labels = [];
    const data = [];
    ORDER.forEach(k => {
        labels.push(k);
        data.push(sentiment && sentiment[k] ? Number(sentiment[k]) : 0);
    });

    const total = data.reduce((a, b) => a + b, 0);
    if (pieChart) {
        try { pieChart.destroy(); } catch (_) {}
    }
    ctx.clearRect(0, 0, container.width, container.height);

    if (total === 0) {
        ctx.font = "16px Arial";
        ctx.fillStyle = "#666";
        ctx.textAlign = "center";
        ctx.fillText("감정 데이터가 없습니다.", container.width / 2, container.height / 2);
        return;
    }

    // 차트 색상 팔레트
    const colors = [
        "#4caf50", "#9e9e9e", "#f44336",
        "#2196f3", "#ff9800", "#9c27b0", "#607d8b"
    ];

    // ✅ 차트 설정 (왼쪽 파이 + 오른쪽 범례)
    pieChart = new Chart(ctx, {
        type: "pie",
        data: { labels, datasets:[{ data, backgroundColor: colors, borderWidth: 1 }] },
        options: {
            responsive: true,
            maintainAspectRatio: true,   // ✅ 원 비율 유지
            aspectRatio: 1,              // ✅ 정사각형 (1:1)
            radius: '100%',
            layout: { padding: 10 },
            plugins: {
                legend: {
                    position: "right",
                    align: "center",
                    labels: { boxWidth: 20, font: { size: 13 }, padding: 10, color: "#333" }
                }
            }
        }
    });
}

// ========== 분석 조회 ==========
function loadAnalysis(video_id){
  const url = `${API}/analysis/${encodeURIComponent(video_id)}?topn=100&limit=1000`;
  fetch(url)
    .then(res=>res.json())
    .then(data=>{
      renderPieChart(data.sentiment||{});
      renderWordCloud(data.wordcloud||[]);

      // ===== 감정 단어를 버튼 스타일로 감싸기 =====
      const emotionMap = {
        "중립": "neutral",
        "혐오": "disgust",
        "분노": "anger",
        "슬픔": "sadness",
        "공포": "fear",
        "놀람": "surprise",
        "행복": "happiness"
      };

        let summary = data.summary || "분석 결과 없음";

        // ✅ 감정명 + 영문 둘 다 매칭되게 정규식 교체
        for (const [k, cls] of Object.entries(emotionMap)) {
          const regex = new RegExp(`\\(${k}\\([^)]*\\)\\)`, "g");
          // 예: (중립(Neutral)) 전체를 찾음
          summary = summary.replace(regex, `<span class="emotion-btn ${cls}">$&</span>`);
        }

        const analysisEl = byId("analysisText");
        analysisEl.innerHTML = summary;   // ✅ textContent → innerHTML
      // 댓글 목록 렌더링
      const commentsDiv = byId("commentList");
      commentsDiv.innerHTML = "";
      (data.comments||[]).forEach(c=>{
        const div = document.createElement("div");
        div.className = "comment";
        div.textContent = `${c.text} (${c.emotion || "Unknown"})`;
        commentsDiv.appendChild(div);
      });
    })
    .catch(err=>{
      console.error("분석 데이터 불러오기 실패:", err);
      byId("analysisText").textContent = "분석 결과 로딩 실패";
      renderPieChart({});
      renderWordCloud([]);
    });
}


// ========== 목록/상세 ==========
// /static/js/youtube.js

async function loadVideos(category = null, sort_by = "latest") {
  const params = new URLSearchParams();
  if (category) params.append("category", category);
  if (sort_by) params.append("sort_by", sort_by);

  try {
    const res = await fetch(`${API}/videos?${params.toString()}`);
    const videos = await res.json();
    const list = byId("thumbnailList");
    if (!list) return;

    list.innerHTML = "";

    if (!Array.isArray(videos) || videos.length === 0) {
      list.innerHTML = "<div class='empty'>영상이 없습니다.</div>";
      return;
    }

    // 썸네일 목록 렌더링
    videos.forEach(v => {
      const div = document.createElement("div");
      div.className = "thumbnail-box";
      div.innerHTML = `
        <img src="${v.thumbnail || "https://via.placeholder.com/280x160"}" alt="썸네일">
        <div class="thumbnail-title">${v.title || ""}</div>`;
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
    const first = videos[0];
    if (first) {
      const detail = await fetch(`${API}/videos/${encodeURIComponent(first.video_id)}`).then(r => r.json());
      updateMain(detail);
      loadAnalysis(first.video_id);
    }
  } catch (err) {
    console.error("영상 목록 불러오기 실패:", err);
  }
}


