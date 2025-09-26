package com.bgroup.news.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

@Service
public class KeywordService {

    private final WebClient webClient;

    public KeywordService(WebClient.Builder builder,
                          @Value("${fastapi.base-url}") String baseUrl) {
        this.webClient = builder.baseUrl(baseUrl).build();
    }

    public Mono<String> fetchKeywords() {
        return webClient.get()
                .uri("/keywords")
                .retrieve()
                .bodyToMono(String.class);
    }
}
