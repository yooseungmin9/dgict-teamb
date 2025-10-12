// 입문자용 주석: 로딩 확인 로그 + API 실패 시 더미데이터로라도 차트 그리기

(function(){
  console.log("[sentiment.js] loaded");
  const card = document.getElementById("sentiment-card");
  if(!card){ console.error("sentiment-card 없음"); return; }

  // ✅ API 경로
  const API = card.dataset.api || "http://localhost:8007/sentiment/line";
  const KEYWORDS_API = "http://localhost:8007/keywords/top";

  const $status = document.getElementById("sentiment-status");
  const ctx = document.getElementById("sentiment-chart").getContext("2d");

  const $btnCount = document.getElementById("btn-mode-count");
  const $btnRatio = document.getElementById("btn-mode-ratio");
  const $btnDay   = document.getElementById("btn-g-day");
  const $btnWeek  = document.getElementById("btn-g-week");
  const $btnMonth = document.getElementById("btn-g-month");

  let state = { mode:"count", group:"day", raw:[] };
  let chart;

  const toWeekKey = (d)=>{
    const dt=new Date(d+"T00:00:00");
    const mon=new Date(dt);
    mon.setDate(dt.getDate()-((dt.getDay()+6)%7));
    const y=mon.getFullYear(), jan1=new Date(y,0,1);
    const w=Math.floor(((mon-jan1)/86400000+((jan1.getDay()+6)%7))/7)+1;
    return `${y}-W${String(w).padStart(2,"0")}`;
  };

  const toMonthKey = (d)=>d.slice(0,7);

  function groupRecords(rs,g){
    if(g==="day") return rs;
    const acc={};
    for(const r of rs){
      const k=g==="week"?toWeekKey(r.date):toMonthKey(r.date);
      acc[k]??={date:k,"부정":0,"중립":0,"긍정":0};
      acc[k]["부정"]+=+r["부정"]||0;
      acc[k]["중립"]+=+r["중립"]||0;
      acc[k]["긍정"]+=+r["긍정"]||0;
    }
    return Object.values(acc).sort((a,b)=>a.date.localeCompare(b.date));
  }

  function makeBarOptions(isRatio){
    return {
      responsive:true,
      maintainAspectRatio:false,
      scales:{
        x:{stacked:true,grid:{display:false}},
        y:{stacked:true,beginAtZero:true,ticks:{callback:v=>isRatio?`${v}%`:v}}
      },
      plugins:{legend:{position:"top"}}
    };
  }

  function makePieOptions(){
    return {
      responsive:true,
      maintainAspectRatio:false,
      plugins:{
        legend:{position:"right"},
        tooltip:{
          callbacks:{
            label: function(context) {
              const label = context.label || '';
              const value = context.parsed || 0;
              const total = context.dataset.data.reduce((a, b) => a + b, 0);
              const percentage = ((value / total) * 100).toFixed(1);
              return `${label}: ${value}건 (${percentage}%)`;
            }
          }
        }
      }
    };
  }

  function render(){
    const isR = state.mode==="ratio";
    const rows = groupRecords(state.raw, state.group);

    if(chart) chart.destroy();

    if(isR){
      renderPieChart(rows);
    } else {
      renderBarChart(rows);
    }

    $status.textContent = `표시: ${state.group} / ${isR?"비율(파이차트)":"건수(막대차트)"}`;
  }

  function renderBarChart(rows){
    const labels = rows.map(d=>d.date);
    const neg = rows.map(d=>+d["부정"]||0);
    const neu = rows.map(d=>+d["중립"]||0);
    const pos = rows.map(d=>+d["긍정"]||0);

    chart = new Chart(ctx, {
      type:"bar",
      data:{
        labels,
        datasets:[
          {label:"부정(<0)", data:neg, stack:"s", backgroundColor:"rgba(235,16,0,0.9)"},
          {label:"중립(=0)", data:neu, stack:"s", backgroundColor:"rgba(201,203,207,0.9)"},
          {label:"긍정(>0)", data:pos, stack:"s", backgroundColor:"rgba(37,99,235,0.9)"},
        ]
      },
      options: {
        ...makeBarOptions(false),
        plugins:{
          datalabels:{ display:false } // 바 차트에서 숨김
        }
      }
    });
  }

  function renderPieChart(rows){
    let totalNeg = 0, totalNeu = 0, totalPos = 0;
    rows.forEach(r => {
      totalNeg += +r["부정"]||0;
      totalNeu += +r["중립"]||0;
      totalPos += +r["긍정"]||0;
    });

    const dataArr = [totalNeg, totalNeu, totalPos];

    chart = new Chart(ctx, {
      type:"pie",
      data:{
        labels: ["부정(<0)", "중립(=0)", "긍정(>0)"],
        datasets:[{
          data: dataArr,
          backgroundColor:[
            "rgba(235,16,0,0.9)",
            "rgba(201,203,207,0.9)",
            "rgba(37,99,235,0.9)"
          ],
          borderColor:[
            "rgba(235,16,0)",
            "rgba(201,203,207)",
            "rgba(37,99,235)"
          ],
          borderWidth: 2
        }]
      },
      options: {
        ...makePieOptions(),
        plugins: {
          ...makePieOptions().plugins,
          datalabels:{
            color:"#fff",
            font:{ weight:"bold" },
            formatter:(value,ctx)=>{
              const sum = ctx.chart.data.datasets[0].data.reduce((a,b)=>a+b,0);
              if(!sum) return "0%";
              return `${((value/sum)*100).toFixed(1)}%`;
            }
          }
        }
      },
      // 파이 차트에만 플러그인 적용
      plugins: [ChartDataLabels]
    });
  }

  async function loadKeywords(){
    try{
      const res = await fetch(`${KEYWORDS_API}?top_n=5`);
      if(!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      console.log("[sentiment.js] 키워드 데이터:", data);

      const $keywordsToday = document.getElementById("keywords-today");
      const $keywordsYesterday = document.getElementById("keywords-yesterday");

      if($keywordsToday && data.today){
        $keywordsToday.innerHTML = data.today
          .map(k => `<span class="keyword-badge">${k.keyword} (${k.count})</span>`)
          .join(" ");
      }
      if($keywordsYesterday && data.yesterday){
        $keywordsYesterday.innerHTML = data.yesterday
          .map(k => `<span class="keyword-badge">${k.keyword} (${k.count})</span>`)
          .join(" ");
      }
    }catch(e){
      console.error("[sentiment.js] 키워드 로딩 실패:", e);
    }
  }

  async function load(){
    try{
      $status.textContent = "로딩중...";
      console.log("[sentiment.js] API 호출:", API);

      const res = await fetch(`${API}?mode=${state.mode}`);
      if(!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      console.log("[sentiment.js] 응답 데이터:", data);

      if(!Array.isArray(data)) throw new Error("API 응답이 배열이 아님");

      const filtered = data.filter(r => ((+r['부정']||0) + (+r['중립']||0) + (+r['긍정']||0)) > 0);
      filtered.sort((a,b) => String(a.date).localeCompare(String(b.date)));

      state.raw = filtered;
      console.log("[sentiment.js] rows(after filter):", state.raw.length);
      render();

    }catch(e){
      console.error("[sentiment.js] API 실패:", e);
      $status.textContent = "로딩 오류 (더미 표시)";

      const today = new Date();
      const d1 = new Date(today);
      d1.setDate(today.getDate()-1);
      const fmt = (d)=>d.toISOString().slice(0,10);
      state.raw = [
        {date: fmt(d1), "부정": 120, "중립": 260, "긍정": 220},
        {date: fmt(today), "부정": 80, "중립": 200, "긍정": 300},
      ];
      render();
    }
  }

  $btnCount.addEventListener("click", ()=>{ state.mode="count"; load(); });
  $btnRatio.addEventListener("click", ()=>{ state.mode="ratio"; load(); });
  $btnDay  .addEventListener("click", ()=>{ state.group="day";   render(); });
  $btnWeek .addEventListener("click", ()=>{ state.group="week";  render(); });
  $btnMonth.addEventListener("click", ()=>{ state.group="month"; render(); });

  load();
  loadKeywords();
})();
