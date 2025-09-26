package com.bgroup.news.mongo.repository;

import com.bgroup.news.mongo.document.MemberDoc;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface MemberRepository extends MongoRepository<MemberDoc, String> {
}
