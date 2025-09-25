package com.bgroup.news;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

@RestController
public class ApiController {

    private final WebClient webClient = WebClient.create("http://localhost:8001");

    @GetMapping("/keywords")
    public Mono<String> getKeywords() {
        return webClient.get()
                .uri("/keywords")
                .retrieve()
                .bodyToMono(String.class);
    }
}