package com.bgroup.news.news.dto;

import lombok.Data;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;

import java.time.LocalDateTime;
import java.util.List;

@Data
@Document(collection = "shared_articles")
public class Article {
    @Id
    private String id;

    private String title;
    private String url;
    private String content;
    private String image;
    private String summary;
    private String press;

    @Field("main_section")
    private String mainSection;

    private String category;

    @Field("sentiment_score")
    private Double sentimentScore;

    private List<String> keywords;

    @Field("published_at")
    private LocalDateTime publishedAt;
}
