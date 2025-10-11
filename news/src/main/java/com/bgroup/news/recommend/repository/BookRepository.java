package com.bgroup.news.recommend.repository;

import com.bgroup.news.recommend.dto.BookResponse;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.mongodb.repository.MongoRepository;

public interface BookRepository extends MongoRepository<BookResponse, String> {
    Page<BookResponse> findAll(Pageable pageable);
}