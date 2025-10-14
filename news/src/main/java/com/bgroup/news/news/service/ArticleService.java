package com.bgroup.news.news.service;

import com.bgroup.news.news.dto.Article;
import com.bgroup.news.news.repository.ArticleRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;

@Service
public class ArticleService {

    private final ArticleRepository repo;

    public ArticleService(ArticleRepository repo) {
        this.repo = repo;
    }

    public Page<Article> getAllArticles(int page, int size) {
        Pageable pageable = PageRequest.of(page - 1, size, Sort.by(Sort.Direction.DESC, "publishedAt"));
        return repo.findAll(pageable);
    }

    public Page<Article> getArticlesByCategory(String category, int page, int size) {
        Pageable pageable = PageRequest.of(page - 1, size, Sort.by(Sort.Direction.DESC, "publishedAt"));
        return repo.findByCategory(category, pageable);
    }

    public Article getArticleById(String id) {
        return repo.findById(id).orElse(null);
    }
}
