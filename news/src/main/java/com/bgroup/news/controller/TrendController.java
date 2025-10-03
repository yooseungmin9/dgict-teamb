package com.bgroup.news.controller;

import com.bgroup.news.dto.KeywordRankingResponse;
import org.bson.Document;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.aggregation.Aggregation;
import org.springframework.data.mongodb.core.aggregation.AggregationOperation;
import org.springframework.data.mongodb.core.aggregation.AggregationResults;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.*;

@RestController
@RequestMapping("/api/trends")
public class TrendController {
    @Value("${app.mongo.collection:shared_articles}")
    private String articleCollection;

    private final WebClient trendClient; // FastAPI(네이버 DataLab)
    private final MongoTemplate mongoTemplate; // MongoDB(뉴스/키워드)

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
        // 1) 문자열 경계값 (DB에 저장된 포맷과 맞춤: yyyy-MM-dd'T'HH:mm:ss)
        var fmt = java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss");
        String to = java.time.LocalDateTime.now().format(fmt);
        String from = java.time.LocalDateTime.now().minusDays(days).format(fmt);

        // 2) 필요한 필드만
        AggregationOperation projectNeeded = ctx -> new Document("$project",
                new Document("category", 1)
                        .append("keywords", 1)
                        .append("published_at", 1)
        );

        // 3) 문자열 비교 (ISO-8601은 사전순 == 시간순)
        //    published_at 저장값: "2025-10-01T15:47:31.810573" (마이크로초 존재 OK)
        //    경계값: "....:ss" (짧아도 사전순 비교 상 범위 필터 정상 동작)
        AggregationOperation matchDate = ctx -> new Document("$match",
                new Document("$expr",
                        new Document("$and", List.of(
                                new Document("$gte", List.of("$published_at", from)),
                                new Document("$lte", List.of("$published_at", to))
                        ))
                )
        );

        AggregationOperation matchCat = null;
        if (category != null && !category.isBlank()) {
            matchCat = ctx -> new Document("$match", new Document("category", category));
        }

        AggregationOperation notEmptyKeywords = ctx -> new Document("$match",
                new Document("keywords", new Document("$exists", true).append("$ne", Collections.emptyList()))
        );

        AggregationOperation unwind = ctx -> new Document("$unwind", "$keywords");

        AggregationOperation groupCounts = ctx -> new Document("$group",
                new Document("_id",
                        new Document("category", "$category").append("keyword", "$keywords"))
                        .append("count", new Document("$sum", 1))
        );

        AggregationOperation groupTopN = ctx -> new Document("$group",
                new Document("_id", "$_id.category")
                        .append("keywords",
                                new Document("$topN",
                                        new Document("n", topN)
                                                .append("sortBy", new Document("count", -1))
                                                .append("output",
                                                        new Document("keyword", "$_id.keyword")
                                                                .append("count", "$count")
                                                )
                                )
                        )
        );

        AggregationOperation projectOut = ctx -> new Document("$project",
                new Document("_id", 0)
                        .append("category", "$_id")
                        .append("keywords", 1)
        );

        var ops = new ArrayList<AggregationOperation>();
        ops.add(projectNeeded);
        ops.add(matchDate);
        if (matchCat != null) ops.add(matchCat);
        ops.add(notEmptyKeywords);
        ops.add(unwind);
        ops.add(groupCounts);
        ops.add(groupTopN);
        ops.add(projectOut);

        var agg = Aggregation.newAggregation(ops);
        AggregationResults<Document> results =
                mongoTemplate.aggregate(agg, articleCollection, Document.class);

        var out = new ArrayList<KeywordRankingResponse>();
        for (Document d : results) {
            String cat = Objects.toString(d.get("category"), "");
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> arr =
                    (List<Map<String, Object>>) d.get("keywords", List.class);
            if (arr == null) continue;
            for (int i = 0; i < arr.size(); i++) {
                var m = arr.get(i);
                String kw = Objects.toString(m.get("keyword"), "");
                int cnt = ((Number) m.getOrDefault("count", 0)).intValue();
                out.add(new KeywordRankingResponse(i + 1, kw, cat, cnt));
            }
        }

        // 보기 좋게 정렬
        out.sort(Comparator
                .comparing(KeywordRankingResponse::getCategory, Comparator.nullsLast(String::compareTo))
                .thenComparingInt(KeywordRankingResponse::getRank));

        return out;
    }
}
