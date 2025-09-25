package com.bgroup.news.chatbot_cont;

import org.springframework.http.*;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

@Controller
public class ChatController {

    private final RestTemplate restTemplate = new RestTemplate();
    private final String FASTAPI_URL = "http://127.0.0.1:8000";

    // 브라우저에서 http://localhost:8080/chat → chat.html 렌더링
    @GetMapping("/chat")
    public String chatPage() {
        return "/chat"; // src/main/resources/templates/chat.html
    }

    // 		/api/chat → FastAPI 프록시
    @PostMapping("/api/chat")
    @ResponseBody
    public ResponseEntity<String> proxyChat(@RequestBody Map<String, Object> body) {
		// 사용자가 보낸 요청을 FastAPI 서버로 다시 전달(forward)하기 위해 URL 구성
        String url = FASTAPI_URL + "/chat";
		
		// restTemplate.postForEntity()
		// → 다른 서버(FastAPI)로 HTTP POST 요청을 보내고,
		//   그 응답을 받아서 ResponseEntity 객체로 반환한다.
		// ResponseEntity = "응답 전체(상태코드 + 헤더 + 본문)를 직접 다룰 수 있는 만능 도구"
        return restTemplate.postForEntity(url, body, String.class);
    }

    // 		/api/reset → FastAPI 프록시
    @PostMapping("/api/reset")
    @ResponseBody
    public ResponseEntity<String> proxyReset() {
        String url = FASTAPI_URL + "/reset";
        return restTemplate.postForEntity(url, null, String.class);
    }
}
