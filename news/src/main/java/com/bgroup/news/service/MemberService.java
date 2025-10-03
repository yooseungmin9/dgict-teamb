package com.bgroup.news.service;

import com.bgroup.news.dto.MemberDoc;
import com.bgroup.news.repository.MemberRepository;
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
}
