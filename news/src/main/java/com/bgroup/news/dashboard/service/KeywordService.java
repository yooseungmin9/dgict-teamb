package com.bgroup.news.dashboard.service;

import com.bgroup.news.dashboard.dto.HotTopicResponse;
import com.bgroup.news.dashboard.dto.KeywordRankingResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;
import java.util.*;

@Service
@RequiredArgsConstructor
public class KeywordService {
    @Qualifier("trendClient")
    private final WebClient trendClient;

    public List<KeywordRankingResponse> fetchRanking(String category, int days) {
        return trendClient.get()
                .uri(u -> u.path("/keywords/ranking")
                        .queryParam("category", category)
                        .queryParam("days", days)
                        .build())
                .retrieve()
                .bodyToFlux(KeywordRankingResponse.class)
                .collectList()
                .block();
    }
}
