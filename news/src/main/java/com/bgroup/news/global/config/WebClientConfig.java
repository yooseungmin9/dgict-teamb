package com.bgroup.news.global.config;

import io.netty.channel.ChannelOption;
import io.netty.handler.timeout.ReadTimeoutHandler;
import io.netty.handler.timeout.WriteTimeoutHandler;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.ExchangeFilterFunction;
import org.springframework.web.reactive.function.client.ExchangeFilterFunctions;
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
        HttpClient httpClient = HttpClient.create()
                .responseTimeout(Duration.ofSeconds(8)) // 기본 응답 타임아웃(요청별로도 다시 걸어줌)
                .option(io.netty.channel.ChannelOption.CONNECT_TIMEOUT_MILLIS, 2000)
                .doOnConnected(conn -> conn
                        .addHandlerLast(new ReadTimeoutHandler(8))
                        .addHandlerLast(new WriteTimeoutHandler(8)));

        return baseWebClientBuilder
                .baseUrl(baseUrl == null ? "" : baseUrl.trim()) // 예: http://localhost:8004
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .filter(logOnError()) // 선택: 에러 로깅
                .build();
    }

    private ExchangeFilterFunction logOnError() {
        return ExchangeFilterFunction.ofResponseProcessor(resp -> {
            if (resp.statusCode().isError()) {
                int code = resp.statusCode().value();
                String text = resp.statusCode().toString(); // "404 NOT_FOUND"
                return resp.bodyToMono(String.class)
                        .defaultIfEmpty("")
                        .doOnNext(body -> System.err.println(
                                "[youtubeClient] HTTP " + code + " " + text +
                                        (body.isEmpty() ? "" : " | body=" + body)))
                        .thenReturn(resp);
            }
            return reactor.core.publisher.Mono.just(resp);
        });
    }

    @Bean("trendClient")
    public WebClient trendClient(
            WebClient.Builder builder,
            @Value("${fastapi.trend}") String baseUrl
    ) {
        return builder
                .baseUrl(baseUrl.trim())
                .clientConnector(new ReactorClientHttpConnector(
                        HttpClient.create()
                                .responseTimeout(Duration.ofSeconds(5))
                                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 2000)
                ))
                .filter(ExchangeFilterFunctions.statusError(HttpStatusCode::isError,
                        r -> new IllegalStateException("FastAPI error: " + r.statusCode())))
                .build();
    }

    @Bean("sentiClient")
    public WebClient sentiClient(WebClient.Builder builder,
                                 @Value("${fastapi.senti}") String baseUrl) {
        HttpClient http = HttpClient.create()
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 2000)
                .responseTimeout(Duration.ofSeconds(4))
                .doOnConnected(conn -> conn
                        .addHandlerLast(new ReadTimeoutHandler(4))
                        .addHandlerLast(new WriteTimeoutHandler(4)));

        return builder
                .baseUrl(baseUrl.trim())
                .clientConnector(new ReactorClientHttpConnector(http))
                .build();
    }

    @Bean("analysisClient")
    public WebClient analysisClient(WebClient.Builder b, @Value("${fastapi.analysis}") String baseUrl) {
        HttpClient http = HttpClient.create()
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 5_000)
                .responseTimeout(Duration.ofSeconds(15))
                .doOnConnected(c -> c.addHandlerLast(new ReadTimeoutHandler(15))
                        .addHandlerLast(new WriteTimeoutHandler(15)));
        return b.baseUrl(baseUrl.trim())
                .clientConnector(new ReactorClientHttpConnector(http))
                .exchangeStrategies(ExchangeStrategies.builder()
                        .codecs(c -> c.defaultCodecs().maxInMemorySize(10 * 1024 * 1024)) // 10MB
                        .build())
                .build();
    }
}
