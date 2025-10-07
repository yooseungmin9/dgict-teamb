// src/main/java/com/bgroup/news/chatbot_cont/ChatController.java
// [핵심만] /api/tts 프록시: 이중 인코딩 제거(URI 템플릿), Java 8 호환 + 수신값 로그
package com.bgroup.news.chatbot.controller;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Controller;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.http.client.SimpleClientHttpRequestFactory;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Map;
import java.util.logging.Logger;

@Controller
public class ChatController {

    private static final Logger log = Logger.getLogger(ChatController.class.getName());

    @Value("${fastapi.url:http://localhost:8002}")
    private String FASTAPI_URL;

    private static RestTemplate createRestTemplate() {
        // 요청 팩토리 생성
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(5000); // 연결 타임아웃 (ms)
        factory.setReadTimeout(180000);  // 읽기 타임아웃 (ms)

        return new RestTemplate(factory);
    }

    private final RestTemplate rest = createRestTemplate();

//    @GetMapping("/chat") public String chatPage() { return "chat"; }
    @GetMapping("/pages/chat") public String chatPage() { return "pages/chat"; }

    @PostMapping("/api/chat") @ResponseBody
    public ResponseEntity<String> proxyChat(@RequestBody Map<String, Object> body) {
        try {
            return rest.postForEntity(FASTAPI_URL + "/chat", body, String.class);
        } catch (RestClientException e) {
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body("{\"answer\":\"게이트웨이 오류: FastAPI /chat 접속 실패\"}");
        }
    }

    @PostMapping("/api/reset") @ResponseBody
    public ResponseEntity<String> proxyReset() {
        try {
            return rest.postForEntity(FASTAPI_URL + "/reset", null, String.class);
        } catch (RestClientException e) {
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body("{\"message\":\"게이트웨이 오류: FastAPI /reset 접속 실패\"}");
        }
    }

    // ===== STT (변경 없음) =====
    @PostMapping(value = "/api/stt", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @ResponseBody
    public ResponseEntity<String> proxyStt(@RequestParam("audio_file") MultipartFile audioFile,
                                           @RequestParam(name = "lang", defaultValue = "Kor") String lang) {
        String url = FASTAPI_URL + "/api/stt?lang=" + lang;

        ByteArrayResource filePart = new ByteArrayResource(toBytes(audioFile)) {
            @Override public String getFilename() { return audioFile.getOriginalFilename(); }
        };
        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("audio_file", filePart);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);

        try {
            return rest.postForEntity(url, new HttpEntity<>(body, headers), String.class);
        } catch (RestClientException e) {
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body("{\"error\":\"게이트웨이 오류: FastAPI /api/stt 접속 실패\"}");
        }
    }

    // ===== TTS (→ FastAPI /api/tts, 이중 인코딩 방지) =====
    @GetMapping("/api/tts")
    public ResponseEntity<byte[]> proxyTts(@RequestParam Map<String, String> allParams) {
        try {
            // 0) 필수 파라미터 가드 + 수신값 로그(스프링 단계에서 '한글'이어야 정상)
            String text = (allParams.getOrDefault("text", "")).trim();
            if (text.isEmpty()) {
                return jsonError("{\"error\":\"Missing required query param: text\"}", HttpStatus.BAD_REQUEST);
            }
            log.info("[/api/tts] received text len=" + text.length() + " sample=" + text.substring(0, Math.min(20, text.length())));

            // 1) 템플릿 URL (RestTemplate가 단 한 번만 인코딩)
            String urlTpl = FASTAPI_URL
                    + "/api/tts"
                    + "?text={text}"
                    + "&lang={lang}"
                    + "&voice={voice}"
                    + "&fmt={fmt}"
                    + "&rate={rate}"
                    + "&pitch={pitch}";

            // 2) 기본값 보정
            String lang  = allParams.getOrDefault("lang",  "ko-KR");
            String voice = allParams.getOrDefault("voice", "ko-KR-Standard-B"); // 남성
            String fmt   = allParams.getOrDefault("fmt",   "MP3");
            String rate  = allParams.getOrDefault("rate",  "1.0");
            String pitch = allParams.getOrDefault("pitch", "0.0");

            // 3) 오디오/JSON 응답 허용
            HttpHeaders reqHdr = new HttpHeaders();
            reqHdr.setAccept(Arrays.asList(
                    MediaType.valueOf("audio/mpeg"),
                    MediaType.valueOf("audio/ogg"),
                    MediaType.valueOf("audio/wav"),
                    MediaType.APPLICATION_JSON
            ));

            ResponseEntity<byte[]> res = rest.exchange(
                    urlTpl, HttpMethod.GET, new HttpEntity<>(reqHdr), byte[].class,
                    text, lang, voice, fmt, rate, pitch
            );

            // 4) FastAPI 응답 그대로 전달
            HttpHeaders out = new HttpHeaders();
            MediaType ct = res.getHeaders().getContentType();
            out.setContentType(ct != null ? ct : MediaType.APPLICATION_OCTET_STREAM);
            String disp = res.getHeaders().getFirst("Content-Disposition");
            out.set("Content-Disposition", disp != null ? disp : "inline; filename=\"speech.bin\"");
            out.setCacheControl(CacheControl.noCache());

            return new ResponseEntity<>(res.getBody(), out, res.getStatusCode());

        } catch (HttpStatusCodeException e) {
            HttpHeaders out = new HttpHeaders();
            MediaType ct = e.getResponseHeaders() != null ? e.getResponseHeaders().getContentType() : null;
            out.setContentType(ct != null ? ct : MediaType.APPLICATION_JSON);
            out.setCacheControl(CacheControl.noCache());
            byte[] body = e.getResponseBodyAsByteArray();
            return new ResponseEntity<>(body != null ? body : new byte[0], out, e.getStatusCode());
        } catch (RestClientException e) {
            return jsonError("{\"error\":\"Gateway error: cannot reach FastAPI /api/tts\"}", HttpStatus.BAD_GATEWAY);
        } catch (Exception e) {
            return jsonError("{\"error\":\"Unexpected error in /api/tts\"}", HttpStatus.INTERNAL_SERVER_ERROR);
        }
    }

    // ===== Util =====
    private byte[] toBytes(MultipartFile f) {
        try { return f.getBytes(); }
        catch (Exception e) { throw new RuntimeException("파일 읽기 실패", e); }
    }
    private ResponseEntity<byte[]> jsonError(String json, HttpStatus status) {
        HttpHeaders hdr = new HttpHeaders();
        hdr.setContentType(MediaType.APPLICATION_JSON);
        return new ResponseEntity<>(json.getBytes(StandardCharsets.UTF_8), hdr, status);
    }
}