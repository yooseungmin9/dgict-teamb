package com.bgroup.news.dashboard.repository;

import com.bgroup.news.dashboard.dto.KeywordRankingResponse;
import lombok.RequiredArgsConstructor;
import org.bson.Document;
import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.aggregation.*;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.stereotype.Repository;
import org.springframework.data.mongodb.core.aggregation.StringOperators;

import java.sql.Date;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.List;

@Repository
@RequiredArgsConstructor
public class KeywordRankingRepository {

    private final MongoTemplate mongoTemplate;

    /**
     * 뉴스 문서의 keywords 배열 기반 키워드 랭킹
     */
    public List<KeywordRankingResponse> topKeywords(
            String collection,
            String category,
            int days,
            int limit
    ) {
        final String dateField = "published_at";
        List<AggregationOperation> ops = new ArrayList<>();

        ops.add(Aggregation.match(Criteria.where(dateField).exists(true)));

        Document toDateExpr = Document.parse("{ $toDate: \"$" + dateField + "\" }");
        ops.add(Aggregation.addFields().addFieldWithValue("__dt", toDateExpr).build());

        // 최근 N일 기준시각 계산(UTC)
        Instant fromUtc = Instant.now().minusSeconds((long)Math.max(days,1)*86400);

        // 기간 필터
        ops.add(Aggregation.match(Criteria.where("__dt").gte(Date.from(fromUtc))));

        // category 필터 (예: 부동산, 금융 등)
        if (!"all".equalsIgnoreCase(category)) {
            ops.add(Aggregation.match(Criteria.where("category").is(category)));
        }

        // 1️⃣ keywords 배열 펼치기
        ops.add(Aggregation.match(Criteria.where("keywords").exists(true)));
        ops.add(Aggregation.unwind("keywords"));

        // 2️⃣ 문자열 정규화 (trim, 소문자 변환)
        ops.add(Aggregation.project().and(StringOperators.valueOf("keywords").trim()).as("kw_trim"));
        ops.add(Aggregation.project().and(StringOperators.valueOf("kw_trim").toLower()).as("kw"));
        ops.add(Aggregation.match(new Criteria().andOperator(
                Criteria.where("kw").ne(null),
                Criteria.where("kw").ne(""),
                Criteria.where("kw").regex(".*\\S.*")
        )));

        // 3️⃣ 그룹핑: 같은 키워드별로 집계
        ops.add(Aggregation.group("kw").count().as("count"));

        // 4️⃣ 정렬 + 상위 N개
        ops.add(Aggregation.sort(Sort.Direction.DESC, "count"));
        ops.add(Aggregation.limit(limit));

        // 5️⃣ 결과 포맷 (_id → keyword)
        ops.add(Aggregation.project()
                .and("_id").as("keyword")
                .and("count").as("count")
                .andExclude("_id"));

        Aggregation agg = Aggregation.newAggregation(ops);
        var results = mongoTemplate.aggregate(agg, collection, KeywordRankingResponse.class);
        List<KeywordRankingResponse> list = results.getMappedResults();

        // 6️⃣ 순위(rank) 부여
        int i = 1;
        for (var r : list) r.setRank(i++);

        return list;
    }
}
