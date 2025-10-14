package com.bgroup.news.dashboard.service;

import lombok.RequiredArgsConstructor;
import org.bson.Document;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.aggregation.Aggregation;
import org.springframework.data.mongodb.core.aggregation.AggregationOperation;
import org.springframework.stereotype.Service;

import java.time.*;
import java.util.*;

@Service
@RequiredArgsConstructor
public class EmoaService {

    private final MongoTemplate mongoTemplate;

    private final String collectionName = "shared_articles";
    private final ZoneId zone = ZoneId.of("Asia/Seoul");

    private double clamp(double v, double lo, double hi) {
        return Math.max(lo, Math.min(hi, v));
    }

    private Double normalize0to100(Double x) {
        if (x == null) return null;
        double s = x, y;
        if (0 <= s && s <= 1) y = s * 100;
        else if (-1 <= s && s <= 1) y = (s + 1) / 2 * 100;
        else if (-100 <= s && s <= 100) y = (s + 100) / 200 * 100;
        else if (0 <= s && s <= 100) y = s;
        else y = s;
        y = clamp(y, 0, 100);
        return Math.round(y * 100.0) / 100.0;
    }

    private Double avgFor(LocalDate day, String scoreKey){
        ZoneId zone = ZoneId.of("Asia/Seoul");
        String dayStr = day.toString(); // "YYYY-MM-DD"

        List<AggregationOperation> ops = List.of(
                // published_at -> Date
                ctx -> new Document("$addFields",
                        new Document("_dt", new Document("$toDate", "$published_at"))),

                // _dt를 KST 날짜 문자열로 변환해서 dayStr와 비교 (시간대 불일치 방지)
                ctx -> new Document("$addFields",
                        new Document("_dayKst",
                                new Document("$dateToString",
                                        new Document("format", "%Y-%m-%d")
                                                .append("date", "$_dt")
                                                .append("timezone", "Asia/Seoul")))),

                ctx -> new Document("$match", new Document("_dayKst", dayStr)),

                // 점수 추출 (문자/숫자 혼재 대비)
                ctx -> new Document("$project", new Document("_id", 0)
                        .append("score", new Document("$convert",
                                new Document("input", "$" + scoreKey)
                                        .append("to","double")
                                        .append("onError", null)
                                        .append("onNull",  null)))),

                ctx -> new Document("$match", new Document("score", new Document("$ne", null))),
                ctx -> new Document("$group", new Document("_id", null)
                        .append("avg_raw", new Document("$avg", "$score")))
        );

        var agg = Aggregation.newAggregation(ops);
        var res = mongoTemplate.aggregate(agg, collectionName, Document.class)
                .getUniqueMappedResult();
        if (res == null) return null;
        Double avgRaw = res.getDouble("avg_raw");
        return normalize0to100(avgRaw);
    }


    public Map<String, Object> computeScore(String scoreKey) {
        LocalDate today = LocalDate.now(zone);
        LocalDate yest = today.minusDays(1);

        Double avgToday = avgFor(today, scoreKey);
        Double avgYest = avgFor(yest, scoreKey);
        Double delta = (avgToday == null || avgYest == null) ? null
                : Math.round((avgToday - avgYest) * 100.0) / 100.0;

        String weekdayKo = switch (today.getDayOfWeek()) {
            case MONDAY -> "월";
            case TUESDAY -> "화";
            case WEDNESDAY -> "수";
            case THURSDAY -> "목";
            case FRIDAY -> "금";
            case SATURDAY -> "토";
            case SUNDAY -> "일";
        };

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("date", today.toString());
        out.put("weekday", weekdayKo);
        out.put("avg", avgToday);
        out.put("delta", delta);
        return out;
    }
}
