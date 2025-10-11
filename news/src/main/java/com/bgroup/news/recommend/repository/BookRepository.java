package com.bgroup.news.recommend.repository;

import com.bgroup.news.recommend.dto.BookResponse;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.data.mongodb.repository.Query;

public interface BookRepository extends MongoRepository<BookResponse, String> {
    Page<BookResponse> findAll(Pageable pageable);

    // 제목/저자에 검색어 포함(대소문자 무시)
    @Query("{ '$or': [ {'title': { $regex: ?0, $options: 'i' } }, {'author': { $regex: ?0, $options: 'i' } } ] }")
    Page<BookResponse> searchByTitleOrAuthor(String keyword, Pageable pageable);
}