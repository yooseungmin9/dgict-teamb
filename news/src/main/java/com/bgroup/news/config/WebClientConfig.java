package com.bgroup.news.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;

import java.time.Duration;

@Configuration
public class WebClientConfig {

    private ExchangeStrategies strategies() {
        return ExchangeStrategies.builder()
                .codecs(c -> c.defaultCodecs().maxInMemorySize(2 * 1024 * 1024))
                .build();
    }

    // 기본 클라이언트 (8000)
    @Bean
    public WebClient fastApiClient(@Value("${fastapi.base-url}") String baseUrl) {
        return WebClient.builder()
                .baseUrl(baseUrl.trim())
                .exchangeStrategies(strategies())
                .build();
    }

    @Bean("sentimentClient") // 8001
    public WebClient sentimentClient(@Value("${fastapi.sentiment}") String baseUrl) {
        return WebClient.builder()
                .baseUrl(baseUrl.trim())
                .exchangeStrategies(strategies())
                .build();
    }

    @Bean("chatClient") // 8002
    public WebClient chatClient(@Value("${fastapi.chat}") String baseUrl) {
        return WebClient.builder()
                .baseUrl(baseUrl.trim())
                .exchangeStrategies(strategies())
                .build();
    }

    @Bean("booksClient") // 8003
    public WebClient booksClient(@Value("${fastapi.book}") String baseUrl) {
        return WebClient.builder()
                .baseUrl(baseUrl.trim())
                .exchangeStrategies(strategies())
                .build();
    }

    @Bean("youtubeClient")
    public WebClient youtubeClient(@Value("${fastapi.youtube}") String baseUrl) {
        return WebClient.builder()
                .baseUrl(baseUrl.trim())
                .exchangeStrategies(strategies())
                .build();
    }

    @Bean("trendClient")
    public WebClient trendClient(@Value("${fastapi.trend}") String baseUrl) {
        return WebClient.builder()
                .baseUrl(baseUrl.trim())
                .exchangeStrategies(strategies())
                .build();
    }
}

