package com.bgroup.news.dashboard.dto;

import lombok.*;

@Getter @Setter @Builder
@AllArgsConstructor @NoArgsConstructor
public class EmoaScoreResponse {
    private String date;
    private String weekday;
    private Double avg;
    private Double delta;
}
