// /src/main/resources/static/js/ticker.js (compact)
const strip=s=>(s||"").replace(/<[^>]*>/g,"").replace(/\s+/g," ").trim();
const decode=s=>{const t=document.createElement("textarea");t.innerHTML=s??"";return t.value;};

function buildItems(list){
  const frag=document.createDocumentFragment();
  list.forEach((it,i)=>{
    const item=document.createElement("span"); item.className="ticker-item";
    const a=document.createElement("a"); a.textContent=strip(decode(it.title)); a.href=it.link||"#"; a.target="_blank"; a.rel="noopener noreferrer";
    item.appendChild(a);
    if(i<list.length-1){ const sep=document.createElement("span"); sep.className="sep"; sep.textContent="·"; item.appendChild(sep); }
    frag.appendChild(item);
  });
  return frag;
}

function runTicker($wrap,$a,$b,speed=80,gap=64){
  let xA=0,xB=0,wA=$a.scrollWidth,wB=$b.scrollWidth,last=performance.now(),paused=false;
  xB=wA+gap;
  $wrap.addEventListener("mouseenter",()=>paused=true);
  $wrap.addEventListener("mouseleave",()=>paused=false);
  function loop(now){
    const dt=(now-last)/1000; last=now;
    if(!paused){
      const dx=speed*dt; xA-=dx; xB-=dx;
      if(xA<=-wA) xA=xB+wB+gap; if(xB<=-wB) xB=xA+wA+gap;
      $a.style.transform=`translateX(${xA|0}px)`; $b.style.transform=`translateX(${xB|0}px)`;
    }
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);

  let rid=null;
  function recalc(){
    if(rid){clearTimeout(rid); rid=null;}
    const minW=$wrap.clientWidth*2;
    const cloneTo=(el)=>el.appendChild(buildItems([...el.querySelectorAll(".ticker-item a")].map(a=>({title:a.textContent,link:a.href}))));
    while($a.scrollWidth<minW) cloneTo($a);
    while($b.scrollWidth<minW) cloneTo($b);
    wA=$a.scrollWidth; wB=$b.scrollWidth; xA=0; xB=wA+gap;
  }
  window.addEventListener("resize",()=>{ if(rid) clearTimeout(rid); rid=setTimeout(recalc,150); });
  recalc();
}

async function initTicker(){
  const $wrap=document.getElementById("news-ticker");
  const $a=document.getElementById("track-a");
  const $b=document.getElementById("track-b");
  if(!$wrap||!$a||!$b) return;

  const API_BASE=$wrap.dataset.apiBase||"/api";
  const Q=$wrap.dataset.q||"미국 경제";
  const N=+(($wrap.dataset.n)||"5");
  const SORT=$wrap.dataset.sort||"date";

  let started=false;
  const mount=(arts)=>{
    $a.innerHTML=""; $b.innerHTML="";
    $a.appendChild(buildItems(arts)); $b.appendChild(buildItems(arts));
    if(!started){ runTicker($wrap,$a,$b,80,64); started=true; }
  };

  const N_FETCH=Math.min(50,N*4);
  const url = `${API_BASE}/naver/econ?q=${encodeURIComponent(Q)}&n=${N_FETCH}&sort=${encodeURIComponent(SORT)}`;

  try{
    const r=await fetch(url,{cache:"no-store"});
    if(!r.ok) throw new Error(`HTTP ${r.status}`);
    const data=await r.json();
    const raw=Array.isArray(data.articles)?data.articles:[];
    const filtered = raw
      .map(it => ({ title: strip(decode(it.title)), link: it.link }))
      .filter((v,i,self) => self.findIndex(x => x.title === v.title) === i) // 중복 제거만
      .slice(0, N);
    if(!filtered.length) throw new Error("empty after filter");
    mount(filtered);
  }catch(e){ console.error("[ticker] load failed:",e); }
}

document.readyState==="loading"?document.addEventListener("DOMContentLoaded",initTicker):initTicker();