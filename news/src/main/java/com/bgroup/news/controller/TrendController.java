package com.bgroup.news.controller;

import com.bgroup.news.dto.KeywordRankingResponse;
import org.bson.Document;

import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.aggregation.*;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Objects;

@RestController
@RequestMapping("/api/trends")
public class TrendController {

    private final WebClient trendClient; // FastAPI(네이버 DataLab)
    private final MongoTemplate mongoTemplate; // MongoDB(키워드)

    public TrendController(WebClient trendClient, MongoTemplate mongoTemplate) {
        this.trendClient = trendClient;
        this.mongoTemplate = mongoTemplate;
    }

    // 1) 네이버 DataLab 언급량
    @GetMapping("/category-trends")
    public Mono<String> categoryTrends(
            @RequestParam(defaultValue = "30") int days,
            @RequestParam(defaultValue = "date") String time_unit
    ) {
        return trendClient.get()
                .uri(uri -> uri.path("/category-trends")
                        .queryParam("days", days)
                        .queryParam("time_unit", time_unit)
                        .build())
                .retrieve()
                .bodyToMono(String.class);
    }

    // 2) Mongo 키워드 랭킹
    @GetMapping("/keyword-ranking")
    public List<KeywordRankingResponse> keywordRanking(
            @RequestParam(defaultValue = "10") int topN,
            @RequestParam(required = false) String category,
            @RequestParam(defaultValue = "30") int days
    ) {
        var fmt = java.time.format.DateTimeFormatter.BASIC_ISO_DATE;
        String to = java.time.LocalDate.now().format(fmt);
        String from = java.time.LocalDate.now().minusDays(days).format(fmt);

        // 필요한 필드만
        AggregationOperation projectNeeded = ctx -> new org.bson.Document("$project",
                new org.bson.Document("category", 1)
                        .append("keywords", 1)
                        .append("news_date", 1)
        );
        AggregationOperation matchDate = ctx -> new org.bson.Document("$match",
                new org.bson.Document("news_date", new org.bson.Document("$gte", from).append("$lte", to))
        );
        AggregationOperation matchCat = null;
        if (category != null && !category.isBlank()) {
            matchCat = ctx -> new org.bson.Document("$match", new org.bson.Document("category", category));
        }

        AggregationOperation unwind = ctx -> new org.bson.Document("$unwind", "$keywords");

        // (cat, keyword)로 count
        AggregationOperation groupCounts = ctx -> new org.bson.Document("$group",
                new org.bson.Document("_id",
                        new org.bson.Document("category", "$category").append("keyword", "$keywords"))
                        .append("count", new org.bson.Document("$sum", 1))
        );

        // 카테고리 그룹에서 topN (전역 sort 없이)
        AggregationOperation groupTopN = ctx -> new org.bson.Document("$group",
                new org.bson.Document("_id", "$_id.category")
                        .append("keywords",
                                new org.bson.Document("$topN",
                                        new org.bson.Document("n", topN)
                                                .append("sortBy", new org.bson.Document("count", -1))
                                                .append("output",
                                                        new org.bson.Document("keyword", "$_id.keyword")
                                                                .append("count", "$count")
                                                )
                                )
                        )
        );

        AggregationOperation projectOut = ctx -> new org.bson.Document("$project",
                new org.bson.Document("_id", 0)
                        .append("category", "$_id")
                        .append("keywords", 1)
        );

        List<AggregationOperation> ops = new ArrayList<>(List.of(projectNeeded, matchDate));
        if (matchCat != null) ops.add(matchCat);
        ops.addAll(List.of(unwind, groupCounts, groupTopN, projectOut));

        Aggregation agg = Aggregation.newAggregation(ops);
        var results = mongoTemplate.aggregate(agg, "shared_articles", org.bson.Document.class);

        List<KeywordRankingResponse> flat = new ArrayList<>();
        for (org.bson.Document d : results) {
            String cat = d.getString("category");
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> arr = (List<Map<String, Object>>) d.get("keywords", List.class);
            for (int i = 0; i < arr.size(); i++) {
                Map<String, Object> m = arr.get(i);
                String kw = Objects.toString(m.get("keyword"), "");
                int cnt = ((Number) m.getOrDefault("count", 0)).intValue();
                flat.add(new KeywordRankingResponse(i + 1, kw, cat, cnt));
            }
        }
        flat.sort(Comparator.comparing(KeywordRankingResponse::getCategory, Comparator.nullsLast(String::compareTo))
                .thenComparingInt(KeywordRankingResponse::getRank));
        return flat;
    }
}

