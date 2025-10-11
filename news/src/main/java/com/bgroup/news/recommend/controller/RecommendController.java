package com.bgroup.news.recommend.controller;

import com.bgroup.news.member.domain.MemberDoc;
import com.bgroup.news.recommend.dto.BookResponse;
import com.bgroup.news.recommend.dto.YoutubeResponse;
import com.bgroup.news.recommend.repository.BookRepository;
import com.bgroup.news.recommend.service.PreferenceKeywords;
import jakarta.servlet.http.HttpSession;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.ArrayList;
import java.util.List;

@Controller
@RequiredArgsConstructor
public class RecommendController {

    private final BookRepository bookRepository;
    private final @Qualifier("youtubeClient") WebClient youtubeClient;

    @GetMapping("/pages/recommend")
    public String discover(@RequestParam(required = false) String q,
                           @RequestParam(defaultValue = "10") int size,
                           Model model,
                           HttpSession session) {

        MemberDoc me = (MemberDoc) session.getAttribute("loginUser");

        List<BookResponse> books;
        List<String> activeKeywords = new ArrayList<>();

        if (me == null || me.getInterests() == null) {
            // ✅ 게스트: 판매량 내림차순 + 출간일 보조 정렬
            var sort = Sort.by(
                    Sort.Order.desc("salesPoint"),
                    Sort.Order.desc("pubDate")
            );
            var page = PageRequest.of(0, size, sort);
            books = bookRepository.findAll(page).getContent();
        } else {
            // -------------------------------
            // 로그인: 개인화(제목/저자 like) → 폴백(랭크/판매/최신)
            // -------------------------------
            activeKeywords.addAll(PreferenceKeywords.build(me.getInterests()));
            String seed = activeKeywords.isEmpty()
                    ? null
                    : String.join(" ", activeKeywords.subList(0, Math.min(3, activeKeywords.size())));

            books = (seed == null) ? List.of() : findByTitleOrAuthor(seed, size);

            if (books.isEmpty()) {
                books = fetchByRankSalesOrDate(size);
            }
        }

        // -------------------------------
        // YouTube 쿼리 (요청 q > 선호 키워드 > 기본)
        // -------------------------------
        String ytQuery = (q != null && !q.isBlank())
                ? q
                : (!activeKeywords.isEmpty()
                ? String.join(" ", activeKeywords.subList(0, Math.min(3, activeKeywords.size())))
                : "경제 강의");

        Mono<YoutubeResponse> ytMono = youtubeClient.get()
                .uri(uri -> uri.path("/youtube/search")
                        .queryParam("q", ytQuery)
                        .queryParam("max_results", 6)
                        .build())
                .retrieve()
                .bodyToMono(YoutubeResponse.class);

        YoutubeResponse yt = ytMono.block();
        var videos = (yt != null && yt.getItems() != null) ? yt.getItems() : List.of();

        model.addAttribute("books", books);
        model.addAttribute("videos", videos);
        model.addAttribute("query", ytQuery);
        model.addAttribute("activeKeywords", activeKeywords);

        return "pages/recommend";
    }

    // ============================
    // 헬퍼들
    // ============================

    /** 제목/저자 like 검색(최신순) — 개인화 1순위 조회용 */
    private List<BookResponse> findByTitleOrAuthor(String keyword, int size) {
        Pageable page = PageRequest.of(0, size, Sort.by(Sort.Direction.DESC, "pubDate"));
        return bookRepository.findByTitleContainingIgnoreCaseOrAuthorContainingIgnoreCase(
                keyword, keyword, page
        );
    }

    private List<BookResponse> fetchByRankSalesOrDate(int size) {
        // 1) 랭크 기준
        Pageable byRank = PageRequest.of(0, size, Sort.by(Sort.Order.asc("bestseller.rank")));
        List<BookResponse> rankeds = bookRepository.findRanked(byRank);
        if (!rankeds.isEmpty()) return rankeds;

        // 2) 판매지수 기준
        Pageable bySales = PageRequest.of(0, size, Sort.by(Sort.Order.desc("salesPoint")));
        List<BookResponse> bySalesPoint = bookRepository.findWithSalesPoint(bySales);
        if (!bySalesPoint.isEmpty()) return bySalesPoint;

        // 3) 최신순 폴백
        Pageable byDate = PageRequest.of(0, size, Sort.by(Sort.Direction.DESC, "pubDate"));
        return bookRepository.findAllByOrderByPubDateDesc(byDate);
    }
}
