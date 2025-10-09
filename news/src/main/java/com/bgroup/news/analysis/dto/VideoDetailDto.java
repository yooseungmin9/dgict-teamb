package com.bgroup.news.analysis.dto;

import lombok.*;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class VideoDetailDto {
    private String video_id;
    private String title;
    private String thumbnail;
    private String video_url;
    private String published_at;
    private Long   views;
    private Long   comments;
}