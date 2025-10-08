package com.bgroup.news.dashboard.service;

import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.util.Map;

@Service
@RequiredArgsConstructor
public class TrendService {

    @Qualifier("trendClient")
    private final WebClient trendClient;  // baseUrl = http://localhost:8006

    /** FastAPI(8006)에서 카테고리 트렌드 가져오기 */
    public Map<String, Object> getCategoryTrends(int days) {
        return trendClient.get()
                .uri(uri -> uri.path("/category-trends")
                        .queryParam("days", days)
                        .build())
                .retrieve()
                .bodyToMono(new ParameterizedTypeReference<Map<String,Object>>() {})
                .block();
    }
}
