package com.bgroup.news.recommend.controller;

import com.bgroup.news.member.domain.MemberDoc;
import com.bgroup.news.recommend.dto.BookResponse;
import com.bgroup.news.recommend.dto.YoutubeResponse;
import com.bgroup.news.recommend.dto.YoutubeResponse.Item;
import com.bgroup.news.recommend.repository.BookRepository;
import com.bgroup.news.recommend.service.PreferenceKeywords;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.SessionAttribute;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;

@Controller
@RequestMapping("/pages") // 최종 URL: /pages/recommend
@RequiredArgsConstructor
public class RecommendController {

    private final BookRepository bookRepo;    // MongoRepository<BookResponse, String>
    private final WebClient youtubeClient;    // @Bean("youtubeClient")
    private final PreferenceKeywords pref;    // seed 생성 유틸

    @GetMapping(value = "/recommend", produces = MediaType.TEXT_HTML_VALUE)
    public String recommendPage(
            @SessionAttribute(value = "loginUser", required = false) MemberDoc me,
            Model model
    ) {
        final boolean loggedIn = (me != null);
        model.addAttribute("loggedIn", loggedIn);

        // ===== 기본(비로그인) 목록 =====
        final int BOOK_SIZE_DEFAULT   = 5; // ★ 서적 5개
        final int YOUTUBE_SIZE_DEFAULT= 6; // ★ 유튜브 6개

        List<BookResponse> defaultBooks  = getTrendingBooks(BOOK_SIZE_DEFAULT);      // 판매 + 신간 가중
        List<Item>         defaultVideos = getYoutubeForDefault(YOUTUBE_SIZE_DEFAULT); // 타임아웃↑ + 폴백 쿼리

        model.addAttribute("defaultBooks", defaultBooks);
        model.addAttribute("defaultVideos", defaultVideos);

        // ===== 개인화(로그인) 목록 =====
        if (loggedIn) {
            List<String> seeds = pref.buildSeeds(me, 3, 8); // 상위 3개 서브카테고리 → 키워드 최대 8개
            // 유튜브는 1차로 2개 seed만, 부족하면 5개까지 확장 (함수 내부 로직)
            List<BookResponse> personalBooks  = safeGet(() -> getPersonalBooks(seeds, BOOK_SIZE_DEFAULT, defaultBooks), defaultBooks);
            List<Item>         personalVideos = safeGet(() -> getYoutubePersonal(seeds, YOUTUBE_SIZE_DEFAULT, defaultVideos), defaultVideos);

            model.addAttribute("personalBooks", personalBooks);
            model.addAttribute("personalVideos", personalVideos);
            model.addAttribute("activeKeywords", String.join(", ", seeds));
        }

        return "pages/recommend";
    }

    // =========================================================
    // Books
    // =========================================================

    /**
     * 기본 서적(비로그인): "판매지수 + 신간가중"으로 트렌디 정렬
     * score = 0.65 * normalizeSales + 0.35 * freshness(0~1, 365일 선형감쇠)
     */
    private List<BookResponse> getTrendingBooks(int size) {
        // 넉넉한 풀: 판매지수/신간 각각 상위 200개씩
        Pageable bySales = PageRequest.of(0, 200, Sort.by(Sort.Order.desc("salesPoint")));
        Pageable byDate  = PageRequest.of(0, 200, Sort.by(Sort.Order.desc("pubDate")));

        List<BookResponse> pool = new ArrayList<>();
        pool.addAll(bookRepo.findAll(bySales).getContent());
        pool.addAll(bookRepo.findAll(byDate).getContent());

        // 중복 제거
        Map<String, BookResponse> unique = new LinkedHashMap<>();
        for (BookResponse b : pool) {
            if (b != null && b.getId() != null) unique.putIfAbsent(b.getId(), b);
        }
        List<BookResponse> uniqPool = new ArrayList<>(unique.values());

        // 스코어링
        Instant now = Instant.now();
        Map<String, Double> scored = new LinkedHashMap<>();
        for (BookResponse b : uniqPool) {
            double s = 0.65 * normalizeSales(b.getSalesPoint())
                    + 0.35 * freshnessScore(b.getPubDate(), now);
            if (s > 0) scored.put(b.getId(), s);
        }

        // 정렬 후 상위 N개
        List<String> topIds = scored.entrySet().stream()
                .sorted(Map.Entry.<String, Double>comparingByValue().reversed())
                .limit(size)
                .map(Map.Entry::getKey)
                .toList();

        Map<String, BookResponse> idx = uniqPool.stream()
                .collect(Collectors.toMap(BookResponse::getId, x -> x));
        List<BookResponse> result = new ArrayList<>();
        for (String id : topIds) {
            BookResponse b = idx.get(id);
            if (b != null) result.add(b);
        }

        // 부족하면 판매지수 상위로 채우기
        if (result.size() < size) {
            List<BookResponse> best = bookRepo.findAll(bySales).getContent();
            for (BookResponse b : best) {
                if (result.size() >= size) break;
                if (result.stream().noneMatch(x -> Objects.equals(x.getId(), b.getId()))) {
                    result.add(b);
                }
            }
        }
        return result;
    }

    /**
     * 개인화 도서(로그인): seeds로 제목/저자 매칭 + 신간/판매 가중치
     * score = 0.60*match + 0.25*fresh + 0.15*sales
     */
    private List<BookResponse> getPersonalBooks(List<String> seeds, int size, List<BookResponse> fallback) {
        if (seeds == null || seeds.isEmpty()) return fallback;

        Pageable poolPg = PageRequest.of(0, Math.max(size * 5, 60), Sort.by(Sort.Order.desc("pubDate")));
        List<BookResponse> pool = bookRepo.findAll(poolPg).getContent();

        Instant now = Instant.now();
        Map<String, Double> scored = new LinkedHashMap<>();
        for (BookResponse b : pool) {
            double match = keywordMatchScore(b, seeds);
            double fresh = freshnessScore(b.getPubDate(), now);
            double sales = normalizeSales(b.getSalesPoint());
            double score = 0.60 * match + 0.25 * fresh + 0.15 * sales;
            if (score > 0) scored.put(b.getId(), score);
        }
        if (scored.isEmpty()) return fallback;

        List<String> topIds = scored.entrySet().stream()
                .sorted(Map.Entry.<String, Double>comparingByValue().reversed())
                .limit(size)
                .map(Map.Entry::getKey)
                .toList();

        Map<String, BookResponse> idx = pool.stream()
                .collect(Collectors.toMap(BookResponse::getId, x -> x));
        List<BookResponse> ranked = new ArrayList<>();
        for (String id : topIds) {
            BookResponse b = idx.get(id);
            if (b != null) ranked.add(b);
        }

        if (ranked.size() < size) {
            List<BookResponse> best = getTrendingBooks(size); // 기본 기준으로 채움
            for (BookResponse b : best) {
                if (ranked.size() >= size) break;
                if (ranked.stream().noneMatch(x -> Objects.equals(x.getId(), b.getId()))) {
                    ranked.add(b);
                }
            }
        }
        return ranked;
    }

    private static double keywordMatchScore(BookResponse b, List<String> seeds) {
        if (b == null || seeds == null || seeds.isEmpty()) return 0;
        String title  = safeLower(b.getTitle());
        String author = safeLower(b.getAuthor());
        long hit = seeds.stream()
                .map(RecommendController::safeLower)
                .filter(kw -> title.contains(kw) || author.contains(kw))
                .count();
        return Math.min(1.0, hit / Math.max(1.0, seeds.size() / 2.0));
    }

    private static double freshnessScore(Instant pubDate, Instant now) {
        if (pubDate == null) return 0.2;
        long days = Math.max(1, (now.toEpochMilli() - pubDate.toEpochMilli()) / (1000L * 60 * 60 * 24));
        double v = 1.0 - Math.min(1.0, days / 365.0);
        return Math.max(0.0, v);
    }

    private static double normalizeSales(Integer salesPoint) {
        if (salesPoint == null) return 0.0;
        double v = Math.min(100_000, Math.max(0, salesPoint)); // 상한 100k 가정
        return v / 100_000.0;
    }

    // =========================================================
    // YouTube
    // =========================================================

    /** 기본(비로그인) 전용: 타임아웃 길게 + 폴백 쿼리 */
    private List<Item> getYoutubeForDefault(int max) {
        List<Item> r1 = getYoutubeByQuerySortedWithTimeout("경제 강의", max, 8);
        if (!r1.isEmpty()) return r1;

        List<Item> r2 = getYoutubeByQuerySortedWithTimeout("경제 입문 강의", max, 8);
        if (!r2.isEmpty()) return r2;

        return getYoutubeByQuerySortedWithTimeout("재테크 강의", max, 8);
    }

    /**
     * 개인화 유튜브: 점진적 확장 + 타임아웃 완화 + 폴백
     * - 1차: 상위 2개 seed, per-seed 5개, timeout 5s
     * - 부족하면 2차: 상위 5개 seed, per-seed 4개, timeout 6s
     * - 그래도 부족하면 기본 추천으로 폴백
     */
    private List<Item> getYoutubePersonal(List<String> seeds, int max, List<Item> fallback) {
        if (seeds == null || seeds.isEmpty()) return fallback;

        // 1) 1차: 상위 2개 seed
        List<String> s1 = seeds.size() > 2 ? seeds.subList(0, 2) : seeds;
        List<Item> list = mergeYoutubeBySeeds(s1, max, 5 /*perSeedMax*/, 5 /*timeoutSec*/);

        // 2) 결과가 너무 적으면: 상위 5개까지 확장
        if (list.size() < Math.max(2, max / 2) && seeds.size() > s1.size()) {
            int to = Math.min(5, seeds.size()); // 최대 5개 seed
            List<String> s2 = seeds.subList(0, to);
            list = mergeYoutubeBySeeds(s2, max, 4 /*perSeedMax*/, 6 /*timeoutSec*/);
        }

        // 3) 그래도 부족하면: 기본 추천으로 폴백
        if (list.isEmpty()) {
            List<Item> def = getYoutubeForDefault(max);
            return def.isEmpty() ? fallback : def;
        }
        return list;
    }

    /** 여러 seed를 합쳐서 videoId 중복 제거 후 조회수순 정렬 */
    private List<Item> mergeYoutubeBySeeds(List<String> seeds, int max, int perSeedMax, int timeoutSec) {
        List<Item> merged = new ArrayList<>();
        for (String s : seeds) {
            merged.addAll(getYoutubeByQuerySortedWithTimeout(s, Math.min(perSeedMax, max), timeoutSec));
            if (merged.size() >= max) break;
        }
        // videoId 기준 중복 제거
        LinkedHashMap<String, Item> uniq = new LinkedHashMap<>();
        for (Item v : merged) {
            if (v.getVideoId() != null) uniq.putIfAbsent(v.getVideoId(), v);
        }
        List<Item> list = new ArrayList<>(uniq.values());
        list.sort(Comparator.comparingLong((Item v) -> -viewCount(v)));
        if (list.size() > max) list = list.subList(0, max);
        return list;
    }

    /** 쿼리별 타임아웃 조절 가능한 공용 함수 */
    private List<Item> getYoutubeByQuerySortedWithTimeout(String query, int max, int timeoutSec) {
        try {
            YoutubeResponse res = youtubeClient.get()
                    .uri(uriBuilder -> uriBuilder.path("/youtube/search")
                            .queryParam("q", query)
                            .queryParam("max_results", max)
                            .build())
                    .retrieve()
                    .bodyToMono(YoutubeResponse.class)
                    .timeout(java.time.Duration.ofSeconds(timeoutSec))
                    .onErrorReturn(new YoutubeResponse())
                    .block();

            if (res == null || res.getItems() == null) return List.of();
            List<Item> items = new ArrayList<>(res.getItems());
            items.sort(Comparator.comparingLong((Item v) -> -viewCount(v)));
            if (items.size() > max) items = items.subList(0, max);
            return items;
        } catch (Exception e) {
            return List.of();
        }
    }

    private static long viewCount(Item v) {
        if (v == null || v.getStatistics() == null) return 0L;
        try { return Long.parseLong(v.getStatistics().getOrDefault("viewCount", "0")); }
        catch (Exception e) { return 0L; }
    }

    // =========================================================
    // Utils
    // =========================================================

    private static <T> T safeGet(SupplierX<T> s, T fallback){
        try { return s.get(); } catch (Exception e) { return fallback; }
    }
    @FunctionalInterface private interface SupplierX<T> { T get() throws Exception; }

    private static String safeLower(String s) { return s == null ? "" : s.toLowerCase(Locale.ROOT); }
}
