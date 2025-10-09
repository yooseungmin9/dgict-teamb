package com.bgroup.news.origin.controller;

import com.bgroup.news.member.service.MemberService;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

@Controller
@RequestMapping("pages")
public class PageController {

    private final MemberService memberService;

    public PageController(MemberService memberService) {
        this.memberService = memberService;
    }

    @GetMapping("/news")
    public String news(Model model) {
        return "pages/news";
    }

    @GetMapping("/chart")
    public String chartPage() {
        return "pages/chart";
    }

    @GetMapping("/account")
    public String account(Model model) {

        return "pages/account";
    }

    @GetMapping("/youtube_opinion")
    public String youtube_opinion(Model model) {

        return "pages/youtube_opinion";
    }
}
