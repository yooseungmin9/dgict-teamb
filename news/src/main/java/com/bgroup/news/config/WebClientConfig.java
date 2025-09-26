package com.bgroup.news.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class WebClientConfig {

    @Bean
    public WebClient fastApiClient(@Value("${fastapi.base-url}") String baseUrl) {
        // (선택) 응답 바이트 크게 받을 때 메모리 상한 조정
        ExchangeStrategies strategies = ExchangeStrategies.builder()
                .codecs(c -> c.defaultCodecs().maxInMemorySize(2 * 1024 * 1024)) // 2MB
                .build();

        return WebClient.builder()
                .baseUrl(baseUrl)
                .exchangeStrategies(strategies)
                .build();
    }
}
