package com.bgroup.news.recommend.repository;

import com.bgroup.news.recommend.dto.BookResponse;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.data.mongodb.repository.Query;
import org.springframework.data.domain.Pageable;

import java.util.List;

public interface BookRepository extends MongoRepository<BookResponse, String> {

    // 1️⃣ 개인화 검색 (제목 or 저자 like)
    List<BookResponse> findByTitleContainingIgnoreCaseOrAuthorContainingIgnoreCase(
            String titleKeyword, String authorKeyword, Pageable pageable
    );

    // 2️⃣ 랭크가 있는 도서
    @Query(value = "{ 'bestseller.rank': { $exists: true } }")
    List<BookResponse> findRanked(Pageable pageable);

    // 3️⃣ 판매지수(salesPoint) 있는 도서
    @Query(value = "{ 'salesPoint': { $exists: true } }")
    List<BookResponse> findWithSalesPoint(Pageable pageable);

    // 4️⃣ 출간일 최신순
    List<BookResponse> findAllByOrderByPubDateDesc(Pageable pageable);
}