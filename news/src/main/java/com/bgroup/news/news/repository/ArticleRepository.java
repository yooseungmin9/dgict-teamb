package com.bgroup.news.news.repository;

import com.bgroup.news.news.dto.Article;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.mongodb.repository.MongoRepository;

public interface ArticleRepository extends MongoRepository<Article, String> {
    Page<Article> findByCategory(String category, Pageable pageable);
    Page<Article> findAll(Pageable pageable);
}
