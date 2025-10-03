// /static/index.js
// 입문자용 주석: 로딩 확인 로그 + API 실패 시 더미데이터로라도 차트 그리기
(function(){
  console.log("[index.js] loaded");              // ✅ 이 로그가 콘솔에 떠야 JS가 로드된 것
  const card = document.getElementById("sentiment-card");
  if(!card){ console.error("sentiment-card 없음"); return; }

  const API = card.dataset.api || "http://127.0.0.1:8000/sentiment/line";
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
      state.raw = data;
      console.log("[index.js] rows:", state.raw.length);
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

(function () {
  const card = document.getElementById("kw-card");
  if (!card) return; // 다른 페이지 대비

  const API = card.dataset.api || "http://127.0.0.1:8000/keywords/top";
  const $status = document.getElementById("kw-status");
  const $today = document.getElementById("kw-today");
  const $yday  = document.getElementById("kw-yesterday");

  // li 한 줄 HTML 생성 (간단한 가로막대 포함)
  function makeItem(rank, kw, cnt, maxCnt){
    const width = maxCnt ? Math.round((cnt / maxCnt) * 100) : 0; // 0~100%
    const bar = `<div style="background:#e5e7eb;border-radius:6px;height:10px;overflow:hidden;">
                   <div style="height:10px;width:${width}%;background:#6366f1;"></div>
                 </div>`;
    return `
      <li style="display:grid; grid-template-columns:28px 1fr 56px; gap:8px; align-items:center; margin-bottom:8px;">
        <span style="font-weight:700;">${rank}</span>
        <div>
          <div style="font-size:14px; margin-bottom:4px;">${kw}</div>
          ${bar}
        </div>
        <span style="text-align:right; font-variant-numeric:tabular-nums;">${cnt}</span>
      </li>
    `;
  }

  function renderList($el, rows){
    $el.innerHTML = "";
    if (!rows || rows.length === 0){
      $el.innerHTML = `<li style="color:#999;">데이터 없음</li>`;
      return;
    }
    const maxCnt = Math.max(...rows.map(r=>r.count || 0), 0);
    rows.slice(0,3).forEach((r, i)=>{
      $el.insertAdjacentHTML("beforeend", makeItem(i+1, r.keyword, r.count, maxCnt));
    });
  }

  async function load(topN=3){
    try{
      $status.textContent = "로딩중...";
      const res = await fetch(`${API}?top_n=${topN}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json(); // { today:[{keyword,count}..], yesterday:[..] }
      renderList($today, data.today || []);
      renderList($yday,  data.yesterday || []);
      $status.textContent = "완료";
    }catch(e){
      console.error("[keywords] API 실패:", e);
      $status.textContent = "로딩 오류 (더미 표시)";
      // --- 더미 (간단 테스트용) ---
      const dummy = {
        today:     [{keyword:"인정",count:42},{keyword:"평가",count:31},{keyword:"제도",count:27}],
        yesterday: [{keyword:"주택",count:55},{keyword:"보증",count:21},{keyword:"공사",count:19}],
      };
      renderList($today, dummy.today);
      renderList($yday,  dummy.yesterday);
    }
  }

  // 초기 로드
  load(3);
})();
