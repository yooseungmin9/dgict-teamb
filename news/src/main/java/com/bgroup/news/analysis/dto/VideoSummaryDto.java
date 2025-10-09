package com.bgroup.news.analysis.dto;

import lombok.*;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class VideoSummaryDto {
    private String video_id;
    private String title;
    private String thumbnail;
}