package com.bgroup.news.service;

import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.Map;

@Service
@RequiredArgsConstructor
public class ChatbotService {

    private final WebClient fastApiClient; // WebClientConfig에서 주입

    // 동기식 컨트롤러를 그대로 쓰려면 block(); 비동기로 가려면 Mono<String> 반환
    public String sendChat(Map<String, Object> body) {
        return fastApiClient.post()
                .uri("/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                // 실패 시 안전한 폴백(로그는 실제론 로깅 프레임워크로)
                .onErrorResume(e -> Mono.just("{\"error\":\"upstream_failed\"}"))
                .block();
    }

    public String reset() {
        return fastApiClient.post()
                .uri("/reset")
                .retrieve()
                .bodyToMono(String.class)
                .onErrorResume(e -> Mono.just("{\"ok\":false}"))
                .block();
    }
}
