package com.bgroup.news.member.controller;

import com.bgroup.news.member.domain.MemberDoc;
import com.bgroup.news.member.dto.LoginRequest;
import com.bgroup.news.member.service.MemberService;
import jakarta.servlet.http.HttpSession;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@Controller
@RequestMapping("/auth")
public class AuthController {

    private final MemberService memberService;

    public AuthController(MemberService memberService) {
        this.memberService = memberService;
    }

    // ✅ 로그인 페이지 (GET)
    @GetMapping("/login")
    public String loginPage() {
        return "/member/login";
    }

    // ✅ 로그인 요청 (POST)
    @PostMapping("/login")
    @ResponseBody
    public ResponseEntity<?> login(@RequestBody LoginRequest body, HttpSession session) {
        return memberService.authenticate(body.getId(), body.getPassword())
                .map(m -> {
                    session.setAttribute("loginUser", m);
                    session.setAttribute("admin", m.getAdmin());
                    session.setMaxInactiveInterval(3600);
                    return ResponseEntity.ok(Map.of(
                            "id", m.getId(),
                            "name", m.getName(),
                            "admin", m.getAdmin()
                    ));
                })
                .orElse(ResponseEntity.status(401)
                        .body(Map.of("error", "INVALID_CREDENTIALS")));
    }

    // ✅ 웹 로그인 (폼 방식)
    @PostMapping("/login/form")
    public String loginForm(@RequestParam String id,
                            @RequestParam String password,
                            HttpSession session,
                            Model model) {
        return memberService.authenticate(id, password)
                .map(m -> {
                    session.setAttribute("loginUser", m);
                    session.setAttribute("admin", m.getAdmin());
                    session.setMaxInactiveInterval(3600);
                    return "redirect:/pages/dashboard";
                })
                .orElseGet(() -> {
                    model.addAttribute("error", "아이디 또는 비밀번호가 올바르지 않습니다.");
                    return "/member/login";
                });
    }

    // ✅ 로그아웃
    @PostMapping("/logout")
    public String logout(HttpSession session) {
        session.invalidate();
        return "redirect:/pages/dashboard";
    }
}
