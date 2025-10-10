package com.bgroup.news.member.domain;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;

import java.time.Instant;

@Data                       // getter/setter, toString, equals, hashCode 자동 생성
@NoArgsConstructor          // 기본 생성자 자동 생성
@AllArgsConstructor         // 모든 필드를 받는 생성자 자동 생성
@Document(collection = "members")
public class MemberDoc {

    @Id
    private String id;          // "_id": "user002"

    private String password;    // 보안: 해시로 저장 권장(BCrypt 등)
    private String name;

    @Field("birth_year")
    private Integer birthYear;  // Mongo: birth_year -> Java: birthYear

    private String phone;
    private String region;      // 예: "대전"
    private String gender;      // 예: "여"

    private Interests interests; // null 가능성 고려

    private Integer admin;      // 0/1 플래그 (권한 등급이면 Role로 대체 고려)

    // 선택: 생성/수정 시간
    private Instant createdAt;
    private Instant updatedAt;

    @Data
    @NoArgsConstructor @AllArgsConstructor @Builder
    public static class Interests {
        private Integer global;
        private Integer finance;
        private Integer estate;
        private Integer industry;
        private Integer stock;
        private Integer general;
    }
}