package com.bgroup.news.news.controller;

import com.bgroup.news.news.dto.Article;
import com.bgroup.news.news.service.ArticleService;
import org.springframework.data.domain.Page;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.*;

@Controller
@RequestMapping("/pages/news")
public class NewsController {

    private final ArticleService articleService;

    public NewsController(ArticleService articleService) {
        this.articleService = articleService;
    }

    /** ✅ 목록 페이지 */
    @GetMapping({"", "/"})
    public String list(@RequestParam(defaultValue = "1") int page,
                       @RequestParam(defaultValue = "10") int size,
                       @RequestParam(required = false) String category,
                       Model model) {

        Page<Article> pageData;

        if (category != null && !category.isEmpty()) {
            pageData = articleService.getArticlesByCategory(category, page, size);
        } else {
            pageData = articleService.getAllArticles(page, size);
        }

        model.addAttribute("items", pageData.getContent());
        model.addAttribute("page", page);
        model.addAttribute("size", size);
        model.addAttribute("hasPrev", pageData.hasPrevious());
        model.addAttribute("hasNext", pageData.hasNext());

        return "pages/news";
    }

    /** ✅ 상세 (모달 JSON 요청) */
    @GetMapping("/{id}")
    @ResponseBody
    public Article detail(@PathVariable String id) {
        return articleService.getArticleById(id);
    }
}
