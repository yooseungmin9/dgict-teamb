// /static/index.js
// 입문자용 주석: 로딩 확인 로그 + API 실패 시 더미데이터로라도 차트 그리기
(function(){
  console.log("[index.js] loaded");              // ✅ 이 로그가 콘솔에 떠야 JS가 로드된 것
  const card = document.getElementById("sentiment-card");
  if(!card){ console.error("sentiment-card 없음"); return; }

  const API = card.dataset.api || "/api/sentiment/line";
  const $status = document.getElementById("sentiment-status");
  const ctx = document.getElementById("sentiment-chart").getContext("2d");

  const $btnCount = document.getElementById("btn-mode-count");
  const $btnRatio = document.getElementById("btn-mode-ratio");
  const $btnDay   = document.getElementById("btn-g-day");
  const $btnWeek  = document.getElementById("btn-g-week");
  const $btnMonth = document.getElementById("btn-g-month");

  let state = { mode:"count", group:"day", raw:[] };
  let chart;

  const toWeekKey = (d)=>{ const dt=new Date(d+"T00:00:00"); const mon=new Date(dt);
    mon.setDate(dt.getDate()-((dt.getDay()+6)%7)); const y=mon.getFullYear(), jan1=new Date(y,0,1);
    const w=Math.floor(((mon-jan1)/86400000+((jan1.getDay()+6)%7))/7)+1; return `${y}-W${String(w).padStart(2,"0")}`; };
  const toMonthKey = (d)=>d.slice(0,7);
  function groupRecords(rs,g){ if(g==="day") return rs; const acc={};
    for(const r of rs){ const k=g==="week"?toWeekKey(r.date):toMonthKey(r.date);
      acc[k]??={date:k,"부정":0,"중립":0,"긍정":0};
      acc[k]["부정"]+=+r["부정"]||0; acc[k]["중립"]+=+r["중립"]||0; acc[k]["긍정"]+=+r["긍정"]||0; }
    return Object.values(acc).sort((a,b)=>a.date.localeCompare(b.date));
  }
  function makeOptions(isRatio){ return {
    responsive:true, maintainAspectRatio:false,
    scales:{ x:{stacked:true,grid:{display:false}},
             y:{stacked:true,beginAtZero:true,ticks:{callback:v=>isRatio?`${v}%`:v}} },
    plugins:{legend:{position:"top"}}
  };}

  function render(){
    const isR = state.mode==="ratio";
    const rows = groupRecords(state.raw, state.group);
    const labels = rows.map(d=>d.date);
    let neg = rows.map(d=>+d["부정"]||0), neu = rows.map(d=>+d["중립"]||0), pos = rows.map(d=>+d["긍정"]||0);
    if(isR){
      const N=[],E=[],P=[];
      for(let i=0;i<labels.length;i++){
        const t=(neg[i]+neu[i]+pos[i])||1;
        N.push(+((neg[i]/t*100).toFixed(2)));
        E.push(+((neu[i]/t*100).toFixed(2)));
        P.push(+((pos[i]/t*100).toFixed(2)));
      }
      neg=N; neu=E; pos=P;
    }
    if(chart) chart.destroy();
    chart = new Chart(ctx, {
      type:"bar",
      data:{ labels, datasets:[
        {label:"부정(<0)", data:neg, stack:"s"},
        {label:"중립(=0)", data:neu, stack:"s"},
        {label:"긍정(>0)", data:pos, stack:"s"},
      ]},
      options: makeOptions(isR)
    });
    $status.textContent = `표시: ${state.group} / ${isR?"비율(%)":"건수"}`;
  }

  async function load(){
    try{
      $status.textContent = "로딩중...";         // ✅ 이 문구가 떠야 JS가 실행 중
      const res = await fetch(`${API}?mode=${state.mode}`);
      if(!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if(!Array.isArray(data)) throw new Error("API 응답이 배열이 아님");

      // ✅ 합계가 0인 날짜는 숨김
      const filtered = data.filter(r => ((+r['부정']||0) + (+r['중립']||0) + (+r['긍정']||0)) > 0);

      // ✅ 날짜 오름차순 정렬(문자열 'YYYY-MM-DD' 기준)
      filtered.sort((a,b) => String(a.date).localeCompare(String(b.date)));

      state.raw = filtered;
      console.log("[index.js] rows(after filter):", state.raw.length);
      render();

    }catch(e){
      console.error("[index.js] API 실패:", e);
      $status.textContent = "로딩 오류 (더미 표시)";
      // 더미 2일치라도 표시해서 화면이 비어보이지 않게
      const today = new Date(), d1 = new Date(today); d1.setDate(today.getDate()-1);
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
})();
