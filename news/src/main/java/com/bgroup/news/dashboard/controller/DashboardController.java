package com.bgroup.news.dashboard.controller;

import com.bgroup.news.dashboard.service.DashboardService;
import com.bgroup.news.origin.dto.KeywordRankingResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.List;

@Controller
@RequiredArgsConstructor
public class DashboardController {

    private final DashboardService dashboardService;

    @GetMapping({"/", "/dashboard"})
    public String dashboard(Model model,
                            @RequestParam(defaultValue = "30") int days,
                            @RequestParam(defaultValue = "date") String time_unit,
                            @RequestParam(defaultValue = "10") int topN,
                            @RequestParam(required = false) String category) {

        String categoryTrendsJson = dashboardService
                .fetchCategoryTrends(days, time_unit)
                .block(); // 간단히 동기화 (대시보드 초기 로드)

        List<KeywordRankingResponse> ranking =
                dashboardService.fetchKeywordRanking(topN, category, days);

        model.addAttribute("mainPageTitle", "경제 뉴스 분석 대시보드");
        model.addAttribute("todayNews", "오늘의 뉴스");
        model.addAttribute("categoryTrendsJson", categoryTrendsJson);
        model.addAttribute("keywordRanking", ranking);
        model.addAttribute("days", days);
        model.addAttribute("timeUnit", time_unit);
        model.addAttribute("topN", topN);
        model.addAttribute("category", category);

        return "pages/dashboard";
    }
}
