package com.bgroup.news.member.service;

import com.bgroup.news.member.domain.MemberDoc;
import com.bgroup.news.member.dto.SignupRequest;
import com.bgroup.news.member.repository.MemberRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.NoSuchElementException;
import java.util.Objects;
import java.util.Optional;

@Service
public class MemberService {

    private final MemberRepository repo;

    public MemberService(MemberRepository repo) {
        this.repo = repo;
    }

    public Optional<MemberDoc> findById(String id) {
        return repo.findById(id);
    }

    public MemberDoc getOrThrow(String id) {
        return repo.findById(id)
                .orElseThrow(() -> new NoSuchElementException("member not found: " + id));
    }

    public boolean existsById(String id) {
        return repo.existsById(id);
    }

    public List<MemberDoc> listAll() {
        return repo.findAll(Sort.by(Sort.Direction.ASC, "id"));
    }

    public Page<MemberDoc> list(int page, int size) {
        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.ASC, "id"));
        return repo.findAll(pageable);
    }

    public MemberDoc save(MemberDoc m) {
        return repo.save(m);
    }

    public Optional<MemberDoc> authenticate(String id, String rawPassword) {
        return repo.findById(id)
                .filter(m -> Objects.equals(m.getPassword(), rawPassword));
    }

    public MemberDoc saveMember(MemberDoc member) {
        return repo.save(member);
    }

    public MemberDoc register(SignupRequest req) {
        MemberDoc member = new MemberDoc();
        member.setId(req.getId());
        member.setPassword(req.getPassword()); // 나중에 BCrypt로 암호화 가능
        member.setName(req.getName());
        member.setBirthYear(req.getBirthYear());
        member.setPhone(req.getPhone());
        member.setRegion(req.getRegion());
        member.setGender(req.getGender());
        member.setAdmin(0); // 기본 일반회원
        return repo.save(member);
    }

}
