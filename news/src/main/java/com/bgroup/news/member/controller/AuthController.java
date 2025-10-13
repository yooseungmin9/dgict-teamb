package com.bgroup.news.member.controller;

import com.bgroup.news.member.domain.MemberDoc;
import com.bgroup.news.member.dto.LoginRequest;
import com.bgroup.news.member.service.MemberService;
import jakarta.servlet.http.HttpSession;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

import java.util.List;
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
    public String loginPage(@RequestHeader(value = "Referer", required = false) String referer,
                            HttpSession session) {
        // 로그인 페이지로 직접 접근한 게 아니라면 referer 저장
        if (referer != null && !referer.contains("/auth/login")) {
            session.setAttribute("redirectAfterLogin", referer);
        }
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

                    // 원래 페이지 정보가 있으면 그쪽으로 리다이렉트
                    String redirectUrl = (String) session.getAttribute("redirectAfterLogin");
                    session.removeAttribute("redirectAfterLogin"); // 한 번 쓰고 삭제
                    return "redirect:" + (redirectUrl != null ? redirectUrl : "/pages/dashboard");
                })
                .orElseGet(() -> {
                    model.addAttribute("error", "아이디 또는 비밀번호가 올바르지 않습니다.");
                    return "/member/login";
                });
    }

    // ✅ 로그아웃
    @PostMapping("/logout")
    public String logout(@RequestHeader(value = "Referer", required = false) String referer,
                         HttpSession session) {
        session.invalidate();

        // 로그아웃 후 원래 페이지로 돌아감
        if (referer != null && !referer.contains("/auth")) {
            return "redirect:" + referer;
        } else {
            return "redirect:/pages/dashboard";
        }
    }
}
