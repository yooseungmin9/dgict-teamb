package com.bgroup.news.dashboard.dto;

import lombok.Data;

import java.util.List;
import java.util.Map;

@Data
public class SentimentResponse {
    private List<String> labels;
    private Map<String, List<Integer>> series;
}