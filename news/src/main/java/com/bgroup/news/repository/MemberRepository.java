package com.bgroup.news.repository;

import com.bgroup.news.dto.MemberDoc;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface MemberRepository extends MongoRepository<MemberDoc, String> {
}
