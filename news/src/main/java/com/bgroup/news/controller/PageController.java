package com.bgroup.news.controller;

import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import reactor.core.publisher.Mono;

@RequestMapping("pages")
@Controller
public class PageController {
    @GetMapping({"/", "/dashboard"})
    public String index(Model model){
        model.addAttribute("mainPageTitle","경제 뉴스 분석 대시보드");
        model.addAttribute("todayNews","오늘의 뉴스");
        return "pages/dashboard";
    }

    @GetMapping("/news")
    public String news(Model model){
        return "pages/news";
    }

    @GetMapping("/sentiment")
    public String sentiment(Model model){
        return "pages/sentiment";
    }

    @GetMapping("/global")
    public String global(Model model){
        return "pages/global";
    }

    @GetMapping("/trends")
    public String trends(Model model){
        return "pages/trends";
    }

    @GetMapping("/recommendations")
    public String recommendations(Model model){
        return "pages/recommendations";
    }

    @GetMapping("/login")
    public String login(Model model){
        return "pages/login";
    }

    @GetMapping("/chart")
    public String chartPage() {
        return "pages/chart";  // templates/chart.html 반환
    }

    @GetMapping("/chat")
    public String chatPage() {
        return "pages/chat"; // src/main/resources/templates/chat.html
    }
}

