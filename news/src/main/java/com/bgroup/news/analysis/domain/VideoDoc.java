package com.bgroup.news.analysis.domain;

import java.time.Instant;
import java.util.List;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;
import lombok.*;

@Document(collection = "youtube_db2")
@Data @NoArgsConstructor @AllArgsConstructor @Builder
public class VideoDoc {
    @Id private String id;
    @Field("video_id")     private String videoId;
    @Field("category")     private String category;
    @Field("title")        private String title;
    @Field("published_at") private Instant publishedAt;
    @Field("view_count")   private Long viewCount;
    @Field("comment_count")private Long commentCount;
    @Field("thumbnail_url")private String thumbnailUrl;

    private List<Comment> comments;

    @Data @NoArgsConstructor @AllArgsConstructor @Builder
    public static class Comment {
        private String text;
        private String emotion;
    }
}