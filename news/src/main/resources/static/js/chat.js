// static/js/chat.js
// (1) 서버 엔드포인트
const CHAT_URL  = "/api/chat";
const RESET_URL = "/api/reset";
const TIMEOUT_MS = 180000;

// (2) 필수 요소
const chatEl   = document.getElementById("chat");
const formEl   = document.getElementById("chatForm");
const inputEl  = document.getElementById("messageInput");
const sendBtn  = document.getElementById("sendBtn");
const resetBtn = document.getElementById("resetBtn");

// (3) 유틸
const escapeHtml = (s)=>String(s||"").replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
const scrollToBottom = ()=>{ chatEl.scrollTop = chatEl.scrollHeight; };

function bubbleUser(text){
  chatEl.insertAdjacentHTML("beforeend",
    `<div class="message user-message"><div class="message-content">${escapeHtml(text)}</div></div>`);
  scrollToBottom();
}
function bubbleAI(html){
  chatEl.insertAdjacentHTML("beforeend",
    `<div class="message bot-message"><div class="message-content">${html}</div></div>`);
  scrollToBottom();
}
function bubbleTyping(){
  const id = "typing-" + (crypto?.randomUUID?.() || Math.random().toString(36).slice(2));
  chatEl.insertAdjacentHTML("beforeend",
    `<div id="${id}" class="message bot-message"><div class="message-content">입력 중...</div></div>`);
  scrollToBottom();
  return id;
}
function removeEl(id){ const el=document.getElementById(id); if(el) el.remove(); }
function mdSafe(text){ return escapeHtml(text).replace(/^-\s/gm,"• ").replace(/\n/g,"<br>"); }

// (4) 전송 핸들러
formEl?.addEventListener("submit", async (e)=>{
  e.preventDefault();
  const q = inputEl.value.trim();
  if(!q) return;
  bubbleUser(q);
  inputEl.value="";
  sendBtn.disabled = true;
  const typingId = bubbleTyping();

  try{
    const ctrl = new AbortController();
    const to = setTimeout(()=>ctrl.abort('timeout'), TIMEOUT_MS);

    const res = await fetch(CHAT_URL, {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ message: q }),
      signal: ctrl.signal
    });
    clearTimeout(to);

    if(!res.ok){ removeEl(typingId); return bubbleAI(`서버 오류(${res.status})`); }
    const data = await res.json();
    removeEl(typingId);
    bubbleAI(mdSafe(data.answer || "응답이 비었습니다."));
  }catch(err){
    removeEl(typingId);
    bubbleAI("요청 실패: " + (err?.message || err));
  }finally{
    sendBtn.disabled = false;
  }
});

// (5) 초기화 버튼
resetBtn?.addEventListener("click", async ()=>{
  resetBtn.disabled = true;
  try{
    const res = await fetch(RESET_URL, { method:"POST" });
    if(res.ok) bubbleAI("대화 기록을 초기화했습니다.");
    else bubbleAI("초기화 실패.");
  }catch{
    bubbleAI("초기화 요청 실패.");
  }finally{
    resetBtn.disabled = false;
  }
});

// (6) FAQ 버튼 자동 입력+전송(선택)
document.querySelectorAll(".faq-item")?.forEach(btn=>{
  btn.addEventListener("click", ()=>{
    inputEl.value = btn.dataset.question || btn.textContent.trim();
    formEl.requestSubmit();
  });
});