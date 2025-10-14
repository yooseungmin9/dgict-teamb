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
@RequestMapping("/pages")
@RequiredArgsConstructor
public class RecommendController {

    private final BookRepository bookRepo;
    private final WebClient youtubeClient;
    private final PreferenceKeywords pref;

    // recommendPage : 추천 페이지 / 로그인 분기 / 기본값·개인화 세팅 / 모델 추가
    @GetMapping(value = "/recommend", produces = MediaType.TEXT_HTML_VALUE)
    public String recommendPage(
            @SessionAttribute(value = "loginUser", required = false) MemberDoc me,
            Model model
    ) {
        final boolean loggedIn = (me != null);
        model.addAttribute("loggedIn", loggedIn);

        final int BOOK_SIZE_DEFAULT = 5;
        final int YOUTUBE_SIZE_DEFAULT = 6;

        List<BookResponse> defaultBooks = getTrendingBooks(BOOK_SIZE_DEFAULT);
        List<Item> defaultVideos = getYoutubeForDefault(YOUTUBE_SIZE_DEFAULT);

        model.addAttribute("defaultBooks", defaultBooks);
        model.addAttribute("defaultVideos", defaultVideos);

        if (loggedIn) {
            var prefs = Optional.ofNullable(me.getPreferences()).orElse(null);
            List<String> mainSources = (prefs != null && prefs.getMainSources() != null)
                    ? prefs.getMainSources() : List.of();
            List<String> portals = (prefs != null && prefs.getPortals() != null)
                    ? prefs.getPortals() : List.of();

            boolean preferYouTube = mainSources.contains("youtube")
                    || (prefs != null && prefs.getPlatforms() != null
                    && prefs.getPlatforms().getVideo() != null
                    && !prefs.getPlatforms().getVideo().isEmpty());

            boolean preferSNS = mainSources.contains("sns")
                    || (prefs != null && prefs.getPlatforms() != null
                    && prefs.getPlatforms().getSns() != null
                    && !prefs.getPlatforms().getSns().isEmpty());

            boolean preferPortal = mainSources.contains("portal") || !portals.isEmpty();

            List<String> seeds = pref.buildSeeds(me, 3, 8);

            List<BookResponse> personalBooks = safeGet(() -> getPersonalBooks(seeds, BOOK_SIZE_DEFAULT, defaultBooks), defaultBooks);
            List<Item> personalVideos = safeGet(
                    () -> getYoutubePersonalWithPreference(seeds, YOUTUBE_SIZE_DEFAULT, defaultVideos, preferYouTube),
                    defaultVideos
            );

            model.addAttribute("personalBooks", personalBooks);
            model.addAttribute("personalVideos", personalVideos);
            model.addAttribute("activeKeywords", String.join(", ", seeds));

            model.addAttribute("preferYouTube", preferYouTube);
            model.addAttribute("preferSNS", preferSNS);
            model.addAttribute("preferPortal", preferPortal);
            model.addAttribute("activePortals", String.join(", ", portals));
        }

        return "pages/recommend";
    }

    // getTrendingBooks : 비로그인용 기본 도서 추천 / 판매지수·출간일·스코어 / 중복 제거 / 상위 n
    private List<BookResponse> getTrendingBooks(int size) {
        Pageable bySales = PageRequest.of(0, 200, Sort.by(Sort.Order.desc("salesPoint")));
        Pageable byDate = PageRequest.of(0, 200, Sort.by(Sort.Order.desc("pubDate")));

        List<BookResponse> pool = new ArrayList<>();
        pool.addAll(bookRepo.findAll(bySales).getContent());
        pool.addAll(bookRepo.findAll(byDate).getContent());

        Map<String, BookResponse> unique = new LinkedHashMap<>();
        for (BookResponse b : pool) {
            if (b != null && b.getId() != null) unique.putIfAbsent(b.getId(), b);
        }
        List<BookResponse> uniqPool = new ArrayList<>(unique.values());

        Instant now = Instant.now();
        Map<String, Double> scored = new LinkedHashMap<>();
        for (BookResponse b : uniqPool) {
            double s = 0.65 * normalizeSales(b.getSalesPoint())
                    + 0.35 * freshnessScore(b.getPubDate(), now);
            if (s > 0) scored.put(b.getId(), s);
        }

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

    // getPersonalBooks : 로그인용 도서 추천 / 키워드·출간일·판매지수 가중 / 상위 n / 폴백
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
            List<BookResponse> best = getTrendingBooks(size);
            for (BookResponse b : best) {
                if (ranked.size() >= size) break;
                if (ranked.stream().noneMatch(x -> Objects.equals(x.getId(), b.getId()))) {
                    ranked.add(b);
                }
            }
        }
        return ranked;
    }

    // keywordMatchScore : 제목·저자 키워드 매칭률
    private static double keywordMatchScore(BookResponse b, List<String> seeds) {
        if (b == null || seeds == null || seeds.isEmpty()) return 0;
        String title = safeLower(b.getTitle());
        String author = safeLower(b.getAuthor());
        long hit = seeds.stream()
                .map(RecommendController::safeLower)
                .filter(kw -> title.contains(kw) || author.contains(kw))
                .count();
        return Math.min(1.0, hit / Math.max(1.0, seeds.size() / 2.0));
    }

    // freshnessScore : 출간일 최신성 점수
    private static double freshnessScore(Instant pubDate, Instant now) {
        if (pubDate == null) return 0.2;
        long days = Math.max(1, (now.toEpochMilli() - pubDate.toEpochMilli()) / (1000L * 60 * 60 * 24));
        double v = 1.0 - Math.min(1.0, days / 365.0);
        return Math.max(0.0, v);
    }

    // normalizeSales : 판매지수 정규화
    private static double normalizeSales(Integer salesPoint) {
        if (salesPoint == null) return 0.0;
        double v = Math.min(100_000, Math.max(0, salesPoint));
        return v / 100_000.0;
    }

    // getYoutubeForDefault : 비로그인 기본 유튜브 추천
    private List<Item> getYoutubeForDefault(int max) {
        List<Item> r1 = getYoutubeByQuerySortedWithTimeout("경제 강의", max, 8);
        if (!r1.isEmpty()) return r1;
        List<Item> r2 = getYoutubeByQuerySortedWithTimeout("경제 입문 강의", max, 8);
        if (!r2.isEmpty()) return r2;
        return getYoutubeByQuerySortedWithTimeout("재테크 강의", max, 8);
    }

    // getYoutubePersonalWithPreference : 개인화 유튜브 추천 / 선호도 반영 / 폴백
    private List<Item> getYoutubePersonalWithPreference(List<String> seeds, int max, List<Item> fallback, boolean preferYouTube){
        if (seeds == null || seeds.isEmpty()) return fallback;

        if (!preferYouTube) {
            List<String> s1 = (seeds.size() > 2) ? seeds.subList(0,2) : seeds;
            List<Item> list = mergeYoutubeBySeeds(s1, Math.min(max, 4), 2, 4);
            return list.isEmpty() ? getYoutubeForDefault(max) : list;
        }

        List<String> s1 = seeds.size() > 3 ? seeds.subList(0, 3) : seeds;
        List<Item> list = mergeYoutubeBySeeds(s1, max, 5, 6);

        if (list.size() < Math.max(2, max/2) && seeds.size() > s1.size()){
            int to = Math.min(6, seeds.size());
            List<String> s2 = seeds.subList(0, to);
            list = mergeYoutubeBySeeds(s2, max, 4, 7);
        }
        return list.isEmpty() ? getYoutubeForDefault(max) : list;
    }

    // mergeYoutubeBySeeds : 여러 검색 결과 병합 / 중복 제거 / 조회수 정렬
    private List<Item> mergeYoutubeBySeeds(List<String> seeds, int max, int perSeedMax, int timeoutSec) {
        List<Item> merged = new ArrayList<>();
        for (String s : seeds) {
            merged.addAll(getYoutubeByQuerySortedWithTimeout(s, Math.min(perSeedMax, max), timeoutSec));
            if (merged.size() >= max) break;
        }
        LinkedHashMap<String, Item> uniq = new LinkedHashMap<>();
        for (Item v : merged) {
            if (v.getVideoId() != null) uniq.putIfAbsent(v.getVideoId(), v);
        }
        List<Item> list = new ArrayList<>(uniq.values());
        list.sort(Comparator.comparingLong((Item v) -> -viewCount(v)));
        if (list.size() > max) list = list.subList(0, max);
        return list;
    }

    // getYoutubeByQuerySortedWithTimeout : 단일 유튜브 요청 / 정렬 / 타임아웃
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

    // viewCount : 조회수 파싱
    private static long viewCount(Item v) {
        if (v == null || v.getStatistics() == null) return 0L;
        try { return Long.parseLong(v.getStatistics().getOrDefault("viewCount", "0")); }
        catch (Exception e) { return 0L; }
    }

    // safeGet : 예외 시 폴백 반환
    private static <T> T safeGet(SupplierX<T> s, T fallback){
        try { return s.get(); } catch (Exception e) { return fallback; }
    }

    // SupplierX : 체크 예외용 Supplier
    @FunctionalInterface private interface SupplierX<T> { T get() throws Exception; }

    // safeLower : null 방지 소문자 변환
    private static String safeLower(String s) { return s == null ? "" : s.toLowerCase(Locale.ROOT); }
}
