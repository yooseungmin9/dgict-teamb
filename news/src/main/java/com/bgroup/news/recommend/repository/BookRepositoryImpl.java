package com.bgroup.news.recommend.repository;

import com.bgroup.news.recommend.dto.BookResponse;
import lombok.RequiredArgsConstructor;
import org.bson.Document;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

@Repository
@RequiredArgsConstructor
public class BookRepositoryImpl implements BookRepositoryCustom {

    private final MongoTemplate mongo;

    @Override
    public List<BookResponse> searchPersonalized(List<String> keywords, int limit) {
        if (keywords == null || keywords.isEmpty()) return List.of();

        // 1년(초) 기준 decay 스케일 (원하면 조정)
        long nowSec = Instant.now().getEpochSecond();
        long yearSec = 31536000L;

        List<Document> pipeline = new ArrayList<>();

        // $search (Atlas Search)
        Document search = new Document("$search",
                new Document("index", "book_search")
                        .append("compound", new Document("should", List.of(
                                // title/author/keywords ANY 매칭
                                new Document("text", new Document("query", keywords)
                                        .append("path", List.of("title","author","keywords"))
                                )
                        )).append("minimumShouldMatch", 1))
        );
        pipeline.add(search);

        // 관련도 점수 꺼내기
        pipeline.add(new Document("$addFields", new Document("rel", new Document("$meta", "searchScore"))));

        // 최신성/행동지표 정규화 + 최종 점수
        // recency = exp(- max(now-pubDate,0)/scale )
        Document recency = new Document("$exp",
                new Document("$multiply", List.of(
                        -1,
                        new Document("$divide", List.of(
                                new Document("$max", List.of(
                                        0,
                                        new Document("$subtract", List.of(nowSec, new Document("$toLong", new Document("$toDate", "$pubDate"))))
                                )),
                                yearSec
                        ))
                ))
        );

        // clicks, dwellSec 정규화 (0~1 사이로 대충)
        Document clicksNorm = new Document("$min", List.of(
                1,
                new Document("$divide", List.of(new Document("$ifNull", List.of("$clicks", 0)), 50)) // 50번 클릭 = 1.0
        ));
        Document dwellNorm = new Document("$min", List.of(
                1,
                new Document("$divide", List.of(new Document("$ifNull", List.of("$dwellSec", 0.0)), 120.0)) // 120초 = 1.0
        ));
        Document behavior = new Document("$add", List.of(
                new Document("$multiply", List.of(0.6, clicksNorm)),
                new Document("$multiply", List.of(0.4, dwellNorm))
        ));

        // finalScore = rel * (0.6*recency + 0.4) * (1 + 0.3*behavior)
        Document finalScore = new Document("$multiply", List.of(
                "$rel",
                new Document("$add", List.of(new Document("$multiply", List.of(0.6, recency)), 0.4)),
                new Document("$add", List.of(1, new Document("$multiply", List.of(0.3, behavior))))
        ));

        pipeline.add(new Document("$addFields", new Document("finalScore", finalScore)));
        pipeline.add(new Document("$sort", new Document("finalScore", -1)));
        pipeline.add(new Document("$limit", limit));

        return mongo.aggregate(new org.springframework.data.mongodb.core.aggregation.TypedAggregation<>(
                BookResponse.class,
                pipeline.stream().map(doc -> (org.springframework.data.mongodb.core.aggregation.AggregationOperation)
                        context -> doc
                ).toList()
        ), BookResponse.class).getMappedResults();
    }
}