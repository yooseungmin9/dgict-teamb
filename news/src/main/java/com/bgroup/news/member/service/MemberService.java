package com.bgroup.news.member.service;

import com.bgroup.news.member.domain.MemberDoc;
import com.bgroup.news.member.dto.SignupRequest;
import com.bgroup.news.member.repository.MemberRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import java.time.Instant;

import java.util.*;

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
        member.setPassword(req.getPassword());
        member.setName(req.getName());
        member.setBirthYear(req.getBirthYear());
        member.setPhone(req.getPhone());
        member.setRegion(req.getRegion());
        member.setGender(req.getGender());
        member.setAdmin(0);

        // ✅ 생성·수정 시간 설정 (optional)
        member.setCreatedAt(Instant.now());
        member.setUpdatedAt(Instant.now());

        return repo.save(member);
    }

    public void updateInterests(String userId, List<String> selected){
        MemberDoc m = getOrThrow(userId);

        // 키워드 → 카테고리 맵 (서버 기준 룩업)
        Map<String, String> kw2cat = Map.ofEntries(
                // 증권
                Map.entry("주식","증권"), Map.entry("코스피","증권"), Map.entry("ETF","증권"),
                Map.entry("공모주","증권"), Map.entry("배당","증권"), Map.entry("리츠","증권"),
                Map.entry("거래량","증권"),
                // 금융
                Map.entry("금리","금융"), Map.entry("대출","금융"), Map.entry("예금","금융"),
                Map.entry("보험","금융"), Map.entry("환율","금융"), Map.entry("금융감독원","금융"),
                Map.entry("비트코인","금융"),
                // 부동산
                Map.entry("부동산","부동산"), Map.entry("아파트","부동산"), Map.entry("전세","부동산"),
                Map.entry("청약","부동산"), Map.entry("재건축","부동산"), Map.entry("공시지가","부동산"),
                Map.entry("집값","부동산"),
                // 산업
                Map.entry("산업","산업"), Map.entry("자동차","산업"), Map.entry("반도체","산업"),
                Map.entry("전기차","산업"), Map.entry("배터리","산업"), Map.entry("로봇","산업"),
                Map.entry("AI","산업"),
                // 글로벌경제
                Map.entry("미국","글로벌경제"), Map.entry("중국","글로벌경제"), Map.entry("달러","글로벌경제"),
                Map.entry("무역","글로벌경제"), Map.entry("유가","글로벌경제"), Map.entry("나스닥","글로벌경제"),
                Map.entry("IMF","글로벌경제"),
                // 일반
                Map.entry("물가","일반"), Map.entry("소비","일반"), Map.entry("고용","일반"),
                Map.entry("임금","일반"), Map.entry("GDP","일반"), Map.entry("경기침체","일반"),
                Map.entry("가계부채","일반")
        );

        int g=0,f=0,e=0,i=0,s=0,n=0;
        if(selected != null){
            for(String kw : selected){
                String c = kw2cat.get(kw);
                if(c == null) continue;
                switch (c){
                    case "글로벌경제" -> g++;
                    case "금융"      -> f++;
                    case "부동산"    -> e++;
                    case "산업"      -> i++;
                    case "증권"      -> s++;
                    case "일반"      -> n++;
                }
            }
        }

        // 간단 정규화 (카테고리당 최대 4개 선택한 걸 0~4 점수로 사용)
        int cap = 4;
        MemberDoc.Interests it = new MemberDoc.Interests();
        it.setGlobal(Math.min(g, cap));
        it.setFinance(Math.min(f, cap));
        it.setEstate(Math.min(e, cap));
        it.setIndustry(Math.min(i, cap));
        it.setStock(Math.min(s, cap));
        it.setGeneral(Math.min(n, cap));

        m.setInterests(it);
        m.setUpdatedAt(Instant.now());
        save(m);
    }
}
