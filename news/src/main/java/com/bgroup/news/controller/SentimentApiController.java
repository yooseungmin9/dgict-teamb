package com.bgroup.news.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.Duration;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/sentiment")
public class SentimentApiController {

    private final @Qualifier("sentiClient") WebClient sentiClient;

    @GetMapping(value = "/line", produces = MediaType.APPLICATION_JSON_VALUE)
    public Mono<String> getSentimentLine(
            @RequestParam(defaultValue = "count") String mode
    ) {
        return sentiClient.get()
                .uri(uri -> uri.path("/sentiment/line")
                        .queryParam("mode", mode)
                        .build())
                .retrieve()
                .bodyToMono(String.class)
                .timeout(Duration.ofSeconds(2))
                .onErrorReturn("{}"); // 실패 시 빈 JSON
    }
}
