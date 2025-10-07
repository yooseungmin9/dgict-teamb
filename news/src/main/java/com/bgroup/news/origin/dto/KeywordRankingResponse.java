package com.bgroup.news.origin.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class KeywordRankingResponse {
    private int rank;        // 순위
    private String keyword;  // 키워드
    private String category; // 카테고리
    private int count;       // 언급량
}
