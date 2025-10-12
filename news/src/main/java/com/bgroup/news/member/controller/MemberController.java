package com.bgroup.news.member.controller;

import com.bgroup.news.member.domain.MemberDoc;
import com.bgroup.news.member.dto.PreferenceSurveyRequest;
import com.bgroup.news.member.dto.SignupRequest;
import com.bgroup.news.member.service.MemberService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
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
    public String signupSubmit(@ModelAttribute SignupRequest req, HttpSession session) {
        // 1) 가입
        MemberDoc saved = memberService.register(req);

        // 2) 자동 로그인 (세션에 저장)
        session.setAttribute("loginUser", saved);
        session.setAttribute("admin", saved.getAdmin());
        session.setMaxInactiveInterval(3600); // 선택

        // 3) 리다이렉트
        return "redirect:/pages/dashboard";
    }

    // 마이페이지(계정 정보)
    @GetMapping("/account")
    public String account(HttpServletRequest request, Model model) {
        boolean ajax = "XMLHttpRequest".equalsIgnoreCase(request.getHeader("X-Requested-With"));
        return ajax ? "member/account :: accountPanel" : "member/account";
    }

    // 관리자 페이지
    @GetMapping("/admin")
    public String adminPage(Model model) {
        return "member/admin";
    }

    // 키워드 기반 선호 저장 (/member/interests)
    @PostMapping(
            path = "/interests",
            consumes = MediaType.APPLICATION_JSON_VALUE
    )
    @ResponseBody
    public ResponseEntity<Void> saveInterests(
            @RequestBody(required = false) List<String> keywords,
            @SessionAttribute(value = "loginUser", required = false) MemberDoc me,
            HttpSession session
    ) {
        if (me == null) {
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build(); // 401
        }

        memberService.updateInterests(
                me.getId(),
                (keywords == null ? Collections.emptyList() : keywords)
        );

        // ✅ 세션 최신화 (화면에서 즉시 최신값 사용)
        MemberDoc refreshed = memberService.getOrThrow(me.getId());
        session.setAttribute("loginUser", refreshed);

        return ResponseEntity.noContent().build(); // 204
    }

    // 설문 메타 저장 (/member/preferences)
    @PostMapping(
            path = "/preferences",
            consumes = MediaType.APPLICATION_JSON_VALUE
    )
    @ResponseBody
    public ResponseEntity<Void> savePreferenceSurvey(
            @RequestBody PreferenceSurveyRequest req,
            @SessionAttribute(value = "loginUser", required = false) MemberDoc me,
            HttpSession session
    ){
        if (me == null) return ResponseEntity.status(HttpStatus.UNAUTHORIZED).build(); // 401

        memberService.applyPreferenceSurvey(me.getId(), req);

        // ✅ 세션 최신화
        MemberDoc refreshed = memberService.getOrThrow(me.getId());
        session.setAttribute("loginUser", refreshed);

        return ResponseEntity.noContent().build(); // 204
    }
}
