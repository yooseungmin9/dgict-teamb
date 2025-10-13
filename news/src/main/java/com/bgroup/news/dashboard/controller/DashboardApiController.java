package com.bgroup.news.dashboard.controller;

import com.bgroup.news.dashboard.dto.KeywordRankingResponse;
import com.bgroup.news.dashboard.dto.NewsCountResponse;
import com.bgroup.news.dashboard.repository.KeywordRankingRepository;
import com.bgroup.news.dashboard.service.EmoaService;
import com.bgroup.news.dashboard.service.NewsCountService;
import com.bgroup.news.dashboard.service.SentimentService;
import com.bgroup.news.dashboard.service.TrendService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.OffsetDateTime;
import java.time.ZoneId;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/dashboard")
@RequiredArgsConstructor
public class DashboardApiController {

    private final TrendService trendService;                 // 8006 proxy
    private final SentimentService sentimentService;         // 8007 proxy
    private final KeywordRankingRepository keywordRepo;      // Mongo aggregation
    private final EmoaService emoaService;
    private final NewsCountService newsCountService;

    /** 핫토픽(데이터랩 그래프) — FastAPI(8006) 프록시 */
    @GetMapping("/trends/category-trends")
    public Map<String, Object> categoryTrends(@RequestParam(defaultValue = "30") int days) {
        return trendService.getCategoryTrends(days);
    }

    /** 감성 라인/스택 — FastAPI(8007) 프록시 */
    @GetMapping("/sentiment/line")
    public ResponseEntity<?> sentimentLine(
            @RequestParam(defaultValue = "count") String mode,
            @RequestParam(defaultValue = "30") int days) {
        try {
            return ResponseEntity.ok(sentimentService.getLine(mode, days));
        } catch (Exception e) {
            return ResponseEntity.status(504).body(Map.of(
                    "ok", false, "series", List.of(), "message", e.getMessage()));
        }
    }

    /** 키워드 랭킹 — Mongo 집계 */
    @GetMapping("/keywords/ranking")
    public List<KeywordRankingResponse> ranking(
            @RequestParam String category,                 // '금융','부동산','산업','글로벌경제','일반'
            @RequestParam(defaultValue = "30") int days,
            @RequestParam(defaultValue = "50") int limit) {
        // 너희 컬렉션명으로 바꿔줘 (예: "news")
        return keywordRepo.topKeywords("shared_articles", category, days);
    }

    // /emoa/score?score_key=sentiment_score
    @GetMapping("/emoa/score")
    public Map<String,Object> score(@RequestParam(name="score_key", defaultValue="sentiment_score") String scoreKey){
        return emoaService.computeScore(scoreKey);
    }

    @GetMapping("/count")
    public NewsCountResponse getNewsCount() {
        long total = newsCountService.total();
        long today = newsCountService.countTodayKST();
        long last7 = newsCountService.countLast7DaysKST();
        return new NewsCountResponse(
                newsCountService.getCollection(),
                total, today, last7,
                OffsetDateTime.now(ZoneId.of("Asia/Seoul"))
        );
    }
}
