package com.bgroup.news.member.controller;

import com.bgroup.news.member.domain.MemberDoc;
import com.bgroup.news.member.dto.SignupRequest;
import com.bgroup.news.member.service.MemberService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.data.domain.Page;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

import java.util.Collections;
import java.util.List;

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
        model.addAttribute("member", new SignupRequest());
        return "member/signup";
    }

    // 회원 등록 처리
    @PostMapping("/signup")
    public String signupSubmit(@ModelAttribute SignupRequest req) {
        memberService.register(req);
        return "redirect:/pages/dashboard";
    }

    @GetMapping("/account")
    public String account(HttpServletRequest request, Model model) {
        boolean ajax = "XMLHttpRequest".equalsIgnoreCase(request.getHeader("X-Requested-With"));
        // model.addAttribute("me", memberService.current()); // 필요시
        return ajax ? "member/account :: accountPanel" : "member/account";
    }

    @GetMapping("/admin")
    public String adminPage(Model model) {
        return "member/admin";
    }

    @PostMapping(
            path = "/interests",
            consumes = MediaType.APPLICATION_JSON_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE
    )
    @ResponseBody
    public ResponseEntity<Void> saveInterests(
            @RequestBody(required = false) List<String> keywords,
            @SessionAttribute(value = "loginUser", required = false) MemberDoc me
    ) {
        if (me == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build(); // 401
        }

        memberService.updateInterests(
                me.getId(),
                (keywords == null ? Collections.emptyList() : keywords)
        );

        return ResponseEntity.ok().build();
    }
}
