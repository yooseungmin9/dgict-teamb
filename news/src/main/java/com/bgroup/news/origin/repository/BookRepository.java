package com.bgroup.news.origin.repository;

import com.bgroup.news.origin.dto.BookResponse;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface BookRepository extends MongoRepository<BookResponse, String> {
    List<BookResponse> findTop10ByOrderByPubDateDesc();
    List<BookResponse> findTop10ByCategoryIdOrderByPubDateDesc(Integer categoryId);
}