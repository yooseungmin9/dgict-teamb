package com.bgroup.news.member.domain;

import lombok.*;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;

import java.time.Instant;
import java.util.Map;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Document(collection = "members")
public class MemberDoc {
    @Id private String id;
    private String password;
    private String name;
    @Field("birth_year") private Integer birthYear;
    private String phone;
    private String region;
    private String gender;

    // ✅ 기존(하위호환용 합계)
    private Interests interests;   // global/finance/estate/industry/stock/general

    private Integer admin;
    private Instant createdAt;
    private Instant updatedAt;

    // ✅ 신규: 세분화 저장소
    private Preferences preferences;

    @Data @NoArgsConstructor @AllArgsConstructor @Builder
    public static class Interests {
        private Integer global, finance, estate, industry, stock, general;
    }

    @Data @NoArgsConstructor @AllArgsConstructor @Builder
    public static class Preferences {
        // parent -> (sub -> score)
        private Map<String, Map<String, Integer>> explicit;
        private Map<String, Map<String, Integer>> implicit;
        private Instant lastUpdated;
    }
}
