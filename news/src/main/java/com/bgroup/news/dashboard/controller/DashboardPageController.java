package com.bgroup.news.dashboard.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;

@Controller
@RequestMapping("pages")
public class DashboardPageController {
    @GetMapping({"/", "/dashboard"})
    public String showDashboard() {
        return "pages/dashboard"; // templates/pages/dashboard.html
    }
}
