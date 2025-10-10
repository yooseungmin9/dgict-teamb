package com.bgroup.news.analysis.controller;

import com.bgroup.news.analysis.dto.AnalysisResponseDto;
import com.bgroup.news.analysis.dto.VideoDetailDto;
import com.bgroup.news.analysis.dto.VideoSummaryDto;
import com.bgroup.news.analysis.service.YoutubeService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api")
@RequiredArgsConstructor
public class YoutubeController {

    private final YoutubeService youtubeService;

    /**
     * 🎥 영상 목록 (좌측 썸네일 리스트)
     */
    @GetMapping("/videos")
    public ResponseEntity<List<VideoSummaryDto>> listVideos() {
        List<VideoSummaryDto> list = youtubeService.listVideos();
        return ResponseEntity.ok(list);
    }

    /**
     * 🎬 영상 상세 (제목, 조회수, 댓글수 등)
     */
    @GetMapping("/videos/{videoId}")
    public ResponseEntity<VideoDetailDto> getVideoDetail(@PathVariable String videoId) {
        VideoDetailDto detail = youtubeService.getVideoDetail(videoId);
        return ResponseEntity.ok(detail);
    }

    /**
     * 📊 영상 분석 (FastAPI 연동)
     * JS: fetch("/api/analysis/{videoId}?topn=100&limit=1000")
     */
    @GetMapping("/analysis/{videoId}")
    public ResponseEntity<AnalysisResponseDto> getAnalysis(
            @PathVariable String videoId,
            @RequestParam(required = false) Integer limit,
            @RequestParam(defaultValue = "100") int topn) {

        // limit은 현재 YoutubeService 내부에서 1000으로 고정되어 있으므로 무시 가능
        AnalysisResponseDto analysis = youtubeService.getAnalysis(videoId);
        return ResponseEntity.ok(analysis);
    }
}
