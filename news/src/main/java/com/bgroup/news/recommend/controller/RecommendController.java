package com.bgroup.news.recommend.controller;

import com.bgroup.news.origin.dto.BookResponse;
import com.bgroup.news.origin.dto.YoutubeResponse;
import com.bgroup.news.origin.repository.BookRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.List;

@Controller
@RequiredArgsConstructor
public class RecommendController {

    private final BookRepository bookRepository;
    private final @Qualifier("youtubeClient") WebClient youtubeClient; // 유튜브는 계속 API

    @GetMapping("/pages/recommend")
    public String discover(@RequestParam(defaultValue = "경제 강의") String q, Model model) {

        // ✅ DB에서 책 가져오기
//        List<BookResponse> books = bookRepository.findTop10ByOrderByPubDateDesc();
        List<BookResponse> books = bookRepository.findTop10ByCategoryIdOrderByPubDateDesc(3065);
        model.addAttribute("books", books);

        // ✅ 유튜브는 여전히 API 호출
        Mono<YoutubeResponse> ytMono = youtubeClient.get()
                .uri(uri -> uri.path("/youtube/search")
                        .queryParam("q", q)
                        .queryParam("max_results", 3)
                        .build())
                .retrieve()
                .bodyToMono(YoutubeResponse.class);

        var videos = ytMono.block() != null ? ytMono.block().getItems() : List.of();

        model.addAttribute("books", books);
        model.addAttribute("videos", videos);
        model.addAttribute("query", q);
        return "pages/recommend";
    }
}

