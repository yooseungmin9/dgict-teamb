package com.bgroup.news.controller;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;
import org.springframework.web.reactive.function.client.WebClient;

@Controller
public class SentimentController {

    private final WebClient sentimentClient;

    public SentimentController(@Qualifier("sentimentClient") WebClient sentimentClient) {
        this.sentimentClient = sentimentClient;
    }

    // ✅ 페이지 렌더링 (Thymeleaf)
    @GetMapping("/pages/sentiment")
    public String getSentimentPage(@RequestParam(required = false) Integer days, Model model) {
        // 페이지는 그냥 템플릿만 반환 (데이터는 JS에서 /api/sentiment 호출)
        model.addAttribute("defaultDays", days != null ? days : 7);
        return "pages/sentiment";
    }

    // ✅ API 프록시 (JSON 반환)
    @GetMapping("/api/sentiment")
    @ResponseBody
    public String getSentimentApi(@RequestParam(required = false) Integer days) {
        int d = (days != null ? days : 7);
        return sentimentClient.get()
                .uri(uri -> uri.path("/sentiment").queryParam("days", d).build())
                .retrieve()
                .bodyToMono(String.class)
                .block();
    }
}
