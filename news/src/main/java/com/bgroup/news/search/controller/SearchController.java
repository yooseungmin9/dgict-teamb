package com.bgroup.news.search.controller;

import com.bgroup.news.member.domain.MemberDoc;
import com.bgroup.news.search.service.SearchService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.SessionAttribute;

import java.util.List;

@Controller
@RequestMapping("/pages")
@RequiredArgsConstructor
public class SearchController {

    private final SearchService searchService;

    @GetMapping(value = "/search", produces = MediaType.TEXT_HTML_VALUE)
    public String search(
            @RequestParam(name = "q",  required = false) String q,
            // ▼ 섹션별 개수 파라미터 (기본값: 뉴스5, 영상3, 서적5)
            @RequestParam(name = "nn", required = false, defaultValue = "5")  int newsSize,
            @RequestParam(name = "nv", required = false, defaultValue = "3")  int videoSize,
            @RequestParam(name = "nb", required = false, defaultValue = "5")  int bookSize,
            @SessionAttribute(value = "loginUser", required = false) MemberDoc me,
            Model model
    ) {
        String query = (q == null) ? "" : q.trim();
        model.addAttribute("q", query);
        model.addAttribute("loggedIn", me != null);

        // 현재 개수(템플릿에서 '더보기' 링크 구성에 사용)
        model.addAttribute("nn", newsSize);
        model.addAttribute("nv", videoSize);
        model.addAttribute("nb", bookSize);

        // 검색
        var books  = searchService.searchBooks(query,  bookSize);
        var videos = searchService.searchYoutube(query, videoSize);
        var news   = searchService.searchNews(query,   newsSize);

        model.addAttribute("books",  books);
        model.addAttribute("videos", videos);
        model.addAttribute("news",   news);

        model.addAttribute("emptyQuery", query.isBlank());
        return "pages/search";
    }
}
