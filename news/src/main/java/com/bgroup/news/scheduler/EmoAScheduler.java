package com.bgroup.news.scheduler;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import java.util.Map;

@Component
public class EmoAScheduler {

    private final RestTemplate http = new RestTemplate();

    @Scheduled(cron = "0 0 7 * * *", zone = "Asia/Seoul")
    public void updateSentiment() {
        try {
            Map<?,?> res = http.getForObject("http://127.0.0.1:8000/sentiment/today", Map.class);
            System.out.println("[자동 감성 업데이트] " + res);
        } catch (Exception e) {
            System.out.println("감성 업데이트 실패: " + e.getMessage());
        }
    }
}
