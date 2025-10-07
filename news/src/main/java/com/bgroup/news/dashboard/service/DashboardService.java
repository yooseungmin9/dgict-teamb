package com.bgroup.news.dashboard.service;

import com.bgroup.news.origin.dto.KeywordRankingResponse;
import lombok.RequiredArgsConstructor;
import org.bson.Document;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.aggregation.Aggregation;
import org.springframework.data.mongodb.core.aggregation.AggregationOperation;
import org.springframework.data.mongodb.core.aggregation.AggregationResults;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

@Service
@RequiredArgsConstructor
public class DashboardService {

    @Value("${app.mongo.collection:shared_articles}")
    private String articleCollection;

    @Qualifier("trendClient")
    private final WebClient trendClient;

    private final MongoTemplate mongoTemplate;

    public Mono<String> fetchCategoryTrends(int days, String timeUnit) {
        return trendClient.get()
                .uri(uri -> uri.path("/category-trends")
                        .queryParam("days", days)
                        .queryParam("time_unit", timeUnit)
                        .build())
                .retrieve()
                .bodyToMono(String.class);
    }

    public List<KeywordRankingResponse> fetchKeywordRanking(int topN, String category, int days) {
        DateTimeFormatter fmt = DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss");
        String to = LocalDateTime.now().format(fmt);
        String from = LocalDateTime.now().minusDays(days).format(fmt);

        AggregationOperation projectNeeded = ctx -> new Document("$project",
                new Document("category", 1)
                        .append("keywords", 1)
                        .append("published_at", 1));

        AggregationOperation matchDate = ctx -> new Document("$match",
                new Document("$expr",
                        new Document("$and", List.of(
                                new Document("$gte", List.of("$published_at", from)),
                                new Document("$lte", List.of("$published_at", to))
                        ))));

        AggregationOperation matchCat = null;
        if (category != null && !category.isBlank()) {
            matchCat = ctx -> new Document("$match", new Document("category", category));
        }

        AggregationOperation notEmptyKeywords = ctx -> new Document("$match",
                new Document("keywords", new Document("$exists", true).append("$ne", Collections.emptyList())));
        AggregationOperation unwind = ctx -> new Document("$unwind", "$keywords");
        AggregationOperation groupCounts = ctx -> new Document("$group",
                new Document("_id",
                        new Document("category", "$category").append("keyword", "$keywords"))
                        .append("count", new Document("$sum", 1)));

        AggregationOperation groupTopN = ctx -> new Document("$group",
                new Document("_id", "$_id.category")
                        .append("keywords",
                                new Document("$topN",
                                        new Document("n", topN)
                                                .append("sortBy", new Document("count", -1))
                                                .append("output",
                                                        new Document("keyword", "$_id.keyword")
                                                                .append("count", "$count")))));

        AggregationOperation projectOut = ctx -> new Document("$project",
                new Document("_id", 0)
                        .append("category", "$_id")
                        .append("keywords", 1));

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

        out.sort(Comparator
                .comparing(KeywordRankingResponse::getCategory, Comparator.nullsLast(String::compareTo))
                .thenComparingInt(KeywordRankingResponse::getRank));
        return out;
    }
}
