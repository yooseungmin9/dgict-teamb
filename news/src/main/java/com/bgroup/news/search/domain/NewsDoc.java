package com.bgroup.news.search.domain;

import lombok.Data;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;

import java.util.List;

@Data
@Document(collection = "shared_articles")
public class NewsDoc {

    @Id
    private String id;

    private String title;

    // url / image 그대로 저장됨
    private String url;
    private String image;

    private String summary;
    private String content;

    // 언론사
    private String press;

    // 대분류/중분류
    @Field("main_section")
    private String mainSection;

    private String category;

    @Field("sentiment_score")
    private Integer sentimentScore;   // 없으면 null

    private List<String> keywords;

    // NOTE: 현재 DB가 문자열로 저장하고 있으므로 String 사용
    @Field("published_at")
    private String publishedAt;
}