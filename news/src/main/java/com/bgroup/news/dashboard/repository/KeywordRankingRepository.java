package com.bgroup.news.dashboard.repository;

import com.bgroup.news.dashboard.dto.KeywordRankingResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.aggregation.*;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.stereotype.Repository;
import org.springframework.data.mongodb.core.aggregation.StringOperators;

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
            int limit
    ) {
        List<AggregationOperation> ops = new ArrayList<>();

        // category 필터 (예: 부동산, 금융 등)
        if (!"all".equalsIgnoreCase(category)) {
            ops.add(Aggregation.match(Criteria.where("category").is(category)));
        }

        // 1️⃣ keywords 배열 펼치기
        ops.add(Aggregation.unwind("keywords"));

        // 2️⃣ 문자열 정규화 (trim, 소문자 변환)
        ops.add(Aggregation.project()
                .and(StringOperators.valueOf("keywords").trim()).as("kw_trim"));
        ops.add(Aggregation.project()
                .and(StringOperators.valueOf("kw_trim").toLower()).as("kw"));

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
