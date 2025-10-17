package com.bgroup.news.search.repository;

import com.bgroup.news.search.domain.NewsDoc;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.data.mongodb.repository.Query;

public interface NewsRepository extends MongoRepository<NewsDoc, String> {

    @Query("""
        { $or: [
            { 'title':   { $regex: ?0, $options: 'i' } },
            { 'summary': { $regex: ?0, $options: 'i' } },
            { 'content': { $regex: ?0, $options: 'i' } },
            { 'keywords': { $regex: ?0, $options: 'i' } }
        ]}
    """)
    Page<NewsDoc> searchFulltext(String keyword, Pageable pageable);
}