package com.bgroup.news.recommend.repository;

import com.bgroup.news.recommend.dto.BookResponse;

import java.util.List;

public interface BookRepositoryCustom {
    List<BookResponse> searchPersonalized(List<String> keywords, int limit);
}