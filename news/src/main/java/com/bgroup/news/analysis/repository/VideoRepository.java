package com.bgroup.news.analysis.repository;

import java.util.List;

import com.bgroup.news.analysis.domain.VideoDoc;
import org.springframework.data.mongodb.repository.MongoRepository;

public interface VideoRepository extends MongoRepository<VideoDoc, String> {
    VideoDoc findByVideoId(String videoId);
    List<VideoDoc> findTop50ByOrderByPublishedAtDesc();
}