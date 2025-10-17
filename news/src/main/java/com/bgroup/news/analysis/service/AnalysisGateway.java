package com.bgroup.news.analysis.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.util.retry.Retry;

import java.io.IOException;
import java.net.URI;
import java.time.Duration;
import java.util.Collections;
import java.util.List;
import java.util.Map;

@Service
@Slf4j
public class AnalysisGateway {

    private static final Duration REQ_TIMEOUT   = Duration.ofSeconds(12);
    private static final Duration BLOCK_TIMEOUT = Duration.ofSeconds(12);

    private final WebClient client;

    public AnalysisGateway(@Qualifier("analysisClient") WebClient client) {
        this.client = client;
    }

    public List<Map<String, Object>> fetchVideos() {
        List<Map<String, Object>> body = get(
                "/videos",
                new ParameterizedTypeReference<List<Map<String, Object>>>() {}
        );
        return body != null ? body : Collections.emptyList();
    }

    public Map<String, Object> fetchVideoDetail(String videoId) {
        Map<String, Object> body = get(
                "/videos/{id}",
                new ParameterizedTypeReference<Map<String, Object>>() {},
                videoId
        );
        return body != null ? body : Collections.emptyMap();
    }

    public Map<String, Object> fetchAnalysis(String videoId, int topn) {
        Map<String, Object> body = get(
                b -> b.path("/analysis/{id}").queryParam("topn", topn).build(videoId),
                new ParameterizedTypeReference<Map<String, Object>>() {}
        );
        return body != null ? body : Collections.emptyMap();
    }

    private <T> T get(String path, ParameterizedTypeReference<T> typeRef, Object... uriVars) {
        try {
            return client.get()
                    .uri(path, uriVars)
                    .retrieve()
                    .onStatus(HttpStatusCode::is4xxClientError, resp ->
                            resp.bodyToMono(String.class).defaultIfEmpty("")
                                    .doOnNext(b -> log.warn("[AnalysisGateway] 4xx: {} body={}", resp.statusCode(), b))
                                    .then(resp.createException()))
                    .onStatus(HttpStatusCode::is5xxServerError, resp ->
                            resp.bodyToMono(String.class).defaultIfEmpty("")
                                    .doOnNext(b -> log.error("[AnalysisGateway] 5xx: {} body={}", resp.statusCode(), b))
                                    .then(resp.createException()))
                    .bodyToMono(typeRef)
                    .retryWhen(Retry.backoff(2, Duration.ofMillis(300)).filter(this::isTransient))
                    .timeout(REQ_TIMEOUT)
                    .block(BLOCK_TIMEOUT);
        } catch (WebClientResponseException e) {
            log.error("[AnalysisGateway] ResponseException {} body={}", e.getStatusCode(), e.getResponseBodyAsString());
            throw e;
        } catch (WebClientRequestException e) {
            log.error("[AnalysisGateway] RequestException: {}", e.getMessage(), e);
            throw e;
        }
    }

    private <T> T get(java.util.function.Function<org.springframework.web.util.UriBuilder, URI> uriFn,
                      ParameterizedTypeReference<T> typeRef) {
        try {
            return client.get()
                    .uri(uriFn)
                    .retrieve()
                    .onStatus(HttpStatusCode::is4xxClientError, resp ->
                            resp.bodyToMono(String.class).defaultIfEmpty("")
                                    .doOnNext(b -> log.warn("[AnalysisGateway] 4xx: {} body={}", resp.statusCode(), b))
                                    .then(resp.createException()))
                    .onStatus(HttpStatusCode::is5xxServerError, resp ->
                            resp.bodyToMono(String.class).defaultIfEmpty("")
                                    .doOnNext(b -> log.error("[AnalysisGateway] 5xx: {} body={}", resp.statusCode(), b))
                                    .then(resp.createException()))
                    .bodyToMono(typeRef)
                    .retryWhen(Retry.backoff(2, Duration.ofMillis(300)).filter(this::isTransient))
                    .timeout(REQ_TIMEOUT)
                    .block(BLOCK_TIMEOUT);
        } catch (WebClientResponseException e) {
            log.error("[AnalysisGateway] ResponseException {} body={}", e.getStatusCode(), e.getResponseBodyAsString());
            throw e;
        } catch (WebClientRequestException e) {
            log.error("[AnalysisGateway] RequestException: {}", e.getMessage(), e);
            throw e;
        }
    }

    private boolean isTransient(Throwable t) {
        if (t instanceof WebClientRequestException) {
            Throwable cause = t.getCause();
            return (cause instanceof IOException) || cause == null;
        }
        if (t instanceof WebClientResponseException e) {
            return e.getStatusCode().is5xxServerError();
        }
        return false;
    }
}
