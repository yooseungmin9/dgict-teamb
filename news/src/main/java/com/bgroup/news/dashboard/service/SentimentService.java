package com.bgroup.news.dashboard.service;

import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class SentimentService {
    @Qualifier("sentiClient")
    private final WebClient sentiClient;

    public Map<String, Object> getLine(String mode, int days) {
        return sentiClient.get()
                .uri(uri -> uri.path("/sentiment/line")
                        .queryParam("mode", mode)
                        .queryParam("days", days).build())
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String,Object>>() {})
                .timeout(Duration.ofSeconds(4))
                .onErrorReturn(Map.of(  // ★ 폴백
                        "ok", false,
                        "series", List.of(),
                        "message", "senti timeout"
                ))
                .block();
    }
}
