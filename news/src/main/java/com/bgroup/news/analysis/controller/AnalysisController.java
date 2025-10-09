package com.bgroup.news.analysis.controller;

import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

@Controller
@RequestMapping("pages")
public class AnalysisController {

    @GetMapping("/youtube_opinion")
    public String youtube_opinion(Model model) {
        return "pages/youtube_opinion";
    }
}
