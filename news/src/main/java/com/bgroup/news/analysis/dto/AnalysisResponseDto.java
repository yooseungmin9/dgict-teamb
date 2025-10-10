package com.bgroup.news.analysis.dto;

import java.util.List;
import java.util.Map;
import lombok.*;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class AnalysisResponseDto {
    private Map<String,Integer> sentiment;
    private List<WordItem> wordcloud;
    private String summary;
    private List<CommentItem> comments;
}