package com.bgroup.news.search.controller;

import com.bgroup.news.recommend.dto.BookResponse;
import com.bgroup.news.recommend.dto.YoutubeResponse;
import com.bgroup.news.search.domain.NewsDoc;
import com.bgroup.news.search.repository.NewsRepository;
import com.bgroup.news.search.service.SearchService;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/search")
@RequiredArgsConstructor
public class SearchApiController {

    private final SearchService searchService;
    private final NewsRepository newsRepo;

    // 뉴스: 페이지네이션
    @GetMapping("/news")
    public ResponseEntity<NewsPage> news(
            @RequestParam String q,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "5") int size
    ){
        Page<NewsDoc> p = searchService.searchNewsPage(q, page, size);
        return ResponseEntity.ok(new NewsPage(
                p.getContent(),
                p.getNumber(),
                p.getTotalPages(),
                p.hasNext()
        ));
    }

    @GetMapping("/news/{id}")
    public ResponseEntity<NewsDoc> getNewsById(@PathVariable String id) {
        return newsRepo.findById(id)   // 주입되어 있다면 그대로 사용, 없으면 서비스 통해 조회
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    // 서적: 페이지네이션
    @GetMapping("/books")
    public ResponseEntity<BookPage> books(
            @RequestParam String q,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "5") int size
    ){
        Page<BookResponse> p = searchService.searchBooksPage(q, page, size);
        return ResponseEntity.ok(new BookPage(
                p.getContent(),
                p.getNumber(),
                p.getTotalPages(),
                p.hasNext()
        ));
    }

    // 유튜브: nextPageToken 기반 (FastAPI가 token을 내려줌)
    @GetMapping("/videos")
    public ResponseEntity<VideoPage> videos(
            @RequestParam String q,
            @RequestParam(defaultValue = "") String pageToken, // 빈 토큰=첫 페이지
            @RequestParam(defaultValue = "6") int size
    ){
        YoutubeResponse res = searchService.searchYoutubePage(q, size, pageToken);
        String next = (res != null) ? res.getNextPageToken() : null;
        List<YoutubeResponse.Item> items = (res != null) ? res.getItems() : List.of();
        return ResponseEntity.ok(new VideoPage(items, next, next != null && !next.isBlank()));
    }

    // --- DTOs ---
    public record NewsPage(List<NewsDoc> items, int page, int totalPages, boolean hasNext) {}
    public record BookPage(List<BookResponse> items, int page, int totalPages, boolean hasNext) {}
    public record VideoPage(List<YoutubeResponse.Item> items, String nextPageToken, boolean hasNext) {}
}