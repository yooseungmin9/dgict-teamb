package com.bgroup.news.search.service;

import com.bgroup.news.recommend.dto.BookResponse;
import com.bgroup.news.recommend.dto.YoutubeResponse;
import com.bgroup.news.recommend.dto.YoutubeResponse.Item;
import com.bgroup.news.recommend.repository.BookRepository;
import com.bgroup.news.search.domain.NewsDoc;
import com.bgroup.news.search.repository.NewsRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.*;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;
import java.util.*;
import java.util.regex.Pattern;

@Service
@RequiredArgsConstructor
public class SearchService {

    private final BookRepository bookRepo;
    private final NewsRepository newsRepo;
    private final WebClient youtubeClient;

    public List<BookResponse> searchBooks(String q, int size) {
        if (q == null || q.isBlank()) return List.of();
        String safe = Pattern.quote(q.trim());
        PageRequest pg = PageRequest.of(0, size, Sort.by(
                Sort.Order.desc("salesPoint"),
                Sort.Order.desc("pubDate")
        ));
        return bookRepo.searchByTitleOrAuthor(safe, pg).getContent();
    }

    public List<NewsDoc> searchNews(String q, int size) {
        if (q == null || q.isBlank()) return List.of();
        String safe = Pattern.quote(q.trim());
        PageRequest pg = PageRequest.of(0, size, Sort.by(Sort.Order.desc("publishedAt")));
        return newsRepo.searchFulltext(safe, pg).getContent();
    }

    public List<YoutubeResponse.Item> searchYoutube(String q, int size) {
        YoutubeResponse r = searchYoutubePage(q, size, "");
        if (r == null || r.getItems() == null) return List.of();

        List<YoutubeResponse.Item> items = new ArrayList<>(r.getItems());
        items.sort(Comparator.comparingLong((YoutubeResponse.Item v) -> -YoutubeViewCount(v)));

        items = dedupeByVideoId(items);

        if (items.size() > size) items = items.subList(0, size);
        return items;
    }

    private static List<YoutubeResponse.Item> dedupeByVideoId(List<YoutubeResponse.Item> in){
        if (in == null) return List.of();
        Map<String, YoutubeResponse.Item> map = new LinkedHashMap<>();
        for (YoutubeResponse.Item it : in) {
            if (it == null) continue;
            String vid = it.getVideoId();
            if (vid == null || vid.isBlank()) continue;
            map.putIfAbsent(vid, it); // 먼저 온 것 유지
        }
        return new ArrayList<>(map.values());
    }

    private static long YoutubeViewCount(YoutubeResponse.Item v) {
        if (v == null || v.getStatistics() == null) return 0L;
        try { return Long.parseLong(v.getStatistics().getOrDefault("viewCount","0")); }
        catch (Exception e) { return 0L; }
    }

    public Page<NewsDoc> searchNewsPage(String q, int page, int size) {
        if (q == null || q.isBlank()) return Page.empty();
        String safe = Pattern.quote(q.trim());
        PageRequest pg = PageRequest.of(Math.max(page,0), size, Sort.by(Sort.Order.desc("publishedAt")));
        return newsRepo.searchFulltext(safe, pg);
    }

    public Page<BookResponse> searchBooksPage(String q, int page, int size) {
        if (q == null || q.isBlank()) return Page.empty();
        String safe = Pattern.quote(q.trim());
        PageRequest pg = PageRequest.of(Math.max(page,0), size, Sort.by(
                Sort.Order.desc("salesPoint"),
                Sort.Order.desc("pubDate")
        ));
        return bookRepo.searchByTitleOrAuthor(safe, pg);
    }

    public YoutubeResponse searchYoutubePage(String q, int size, String pageToken) {
        if (q == null || q.isBlank()) return new YoutubeResponse();
        try {
            YoutubeResponse res = youtubeClient.get()
                    .uri(uriBuilder -> uriBuilder.path("/youtube/search")
                            .queryParam("q", q.trim())
                            .queryParam("max_results", size)
                            .queryParamIfPresent("page_token",
                                    Optional.ofNullable(blankToNull(pageToken)))
                            .build())
                    .retrieve()
                    .bodyToMono(YoutubeResponse.class)
                    .timeout(Duration.ofSeconds(6))
                    .onErrorReturn(new YoutubeResponse())
                    .block();

            if (res != null && res.getItems() != null) {
                res.getItems().sort(Comparator.comparingLong((YoutubeResponse.Item v) -> -viewCount(v)));
                res.setItems(dedupeByVideoId(res.getItems()));
            }
            return res;
        } catch (Exception e) {
            return new YoutubeResponse();
        }
    }

    private static String blankToNull(String s){ return (s == null || s.isBlank()) ? null : s; }
    private static long viewCount(Item v) {
        if (v == null || v.getStatistics() == null) return 0L;
        try { return Long.parseLong(v.getStatistics().getOrDefault("viewCount","0")); }
        catch (Exception e) { return 0L; }
    }
}