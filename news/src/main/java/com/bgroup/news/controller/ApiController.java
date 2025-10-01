package com.bgroup.news.controller;

import com.bgroup.news.mongo.document.MemberDoc;
import com.bgroup.news.service.KeywordService;
import com.bgroup.news.service.MemberService;
import org.springframework.data.domain.Page;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class ApiController {

    private final KeywordService keywordService;
    private final MemberService memberService;

    public ApiController(KeywordService keywordService,
                         MemberService memberService) {
        this.keywordService = keywordService;
        this.memberService = memberService;
    }

    @GetMapping("/keywords")
    public Mono<String> getKeywords() {
        return keywordService.fetchKeywords();
    }

    @GetMapping("/members/{id}")
    public ResponseEntity<MemberDoc> getMember(@PathVariable String id) {
        return memberService.findById(id)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/members/exists/{id}")
    public Map<String, Boolean> exists(@PathVariable String id) {
        return Map.of("exists", memberService.existsById(id));
    }

    @GetMapping("/members")
    public List<MemberDoc> listMembers() {
        return memberService.listAll();
    }

    @GetMapping("/members/paged")
    public Page<MemberDoc> listMembersPaged(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        return memberService.list(page, size);
    }

    @PostMapping("/members")
    public ResponseEntity<MemberDoc> save(@RequestBody MemberDoc member) {
        MemberDoc saved = memberService.save(member);
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    @PostMapping("/auth/login")
    public ResponseEntity<?> login(@RequestBody Map<String, String> body) {
        String id = body.getOrDefault("id", "");
        String pw = body.getOrDefault("password", "");
        return memberService.authenticate(id, pw)
                .map(m -> ResponseEntity.ok(
                        Map.of("id", m.getId(),
                                "name", m.getName(),
                                "admin", m.getAdmin())))
                .orElse(ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                        .body(Map.of("error", "INVALID_CREDENTIALS")));
    }
}
