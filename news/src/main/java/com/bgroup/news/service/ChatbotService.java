package com.bgroup.news.service;

import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.Map;

@Service
public class ChatbotService {

    private final WebClient fastApiClient;

    public ChatbotService(WebClient fastApiClient) {
        this.fastApiClient = fastApiClient;
    }

    /** 동기 호출 (컨트롤러에서 String으로 바로 반환할 때 사용) */
    public String sendChat(Map<String, Object> body) {
        return fastApiClient.post()
                .uri("/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                .onErrorResume(e -> Mono.just("{\"error\":\"upstream_failed\"}"))
                .block();
    }

    /** 동기 호출: 대화 초기화 */
    public String reset() {
        return fastApiClient.post()
                .uri("/reset")
                .retrieve()
                .bodyToMono(String.class)
                .onErrorResume(e -> Mono.just("{\"ok\":false}"))
                .block();
    }

    /* ---- 필요하면 비동기 버전도 제공 ---- */

    public Mono<String> sendChatAsync(Map<String, Object> body) {
        return fastApiClient.post()
                .uri("/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class);
    }

    public Mono<String> resetAsync() {
        return fastApiClient.post()
                .uri("/reset")
                .retrieve()
                .bodyToMono(String.class);
    }
}
