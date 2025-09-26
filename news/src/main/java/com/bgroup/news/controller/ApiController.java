package com.bgroup.news.controller;

import com.bgroup.news.service.ChatbotService;
import com.bgroup.news.service.KeywordService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.util.Map;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api")
public class ApiController {

    private final ChatbotService chatbotService;
    private final KeywordService keywordService;

    // ----------- Chatbot API -----------
    @PostMapping("/chat")
    public ResponseEntity<?> chat(@RequestBody Map<String, Object> body) {
        String result = chatbotService.sendChat(body);
        return ResponseEntity.ok(result);
    }

    @PostMapping("/reset")
    public ResponseEntity<?> reset() {
        String result = chatbotService.reset();
        return ResponseEntity.ok(result);
    }

    // ----------- Keywords API -----------
    @GetMapping("/keywords")
    public Mono<String> getKeywords() {
        return keywordService.fetchKeywords();
    }
}
