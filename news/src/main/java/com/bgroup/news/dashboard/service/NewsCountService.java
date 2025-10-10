package com.bgroup.news.dashboard.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.stereotype.Service;

import java.time.*;

@Service
public class NewsCountService {

    private final MongoTemplate mongoTemplate;

    @Value("${app.mongo.collection:shared_articles}")
    private String collection;

    public NewsCountService(MongoTemplate mongoTemplate) {
        this.mongoTemplate = mongoTemplate;
    }

    public String getCollection() { return collection; }

    public long total() {
        return mongoTemplate.getCollection(collection).estimatedDocumentCount();
    }

    private long countFrom(Instant fromInclusive) {
        Query q = new Query(Criteria.where("published_at").gte(fromInclusive));
        return mongoTemplate.count(q, collection);
    }

    public long countTodayKST() {
        ZoneId KST = ZoneId.of("Asia/Seoul");
        ZonedDateTime t0 = LocalDate.now(KST).atStartOfDay(KST);
        return countFrom(t0.toInstant());
    }

    public long countLast7DaysKST() {
        ZoneId KST = ZoneId.of("Asia/Seoul");
        ZonedDateTime t0 = LocalDate.now(KST).atStartOfDay(KST).minusDays(6); // 오늘 포함 7일
        return countFrom(t0.toInstant());
    }
}
