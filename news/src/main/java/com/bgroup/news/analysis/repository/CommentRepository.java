package com.bgroup.news.analysis.repository;

import com.bgroup.news.analysis.domain.CommentDoc;
import org.springframework.data.domain.Pageable;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface CommentRepository extends MongoRepository<CommentDoc, String> {
    List<CommentDoc> findByVideoId(String videoId, Pageable pageable);
}