// public/js/chat.js — 음성+텍스트 챗봇 JS (실시간 인식 + 서버 업로드 폴백 + 무음자동전사)

// (1) 서버 엔드포인트
const CHAT_URL  = "/api/chat";
const RESET_URL = "/api/reset";
const STT_URL   = "/api/stt";   // Spring → FastAPI(/stt)
const TTS_URL   = "/api/tts";   // (미사용: 브라우저 TTS 사용 중, 필요시 전환)
const TIMEOUT_MS = 180000;

// ====== 무음 자동 전사 설정 ======
const SILENCE_LIMIT_MS   = 5000;   // 무음 지속 시간 임계값 (ms)
const SILENCE_THRESHOLD  = 0.02;   // 무음 판단 임계값(0~1). 마이크가 약하면 0.01로
const MONITOR_INTERVAL   = 200;    // 볼륨 체크 주기(ms)

// (2) DOM 요소
const chatEl      = document.getElementById("chat");
const formEl      = document.getElementById("chatForm");
const inputEl     = document.getElementById("messageInput");
const sendBtn     = document.getElementById("sendBtn");
const resetBtn    = document.getElementById("resetBtn");

const sttStartBtn = document.getElementById("sttStartBtn");
const sttStopBtn  = document.getElementById("sttStopBtn");
const langSelect  = document.getElementById("langSelect");
const recStatusEl = document.getElementById("recStatus");

const ttsBtn      = document.getElementById("ttsBtn");
const ttsAudio    = document.getElementById("ttsAudio"); // 현재 미사용(브라우저 TTS)

// (3) 상태
let mediaRecorder = null;
let audioChunks   = [];
let rec = null;               // Web SpeechRecognition
let interimBuf = "";          // Web Speech 확정 결과 누적

// 무음 감지용 (폴백 경로에서만 사용)
let audioCtx = null, micSource = null, analyser = null, monitorTimer = null, silenceMs = 0;

// (4) 유틸
const escapeHtml = (s)=>String(s||"").replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
const scrollToBottom = ()=>{ chatEl.scrollTop = chatEl.scrollHeight; };
const mdSafe = (text)=> escapeHtml(text).replace(/^-\s/gm,"• ").replace(/\n/g,"<br>");
const setRecStatus = (t)=>{ if(recStatusEl) recStatusEl.textContent = t; };

// ========== ★ 여기서부터 '엔터=전송 / 쉬프트+엔터=줄바꿈' 전용 핸들러 (중복 선언 제거) ==========
inputEl.addEventListener("keydown", function (e) {
  // IME(한글 입력) 조합 중에는 엔터 입력 무시
  if (e.isComposing) return;

  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();        // 기본 줄바꿈 막기
    formEl.requestSubmit();    // submit 핸들러로 위임
  }
  // Shift+Enter는 기본 동작(줄바꿈) 유지
});
// ============================================================================================

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

// (5) 채팅 전송
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
    const to = setTimeout(()=>ctrl.abort("timeout"), TIMEOUT_MS);

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

// (6) 초기화
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

// (7) FAQ 버튼 자동 입력
document.querySelectorAll(".faq-item")?.forEach(btn=>{
  btn.addEventListener("click", ()=>{
    inputEl.value = btn.dataset.question || btn.textContent.trim();
    formEl.requestSubmit();
  });
});

// ======== Web Speech API (실시간 인식) — HTTPS/localhost, Chrome/Edge 권장 ========
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

// ======== 무음 감지(폴백 경로) ========
function startSilenceMonitor(stream){
  stopSilenceMonitor(); // 중복 방지
  audioCtx   = new (window.AudioContext || window.webkitAudioContext)();
  micSource  = audioCtx.createMediaStreamSource(stream);
  analyser   = audioCtx.createAnalyser();
  analyser.fftSize = 2048;
  micSource.connect(analyser);

  const buf = new Uint8Array(analyser.fftSize);
  silenceMs = 0;

  monitorTimer = setInterval(()=>{
    analyser.getByteTimeDomainData(buf);
    let sum = 0;
    for (let i=0;i<buf.length;i++){
      const v = (buf[i]-128)/128; // -1..1
      sum += Math.abs(v);
    }
    const avg = sum / buf.length; // 0..1
    if (avg < SILENCE_THRESHOLD){
      silenceMs += MONITOR_INTERVAL;
      setRecStatus(`무음 감지… ${Math.max(0, Math.ceil((SILENCE_LIMIT_MS - silenceMs)/1000))}초 후 전사`);
      if (silenceMs >= SILENCE_LIMIT_MS) {
        stopAndUpload(); // 자동 정지+업로드
      }
    } else {
      silenceMs = 0;
      setRecStatus("녹음 중…");
    }
  }, MONITOR_INTERVAL);
}
function stopSilenceMonitor(){
  if (monitorTimer){ clearInterval(monitorTimer); monitorTimer = null; }
  try { if (audioCtx && audioCtx.state !== "closed") audioCtx.close(); } catch {}
  analyser=null; micSource=null; audioCtx=null;
}

// ======== 폴백 경로: 정지 후 업로드 ========
async function stopAndUpload(){
  // Web Speech 중이면 여기 안 오지만 안전 가드
  if (rec && typeof rec.stop === "function") {
    try { rec.stop(); } catch {}
  }
  if (!mediaRecorder || mediaRecorder.state === "inactive") return;

  sttStopBtn.disabled = true;
  setRecStatus("전송 중…");
  stopSilenceMonitor();

  mediaRecorder.stop();
  mediaRecorder.onstop = async ()=>{
    try{
      const mime = mediaRecorder.mimeType || "audio/webm";
      const ext  = mime.includes("ogg") ? "ogg" : mime.includes("mp4") ? "mp4" : "webm";
      const blob = new Blob(audioChunks, { type: mime });

      // 마이크 트랙 해제
      mediaRecorder.stream?.getTracks()?.forEach(t=>t.stop());

      const fd = new FormData();
      fd.append("audio_file", blob, `speech.${ext}`);

      const lang = (langSelect?.value || "ko-KR");
      const res = await fetch(`${STT_URL}?lang=${encodeURIComponent(lang)}`, { method:"POST", body: fd });
      const data = await res.json();

      if (data?.text){
        inputEl.value = data.text;
        bubbleAI("📝 인식(자동 전사): " + escapeHtml(data.text));
      } else {
        bubbleAI("STT 오류: " + escapeHtml(data?.error || "응답 없음"));
      }
    }catch(err){
      bubbleAI("STT 전송 실패: " + (err?.message || err));
    }finally{
      sttStartBtn.disabled = false;
      sttStopBtn.disabled  = true;
      mediaRecorder = null;
      audioChunks = [];
      setRecStatus("대기");
    }
  };
}

// (8) 녹음 시작 — 브라우저 실시간 인식 우선, 불가 시 서버 업로드 폴백(+무음자동전사)
sttStartBtn?.addEventListener("click", async ()=>{
  try{
    await navigator.mediaDevices.getUserMedia({ audio:true }); // 권한 확인

    // 8-1) 브라우저 실시간 인식 경로
    if (SpeechRecognition){
      rec = new SpeechRecognition();
      rec.continuous = true;
      rec.interimResults = true;
      rec.lang = (langSelect?.value || "ko-KR");

      interimBuf = "";
      rec.onresult = (e)=>{
        let tmp = "";
        for (let i=e.resultIndex; i<e.results.length; i++){
          const seg = e.results[i][0].transcript;
          if (e.results[i].isFinal) interimBuf += seg;
          else tmp += seg;
        }
        inputEl.value = (interimBuf + " " + tmp).trim(); // ★ 실시간 채움
      };
      rec.onerror = (e)=> bubbleAI("브라우저 인식 오류: " + (e.error || e.message || e));
      rec.onend = ()=>{
        sttStartBtn.disabled = false;
        sttStopBtn.disabled  = true;
        setRecStatus("대기");
      };
      rec.start();

      sttStartBtn.disabled = true;
      sttStopBtn.disabled  = false;
      setRecStatus("듣는 중…");
      bubbleAI("🎤️ 실시간 음성 인식을 시작합니다.");
      return; // 실시간 사용 시 여기서 종료
    }

    // 8-2) 폴백: 서버 업로드 (MediaRecorder) + 무음 자동 전사
    const stream = await navigator.mediaDevices.getUserMedia({ audio:true });

    let mime = "";
    if (MediaRecorder.isTypeSupported("audio/webm")) mime = "audio/webm";
    else if (MediaRecorder.isTypeSupported("audio/ogg")) mime = "audio/ogg";
    else if (MediaRecorder.isTypeSupported("audio/mp4")) mime = "audio/mp4";

    mediaRecorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    audioChunks = [];
    mediaRecorder.ondataavailable = e => { if (e.data && e.data.size>0) audioChunks.push(e.data); };
    mediaRecorder.onerror = e => bubbleAI("녹음 에러: " + (e?.error?.message || e.message || e));
    mediaRecorder.start(300); // chunk 주기 수집

    // 무음 모니터 시작
    startSilenceMonitor(stream);

    sttStartBtn.disabled = true;
    sttStopBtn.disabled  = false;
    setRecStatus("녹음 중(서버 업로드)...");
    bubbleAI("🎤️ 녹음 시작! **말을 멈추면 5초 뒤 자동 전사**합니다.");
  }catch(err){
    bubbleAI("마이크 접근 실패: " + (err?.message || err));
  }
});

// (9) 녹음 정지 — 실시간은 stop, 폴백은 stopAndUpload
sttStopBtn?.addEventListener("click", async ()=>{
  // 실시간 인식 사용 중이면 중지
  if (rec && typeof rec.stop === "function") {
    try { rec.stop(); } catch {}
    sttStartBtn.disabled = false;
    sttStopBtn.disabled  = true;
    setRecStatus("대기");
    bubbleAI("📝 인식 완료.");
    rec = null;
    return;
  }
  // 폴백 업로드
  await stopAndUpload();
});

// 서버 TTS(mp3) 가져와서 <audio>로 재생하도록 교체
ttsBtn?.addEventListener("click", async ()=>{
  const lastBot = chatEl.querySelector(".bot-message:last-child .message-content");
  if(!lastBot) return alert("읽을 답변이 없습니다.");
  const text = (lastBot.innerText || lastBot.textContent || "").trim();
  if(!text) return alert("읽을 답변이 없습니다.");

  // 선택된 언어 가져오기 (없으면 ko-KR)
  const langSel = document.getElementById("langSelect");
  const lang = (langSel?.value || "ko-KR");

  try{
    const q = new URLSearchParams({
      text: text.slice(0, 2000),
      lang,                      // ko-KR / en-US ...
      voice: "ko-KR-Standard-B",  // 남성
      fmt: "MP3",
      rate: "1.0",
      pitch: "0.0"
    }).toString();

    const res = await fetch(`/api/tts?${q}`);
    const ct = (res.headers.get("content-type") || "").toLowerCase();

    if(res.ok && ct.includes("audio")){
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const audioEl = document.getElementById("ttsAudio");
      if (audioEl) {
        audioEl.src = url;
        await audioEl.play();
      } else {
        new Audio(url).play();
      }
    }else{
      const txt = await res.text().catch(()=> "");
      bubbleAI("TTS 오류: " + (txt || `HTTP ${res.status}`));
    }
  }catch(err){
    bubbleAI("TTS 호출 실패: " + (err?.message || err));
  }
});

/*
[간단 테스트]
1) 입력창에 문장 입력 → Enter → 전송(줄바꿈 없음)
2) 입력창에 문장 입력 → Shift+Enter → 줄바꿈 됨
3) 브라우저 콘솔에서 에러(Identifier 'inputEl' has already been declared)가 없어야 정상
*/