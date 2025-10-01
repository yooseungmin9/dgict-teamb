package com.bgroup.news.controller;

import com.bgroup.news.dto.BooksResponse;
import com.bgroup.news.dto.YoutubeResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import reactor.util.function.Tuple2;

import java.util.List;

@Controller
@RequiredArgsConstructor
public class DiscoverController {

    private final @Qualifier("booksClient") WebClient booksClient;     // :8003
    private final @Qualifier("youtubeClient") WebClient youtubeClient; // :8004

    @GetMapping("/pages/recommendations")
    public String discover(@RequestParam(defaultValue = "경제 강의") String q, Model model) {
        Mono<BooksResponse> booksMono = booksClient.get()
                .uri(uri -> uri.path("/books")
                .queryParam("q", "주식 초보")
                .queryParam("max_results", 10)   // ItemSearch에서 MaxResults로 매핑
                .build())
                .retrieve()
                .bodyToMono(BooksResponse.class);

        Mono<YoutubeResponse> ytMono = youtubeClient.get()
                .uri(uri -> uri.path("/youtube/search")
                        .queryParam("q", q)
                        .queryParam("max_results", 6)
                        .build())
                .retrieve()
                .bodyToMono(YoutubeResponse.class);

        Tuple2<BooksResponse, YoutubeResponse> tuple = Mono.zip(booksMono, ytMono).block();

        var books = (tuple != null && tuple.getT1() != null && tuple.getT1().getItems() != null)
                ? tuple.getT1().getItems() : List.of();

        var videos = (tuple != null && tuple.getT2() != null && tuple.getT2().getItems() != null)
                ? tuple.getT2().getItems() : List.of();

        model.addAttribute("books", books);
        model.addAttribute("videos", videos);
        model.addAttribute("query", q);
        return "pages/recommendations";
    }
}
