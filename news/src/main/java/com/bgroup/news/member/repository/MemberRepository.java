package com.bgroup.news.member.repository;

import com.bgroup.news.member.domain.MemberDoc;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface MemberRepository extends MongoRepository<MemberDoc, String> {
}
