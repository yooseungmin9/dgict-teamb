package com.bgroup.news.member.controller;

import com.bgroup.news.member.domain.MemberDoc;
import com.bgroup.news.member.dto.SignupRequest;
import com.bgroup.news.member.service.MemberService;
import org.springframework.data.domain.Page;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

@Controller
@RequestMapping("/member")
public class MemberController {

    private final MemberService memberService;

    public MemberController(MemberService memberService) {
        this.memberService = memberService;
    }

    // 회원 목록 페이지
    @GetMapping("/list")
    public String listMembers(@RequestParam(defaultValue = "0") int page,
                              @RequestParam(defaultValue = "20") int size,
                              Model model) {
        Page<MemberDoc> memberPage = memberService.list(page, size);
        model.addAttribute("members", memberPage.getContent());
        model.addAttribute("currentPage", page);
        model.addAttribute("totalPages", memberPage.getTotalPages());
        return "member/list";
    }

    // 회원 등록 폼
    @GetMapping("/signup")
    public String signupPage(Model model) {
        model.addAttribute("member", new MemberDoc());
        return "member/signup";
    }

    // 회원 등록 처리
    @PostMapping("/signup")
    public String signupSubmit(@ModelAttribute SignupRequest req) {
        memberService.register(req);
        return "redirect:/pages/dashboard";
    }
}
