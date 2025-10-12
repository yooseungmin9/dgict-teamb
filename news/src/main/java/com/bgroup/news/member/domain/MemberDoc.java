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
        // 기존: parent -> (sub -> score)
        private Map<String, Map<String, Integer>> explicit;
        private Map<String, Map<String, Integer>> implicit;
        private Instant lastUpdated;

        // ▼ 신규(설문 전용, 모두 Optional) — 기존 문서에 없으면 null 유지
        private String mainSource;  // "portal" | "sns" | "youtube" | "ott" | "pressSite"

        @Data @NoArgsConstructor @AllArgsConstructor
        public static class Platforms {
            private String portal;          // "Naver" | "Daum" | ...
            private java.util.List<String> sns;    // ["Instagram","X","TikTok"]
            private java.util.List<String> video;  // ["YouTube","TikTok"]
            private java.util.List<String> ott;    // ["Netflix", ...]
        }
        private Platforms platforms;

        // 카테고리 가중치 (설문 척도 → 0.0~1.0)
        private Map<String, Double> categoryWeights; // economy, politics, tech, world, stock, realEstate, industry, culture

        @Data @NoArgsConstructor @AllArgsConstructor
        public static class RegionInterest {
            private String metro; // "수도권" 등
            private String city;  // "성남"
            private Double level; // 0.0~1.0
        }
        private RegionInterest regionInterest;
    }
}
