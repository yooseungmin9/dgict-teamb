package com.bgroup.news.analysis.domain;

import lombok.*;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.mapping.Field;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
@Document(collection = "youtube_db2") // ← FastAPI와 동일 컬렉션
public class CommentDoc {
    @Id private String id;

    @Field("video_id")
    private String videoId;

    @Field("text")
    private String text;

    @Field("emotion")
    private String emotion;
}