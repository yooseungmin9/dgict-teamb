package com.bgroup.news.dashboard.dto;

import lombok.Data;

import java.util.List;
import java.util.Map;

@Data
public class HotTopicResponse {
    private List<String> dates;
    private Map<String, List<Integer>> categories;
}