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

    private Interests interests;

    private Integer admin;
    private Instant createdAt;
    private Instant updatedAt;

    private Preferences preferences;

    @Data @NoArgsConstructor @AllArgsConstructor @Builder
    public static class Interests {
        private Integer global, finance, estate, industry, stock, general;
    }

    @Data @NoArgsConstructor @AllArgsConstructor @Builder
    public static class Preferences {
        private Map<String, Map<String, Integer>> explicit;
        private Map<String, Map<String, Integer>> implicit;
        private Instant lastUpdated;

        private String mainSource;

        @Data @NoArgsConstructor @AllArgsConstructor
        public static class Platforms {
            private String portal;
            private java.util.List<String> sns;
            private java.util.List<String> video;
            private java.util.List<String> ott;
        }
        private Platforms platforms;

        private java.util.List<String> mainSources;
        private java.util.List<String> portals;
    }
}
