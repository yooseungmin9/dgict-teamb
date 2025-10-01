// TrendController.java — 람다 캡처 오류 해결 + 오타 교정 + 주석/테스트 예시 포함
package com.bgroup.news.controller;

import com.bgroup.news.dto.KeywordRankingResponse;
import org.bson.Document;
import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.aggregation.*;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.*;

/**
 * /api/trends 컨트롤러
 * - FastAPI 프록시: GET /api/trends/category-trends
 * - Mongo 집계:   GET /api/trends/keyword-ranking
 */
@RestController
@RequestMapping("/api/trends")
public class TrendController {

    private final WebClient trendClient;   // FastAPI 베이스 URL로 구성된 WebClient (예: http://localhost:8000/api/trends)
    private final MongoTemplate mongoTemplate;

    public TrendController(WebClient trendClient, MongoTemplate mongoTemplate) {
        this.trendClient = trendClient;
        this.mongoTemplate = mongoTemplate;
    }

    // ============ 1) 네이버 DataLab 언급량 (FastAPI 프록시) ============
    @GetMapping("/category-trends")
    public Mono<ResponseEntity<String>> categoryTrends(
            @RequestParam(defaultValue = "30") int days,
            @RequestParam(name = "time_unit", defaultValue = "date") String timeUnit
    ) {
        // [입문자 주석] 람다에서 캡처할 변수는 final 또는 effectively final 이어야 함
        // days를 재할당하지 말고, '보정값'을 새 변수에 담아서 사용
        final int normalizedDays = Math.min(365, Math.max(7, days));
        final String normalizedTimeUnit = timeUnit; // 여기서는 재할당 안 하므로 effectively final

        return trendClient.get()
                .uri(uri -> uri.path("/category-trends")
                        .queryParam("days", normalizedDays)
                        .queryParam("time_unit", normalizedTimeUnit)
                        .build())
                .retrieve()
                .bodyToMono(String.class)
                .map(ResponseEntity::ok)
                .onErrorResume(ex ->
                        Mono.just(ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                                .body("{\"error\":\"trends proxy failed\"}")));
    }

    // ============ 2) Mongo 키워드 랭킹 (카테고리별 TopN) ============
    @GetMapping("/keyword-ranking")
    public List<KeywordRankingResponse> keywordRanking(
            @RequestParam(name = "topN", defaultValue = "10") int topN,
            @RequestParam(required = false) String category,
            @RequestParam(defaultValue = "30") int days
    ) {
        // [입문자 주석] 파라미터 가드는 별도 변수에 담아 effectively final 유지
        final int nTopN = Math.min(1000, Math.max(1, topN));
        final int nDays = Math.min(365, Math.max(7, days));

        final DateTimeFormatter fmt = DateTimeFormatter.BASIC_ISO_DATE; // YYYYMMDD
        final String to = LocalDate.now().format(fmt);
        final String from = LocalDate.now().minusDays(nDays).format(fmt);

        // 1) 필요한 필드만 남기기
        AggregationOperation projectNeeded = context -> new Document("$project",
                new Document("category", 1)
                        .append("keywords", 1)
                        .append("news_date", 1));

        // 2) 날짜 필터
        Criteria dateCri = Criteria.where("news_date").gte(from).lte(to);
        AggregationOperation matchDate = Aggregation.match(dateCri);

        // 3) 카테고리 필터(옵션)
        AggregationOperation matchCat = null;
        if (StringUtils.hasText(category)) {
            matchCat = Aggregation.match(Criteria.where("category").is(category));
        }

        // 4) keywords 펼치기
        AggregationOperation unwindKeywords = context -> new Document("$unwind", "$keywords");

        // 5) (category, keyword) 단위로 count
        AggregationOperation groupCatKw = context -> new Document("$group",
                new Document("_id", new Document("category", "$category").append("keyword", "$keywords"))
                        .append("count", new Document("$sum", 1)));

        // 6) 카테고리별 정렬을 위해 우선 정렬(카테고리↑, count↓)
        AggregationOperation sortForGroup = Aggregation.sort(Sort.by(
                Sort.Order.asc("_id.category"),
                Sort.Order.desc("count")
        ));

        // 7) 카테고리 단위로 모으면서 정렬된 상태의 배열을 push
        //    [중요] "$._id.keyword" → 오타. 정식 경로는 "$_id.keyword"
        AggregationOperation groupByCategory = context -> new Document("$group",
                new Document("_id", "$_id.category")
                        .append("keywords", new Document("$push",
                                new Document("keyword", "$_id.keyword")
                                        .append("count", "$count")
                        )));

        // 8) TopN만 자르기 ($slice 사용 → Mongo 4.x 이상 호환)
        AggregationOperation projectSliceTopN = context -> new Document("$project",
                new Document("_id", 0)
                        .append("category", "$_id")
                        .append("keywords", new Document("$slice", Arrays.asList("$keywords", nTopN))));

        // 파이프라인 구성
        List<AggregationOperation> ops = new ArrayList<>();
        ops.add(projectNeeded);
        ops.add(matchDate);
        if (matchCat != null) ops.add(matchCat);
        ops.add(unwindKeywords);
        ops.add(groupCatKw);
        ops.add(sortForGroup);
        ops.add(groupByCategory);
        ops.add(projectSliceTopN);

        Aggregation agg = Aggregation.newAggregation(ops);
        var results = mongoTemplate.aggregate(agg, "shared_articles", Document.class);

        // 평탄화하여 응답 DTO 만들기
        List<KeywordRankingResponse> flat = new ArrayList<>();
        for (Document d : results) {
            String cat = d.getString("category");
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> arr = (List<Map<String, Object>>) d.get("keywords", List.class);
            if (arr == null) continue;

            for (int i = 0; i < arr.size(); i++) {
                Map<String, Object> m = arr.get(i);
                String kw = Objects.toString(m.get("keyword"), "");
                int cnt = ((Number) m.getOrDefault("count", 0)).intValue();
                flat.add(new KeywordRankingResponse(i + 1, kw, cat, cnt));
            }
        }

        // 보기 좋게 카테고리/랭크 순 정렬(선택)
        flat.sort(Comparator
                .comparing(KeywordRankingResponse::getCategory, Comparator.nullsLast(String::compareTo))
                .thenComparingInt(KeywordRankingResponse::getRank));

        return flat;
    }
}

/* =========================
   간단 사용 예시(테스트)
   — 터미널에서 호출
=========================

# 1) FastAPI 프록시 (네이버 DataLab 라인 차트용)
curl "http://localhost:8080/api/trends/category-trends?days=30&time_unit=date"

# 2) 키워드 랭킹 (카테고리별 TopN)
curl "http://localhost:8080/api/trends/keyword-ranking?days=30&topN=10"

# 3) 특정 카테고리만 (예: 증권)
curl "http://localhost:8080/api/trends/keyword-ranking?days=30&topN=15&category=증권"

*/