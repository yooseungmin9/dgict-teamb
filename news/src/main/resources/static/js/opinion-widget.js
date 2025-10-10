// /js/opinion-widget.js
document.addEventListener("DOMContentLoaded", async () => {
  const target = document.getElementById("opinion-body");

  try {
    const res = await fetch("http://127.0.0.1:8008/youtube/results");
    const data = await res.json();

    if (!data || data.error) {
      target.innerHTML = "<p style='text-align:center;color:#999;'>데이터 없음</p>";
      return;
    }

    // 카드 HTML 구성
    target.innerHTML = `
      <h4 style="font-weight:600; font-size:15px; margin-bottom:8px;">${data.title}</h4>
      <div style="display:flex; justify-content:center; align-items:center; gap:24px;">
        <a href="https://www.youtube.com/watch?v=${data.video_id}" target="_blank">
          <img src="${data.thumbnail_url}" width="240" style="border-radius:8px;">
        </a>
        <div style="display:flex;justify-content:center;align-items:center;">
          <canvas id="wcCanvas" width="260" height="260" style="margin-top:12px;"></canvas>
        </div>
      </div>
      <p style="font-size:13px;color:#555;margin-top:8px; text-align:center;">${data.summary}</p>
    `;

    // --- ✅ DOM이 갱신된 후 실행되도록 보장 ---
    await new Promise(r => setTimeout(r, 200));

    const canvas = document.getElementById("wcCanvas");
    if (!canvas) {
      console.error("❌ wcCanvas 엘리먼트를 찾을 수 없습니다");
      return;
    }

    const list = data.wordcloud?.map(w => [w.text, w.count]) || [["데이터없음", 1]];
    WordCloud(canvas, {
      list,
      gridSize: 8,
      weightFactor: 2,
      color: "random-dark",
      backgroundColor: "#fff",
      rotateRatio: 0.2,
      fontFamily: "Noto Sans KR",
      shuffle: true
    });

    console.log("✅ 워드클라우드 생성 완료");
  } catch (err) {
    console.error("❌ opinion-widget.js error:", err);
    target.innerHTML = "<p style='text-align:center;color:#999;'>데이터 로드 실패</p>";
  }
});
