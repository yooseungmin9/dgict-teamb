package com.bgroup.news.mongo.document;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;

@Data                       // getter/setter, toString, equals, hashCode 자동 생성
@NoArgsConstructor          // 기본 생성자 자동 생성
@AllArgsConstructor         // 모든 필드를 받는 생성자 자동 생성
@Document(collection = "members")
public class MemberDoc {

    @Id
    private String id;

    private String password;
    private String name;

    @Field("birth_year")
    private Integer birthYear;

    private String phone;
    private String region;
    private String gender;

    private Interests interests;

    private Integer admin;
}
