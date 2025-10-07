package com.bgroup.news.global.config;

import io.netty.channel.ChannelOption;
import io.netty.handler.timeout.ReadTimeoutHandler;
import io.netty.handler.timeout.WriteTimeoutHandler;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;

import java.time.Duration;
import java.util.concurrent.TimeUnit;

@Configuration
@RequiredArgsConstructor
public class WebClientConfig {

    private static final int MAX_IN_MEMORY_SIZE = 10 * 1024 * 1024;

    @Bean
    public ExchangeStrategies exchangeStrategies() {
        return ExchangeStrategies.builder()
                .codecs(config -> config.defaultCodecs().maxInMemorySize(MAX_IN_MEMORY_SIZE))
                .build();
    }

    @Bean
    public ReactorClientHttpConnector reactorClientHttpConnector() {
        HttpClient httpClient = HttpClient.create()
                .compress(true)
                .responseTimeout(Duration.ofSeconds(15))
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 5000)
                .doOnConnected(conn -> conn
                        .addHandlerLast(new ReadTimeoutHandler(10, TimeUnit.SECONDS))
                        .addHandlerLast(new WriteTimeoutHandler(10, TimeUnit.SECONDS))
                )
                .wiretap("com.bgroup.news.fastapi", io.netty.handler.logging.LogLevel.DEBUG);

        return new ReactorClientHttpConnector(httpClient);
    }

    @Bean
    public WebClient.Builder baseWebClientBuilder(
            ExchangeStrategies strategies,
            ReactorClientHttpConnector connector
    ) {
        return WebClient.builder()
                .defaultHeader(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .exchangeStrategies(strategies)
                .clientConnector(connector);
    }

    @Bean
    public WebClient fastApiClient(
            WebClient.Builder baseWebClientBuilder,
            @Value("${fastapi.base-url}") String baseUrl
    ) {
        return baseWebClientBuilder.baseUrl(baseUrl.trim()).build();
    }

    @Bean("chatClient")
    public WebClient chatClient(
            WebClient.Builder baseWebClientBuilder,
            @Value("${fastapi.chat}") String baseUrl
    ) {
        return baseWebClientBuilder.baseUrl(baseUrl.trim()).build();
    }

    @Bean("youtubeClient")
    public WebClient youtubeClient(
            WebClient.Builder baseWebClientBuilder,
            @Value("${fastapi.youtube}") String baseUrl
    ) {
        return baseWebClientBuilder.baseUrl(baseUrl.trim()).build();
    }

    @Bean("trendClient")
    public WebClient trendClient(
            WebClient.Builder baseWebClientBuilder,
            @Value("${fastapi.trend}") String baseUrl
    ) {
        return baseWebClientBuilder.baseUrl(baseUrl.trim()).build();
    }

    @Bean("sentiClient")
    public WebClient sentiClient(
            WebClient.Builder baseWebClientBuilder,
            @Value("${fastapi.senti}") String baseUrl
    ) {
        return baseWebClientBuilder.baseUrl(baseUrl.trim()).build();
    }

    @Bean("analysisClient")
    public WebClient analysisClient(
            WebClient.Builder baseWebClientBuilder,
            @Value("${fastapi.analysis}") String baseUrl
    ) {
        return baseWebClientBuilder.baseUrl(baseUrl.trim()).build();
    }
}
