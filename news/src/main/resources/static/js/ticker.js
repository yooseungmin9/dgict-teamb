// /src/main/resources/static/js/ticker.js
function stripTags(html){ return (html || "").replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim(); }
function decodeHtml(s){ const t=document.createElement("textarea"); t.innerHTML=s??""; return t.value; }

function buildItems(list){
  const frag=document.createDocumentFragment();
  list.forEach((it,idx)=>{
    const item=document.createElement("span"); item.className="ticker-item";
    const a=document.createElement("a");
    a.textContent=stripTags(decodeHtml(it.title));
    a.href=it.link||"#"; a.target="_blank"; a.rel="noopener noreferrer";
    item.appendChild(a);
    if(idx<list.length-1){
      const sep=document.createElement("span"); sep.className="sep"; sep.textContent="·";
      item.appendChild(sep);
    }
    frag.appendChild(item);
  });
  return frag;
}

// ---- 스크롤 엔진 ----
function runTicker($wrap, $a, $b, speed=80, gap=64){
  let xA = 0, xB = 0;
  let wA = $a.scrollWidth, wB = $b.scrollWidth;

  xA = 0;
  xB = wA + gap;

  let last = performance.now();
  let paused = false;

  $wrap.addEventListener('mouseenter', ()=> paused=true);
  $wrap.addEventListener('mouseleave', ()=> paused=false);

  function loop(now){
    const dt = (now - last) / 1000;
    last = now;
    if(!paused){
      const dx = speed * dt;
      xA -= dx; xB -= dx;
      if (xA <= -wA) xA = xB + wB + gap;
      if (xB <= -wB) xB = xA + wA + gap;
      $a.style.transform = `translateX(${Math.round(xA)}px)`;
      $b.style.transform = `translateX(${Math.round(xB)}px)`;
    }
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);

  // 리사이즈 보정
  let rid = null;
  function recalc(){
    if (rid) { clearTimeout(rid); rid = null; }
    const minWidth = $wrap.clientWidth * 2;
    while ($a.scrollWidth < minWidth) {
      $a.appendChild(buildItems(
        Array.from($a.querySelectorAll('.ticker-item a'))
          .map(a=>({title:a.textContent,link:a.href}))
      ));
    }
    while ($b.scrollWidth < minWidth) {
      $b.appendChild(buildItems(
        Array.from($b.querySelectorAll('.ticker-item a'))
          .map(a=>({title:a.textContent,link:a.href}))
      ));
    }
    wA = $a.scrollWidth;
    wB = $b.scrollWidth;
    xA = 0;
    xB = wA + gap;
  }
  window.addEventListener('resize', ()=>{
    if (rid) { clearTimeout(rid); }
    rid = setTimeout(recalc, 150);
  });
  recalc();
}

// ---- 데이터 로드 & 초기화 ----
async function initTicker(){
  const $wrap=document.getElementById("news-ticker");
  const $a=document.getElementById("track-a");
  const $b=document.getElementById("track-b");
  if(!$wrap||!$a||!$b){ return; }

  const API_BASE=$wrap.dataset.apiBase||"/api";
  const Q=$wrap.dataset.q||"일본 경제";
  const N=parseInt($wrap.dataset.n||"5",10);
  const SORT=$wrap.dataset.sort||"date";

  function mount(articles){
    $a.innerHTML=""; $b.innerHTML="";
    $a.appendChild(buildItems(articles));
    $b.appendChild(buildItems(articles));
  }

  async function load(){
    const url=`${API_BASE}/naver/econ?q=${encodeURIComponent(Q)}&n=${N}&sort=${encodeURIComponent(SORT)}`;
    try{
      const r=await fetch(url);
      if(!r.ok) throw new Error(`HTTP ${r.status}`);
      const data=await r.json();
      const list=Array.isArray(data.articles)?data.articles:[];
      if(!list.length) throw new Error("empty list");
      mount(list);
      // DOM 채운 뒤 엔진 시작
      runTicker($wrap, $a, $b, 80, 64);
    }catch(e){
      console.error("[ticker] load failed:", e);
    }
  }
  await load();
}

document.readyState==="loading"
  ? document.addEventListener("DOMContentLoaded", initTicker)
  : initTicker();
