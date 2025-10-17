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

    private final TrendService trendService;
    private final SentimentService sentimentService;
    private final KeywordRankingRepository keywordRepo;
    private final EmoaService emoaService;
    private final NewsCountService newsCountService;

    @GetMapping("/trends/category-trends")
    public Map<String, Object> categoryTrends(@RequestParam(defaultValue = "30") int days) {
        return trendService.getCategoryTrends(days);
    }

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

    @GetMapping("/keywords/ranking")
    public List<KeywordRankingResponse> ranking(
            @RequestParam String category,
            @RequestParam(defaultValue = "30") int days,
            @RequestParam(defaultValue = "50") int limit) {
        // 너희 컬렉션명으로 바꿔줘 (예: "news")
        return keywordRepo.topKeywords("shared_articles", category, days, limit);
    }

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
