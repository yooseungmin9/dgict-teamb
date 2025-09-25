package com.example.news.basic;

import java.time.LocalDate;
import java.util.*;
import java.util.stream.IntStream;

import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
public class BasicController {
    @GetMapping({"/", "/dashboard"})
    public String index(Model model){
        model.addAttribute("mainPageTitle","경제 뉴스 분석 대시보드");
        model.addAttribute("todayNews","오늘의 뉴스");

        return "dashboard";
    }

    @GetMapping("/news")
    public String news(Model model){

        return "news";
    }

    @GetMapping("/sentiment")
    public String sentiment(Model model){

        return "sentiment";
    }

    @GetMapping("/global")
    public String global(Model model){

        return "global";
    }

    @GetMapping("/trends")
    public String trends(Model model){

        return "trends";
    }

    @GetMapping("/chatbot")
    public String chatbot(Model model){

        return "chatbot";
    }

    @GetMapping("/recommendations")
    public String recommendations(Model model){

        return "recommendations";
    }

    @GetMapping("/login")
    public String login(Model model){

        return "login";
    }
}
