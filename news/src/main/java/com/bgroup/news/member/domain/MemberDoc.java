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
        // ===== 기존(그대로 유지)
        // parent -> (sub -> score)
        private Map<String, Map<String, Integer>> explicit;
        private Map<String, Map<String, Integer>> implicit;
        private Instant lastUpdated;

        // 단일(하위호환)
        private String mainSource;

        @Data @NoArgsConstructor @AllArgsConstructor
        public static class Platforms {
            private String portal;                 // 단일(하위호환)
            private java.util.List<String> sns;
            private java.util.List<String> video;
            private java.util.List<String> ott;
        }
        private Platforms platforms;

        // ===== ✅ 신규: 다중 선택 저장
        private java.util.List<String> mainSources;  // ["portal","youtube",...]
        private java.util.List<String> portals;      // ["Naver","Google"]
    }
}
