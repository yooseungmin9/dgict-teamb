package com.bgroup.news.controller;

import com.bgroup.news.dto.MemberDoc;
import com.bgroup.news.service.MemberService;
import jakarta.servlet.http.HttpSession;
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

    @GetMapping({"/", "/dashboard"})
    public String index(Model model) {
        model.addAttribute("mainPageTitle", "경제 뉴스 분석 대시보드");
        model.addAttribute("todayNews", "오늘의 뉴스");
        return "pages/dashboard";
    }

    @GetMapping("/news")
    public String news(Model model) {
        return "pages/news";
    }

    @GetMapping("/global")
    public String global(Model model) {
        return "pages/global";
    }

    @GetMapping("/trends")
    public String showTrendsPage() {
        // 그냥 templates/trends.html 반환
        return "pages/trends";
    }

    @GetMapping("/login")
    public String login(Model model) {
        return "pages/login";
    }

    @PostMapping("/login")
    public String login(@RequestParam String id,
                        @RequestParam String password,
                        HttpSession session,
                        Model model) {
        return memberService.authenticate(id, password)
                .map(m -> {
                    session.setAttribute("loginUser", m);
                    session.setAttribute("admin", m.getAdmin());
                    session.setMaxInactiveInterval(3600);
                    return "redirect:/pages/";
                })
                .orElseGet(() -> {
                    model.addAttribute("error", "아이디 또는 비밀번호가 올바르지 않습니다.");
                    return "pages/login";
                });
    }

    @PostMapping("/logout")
    public String logout(HttpSession session) {
        session.invalidate();
        return "redirect:/pages/dashboard";
    }

    @GetMapping("/chart")
    public String chartPage() {
        return "pages/chart";
    }

    @GetMapping("/members")
    public String membersPage(Model model) {
        model.addAttribute("members", memberService.listAll());
        return "pages/members";
    }

    @GetMapping("/signup")
    public String signupPage(Model model) {
        model.addAttribute("member", new MemberDoc());
        return "pages/signup";
    }

    @PostMapping("/signup")
    public String signupSubmit(@ModelAttribute MemberDoc member) {
        memberService.saveMember(member);
        return "redirect:/pages/members";
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
