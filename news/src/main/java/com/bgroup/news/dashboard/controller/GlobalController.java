// ③ (선택) CORS 회피용 Spring 프록시 — 같은 오리진으로 호출하고 싶을 때
// 경로: src/main/java/.../controller/NewsProxyController.java
// 포인트: 프런트에선 data-api-base="/api" 로 바꾸고 "/api/naver/econ" 호출
package com.bgroup.news.dashboard.controller;

import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

@RestController
@RequestMapping("/api")
public class GlobalController {
    private static final String FASTAPI = "http://127.0.0.1:8010";
    private final RestTemplate http = new RestTemplate();

    @GetMapping("/naver/econ")
    public ResponseEntity<String> proxy(@RequestParam(defaultValue="미국 경제") String q,
                                        @RequestParam(defaultValue="5") int n,
                                        @RequestParam(defaultValue="date") String sort){
        try {
            String url = String.format("%s/naver/econ?q=%s&n=%d&sort=%s",
                    FASTAPI,
                    URLEncoder.encode(q, StandardCharsets.UTF_8.toString()),
                    n,
                    URLEncoder.encode(sort, StandardCharsets.UTF_8.toString()));
            ResponseEntity<String> resp = http.getForEntity(url, String.class);
            return ResponseEntity.status(resp.getStatusCode()).body(resp.getBody());
        } catch (Exception e){
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY).body("{\"error\":\"proxy failed\"}");
        }
    }
}