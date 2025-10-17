package com.bgroup.news.analysis.service;

import com.bgroup.news.analysis.dto.AnalysisResponseDto;
import com.bgroup.news.analysis.dto.VideoDetailDto;
import com.bgroup.news.analysis.dto.VideoSummaryDto;
import com.bgroup.news.analysis.repository.VideoRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import org.springframework.web.server.ResponseStatusException;
import reactor.util.retry.Retry;

import java.time.Duration;
import java.util.*;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Slf4j
public class YoutubeService {

    private final VideoRepository videoRepo;

    @Qualifier("analysisClient")
    private final WebClient analysisClient;

    private static final int LIST_SIZE = 50;
    private static final Duration TIMEOUT = Duration.ofSeconds(10);

    public List<VideoSummaryDto> listVideos() {
        var page = videoRepo.findAll(
                org.springframework.data.domain.PageRequest.of(0, LIST_SIZE,
                        org.springframework.data.domain.Sort.by(org.springframework.data.domain.Sort.Direction.DESC, "publishedAt"))
        );
        return page.getContent().stream()
                .map(v -> VideoSummaryDto.builder()
                        .video_id(s(v.getVideoId()))
                        .title(s(v.getTitle()))
                        .thumbnail(s(v.getThumbnailUrl()))
                        .build())
                .collect(Collectors.toList());
    }

    public VideoDetailDto getVideoDetail(String videoId) {
        var v = Optional.ofNullable(videoRepo.findByVideoId(videoId))
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "video not found"));

        return VideoDetailDto.builder()
                .video_id(s(v.getVideoId()))
                .title(s(v.getTitle()))
                .thumbnail(s(v.getThumbnailUrl()))
                .video_url("https://www.youtube.com/embed/" + s(v.getVideoId()) + "?rel=0")
                .published_at(v.getPublishedAt() != null ? v.getPublishedAt().toString() : null)
                .views(nz(v.getViewCount()))
                .comments(nz(v.getCommentCount()))
                .build();
    }

    public AnalysisResponseDto getAnalysis(String videoId) {
        try {
            log.info("[YoutubeService] FastAPI 요청 시작: videoId={}", videoId);

            Map<String, Object> res = analysisClient.get()
                    .uri(uriBuilder -> uriBuilder
                            .path("/analysis/{id}")
                            .queryParam("topn", 100)
                            .queryParam("limit", 1000)
                            .build(videoId))
                    .retrieve()
                    .bodyToMono(new ParameterizedTypeReference<Map<String, Object>>() {})
                    .timeout(TIMEOUT)
                    .retryWhen(Retry.backoff(1, Duration.ofMillis(300)))
                    .block(TIMEOUT);

            if (res == null || res.isEmpty()) {
                log.warn("[YoutubeService] FastAPI 응답이 비어 있음 (videoId={})", videoId);
                throw new ResponseStatusException(HttpStatus.BAD_GATEWAY, "FastAPI returned empty response");
            }

            @SuppressWarnings("unchecked")
            Map<String, Integer> sentiment = (Map<String, Integer>) res.getOrDefault("sentiment", Map.of());
            @SuppressWarnings("unchecked")
            List<Map<String, Object>> wcList = (List<Map<String, Object>>) res.getOrDefault("wordcloud", List.of());
            List<com.bgroup.news.analysis.dto.WordItem> wordcloud = wcList.stream()
                    .map(m -> new com.bgroup.news.analysis.dto.WordItem(
                            String.valueOf(m.get("text")),
                            ((Number) m.getOrDefault("count", 0)).intValue()))
                    .collect(Collectors.toList());

            @SuppressWarnings("unchecked")
            List<Map<String, Object>> cmts = (List<Map<String, Object>>) res.getOrDefault("comments", List.of());
            List<com.bgroup.news.analysis.dto.CommentItem> samples = cmts.stream()
                    .map(m -> new com.bgroup.news.analysis.dto.CommentItem(
                            String.valueOf(m.get("text")),
                            String.valueOf(m.get("emotion"))))
                    .collect(Collectors.toList());

            String summary = String.valueOf(res.getOrDefault("summary", "분석 결과가 없습니다."));

            return AnalysisResponseDto.builder()
                    .sentiment(sentiment)
                    .wordcloud(wordcloud)
                    .summary(summary)
                    .comments(samples)
                    .build();

        } catch (WebClientResponseException e) {
            log.error("[YoutubeService] FastAPI 응답 오류: {} body={}", e.getStatusCode(), e.getResponseBodyAsString());
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
                    "FastAPI error: " + e.getStatusCode());
        } catch (Exception e) {
            log.error("[YoutubeService] FastAPI 요청 실패: {}", e.getMessage(), e);
            throw new ResponseStatusException(HttpStatus.BAD_GATEWAY,
                    "FastAPI communication error: " + e.getMessage());
        }
    }

    private static String s(String x) { return x == null ? "" : x.trim(); }
    private static long nz(Long x) { return x == null ? 0L : x; }
}
