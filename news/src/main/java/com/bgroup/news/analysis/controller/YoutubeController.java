package com.bgroup.news.analysis.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.util.UriComponentsBuilder;
import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class YoutubeController {

    private final WebClient webClient = WebClient.create("http://localhost:8008");

    @GetMapping("/videos")
    public Mono<ResponseEntity<String>> listVideos(
            @RequestParam(required = false) String category,
            @RequestParam(name = "sort_by", required = false) String sortBy) {

        return webClient.get()
                .uri(uriBuilder -> {
                    var u = uriBuilder.path("/videos");
                    if (category != null) u.queryParam("category", category);
                    if (sortBy != null) u.queryParam("sort_by", sortBy);
                    return u.build();
                })
                .retrieve()
                .toEntity(String.class);
    }

    @GetMapping("/videos/{videoId}")
    public Mono<ResponseEntity<String>> getVideoDetail(@PathVariable String videoId) {
        return webClient.get()
                .uri("/videos/{id}", videoId)
                .retrieve()
                .toEntity(String.class);
    }

    @GetMapping("/analysis/{videoId}")
    public Mono<ResponseEntity<String>> getAnalysis(
            @PathVariable String videoId,
            @RequestParam(required = false) Integer limit,
            @RequestParam(defaultValue = "100") int topn) {

        return webClient.get()
                .uri(uriBuilder -> uriBuilder.path("/analysis/{id}")
                        .queryParam("limit", limit)
                        .queryParam("topn", topn)
                        .build(videoId))
                .retrieve()
                .toEntity(String.class);
    }
}
