package com.bgroup.news.recommend.dto;

import lombok.Data;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;

import java.time.Instant;

@Data
@Document(collection = "aladin_books")
public class BookResponse {
    @Id
    private String id;

    @Field("uniqueKey") private String uniqueKey;
    @Field("author")    private String author;
    @Field("categoryId") private Integer categoryId;
    @Field("cover")     private String cover;
    @Field("ingestedAt") private Instant ingestedAt;
    @Field("isbn13")    private String isbn13;
    @Field("link")      private String link;
    @Field("pubDate")   private Instant pubDate;  // 필요 시 LocalDate/Date로 변경 가능
    @Field("source")    private String source;
    @Field("title")     private String title;
    @Field("updatedAt") private Instant updatedAt;
}
