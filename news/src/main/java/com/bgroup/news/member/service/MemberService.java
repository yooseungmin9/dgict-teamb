package com.bgroup.news.member.service;

import com.bgroup.news.member.domain.MemberDoc;
import com.bgroup.news.member.dto.PreferenceSurveyRequest;
import com.bgroup.news.member.dto.SignupRequest;
import com.bgroup.news.member.repository.MemberRepository;
import org.springframework.data.domain.*;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.*;

@Service
public class MemberService {

    private final MemberRepository repo;

    public MemberService(MemberRepository repo) { this.repo = repo; }

    public Optional<MemberDoc> findById(String id){ return repo.findById(id); }
    public MemberDoc getOrThrow(String id){
        return repo.findById(id).orElseThrow(() -> new NoSuchElementException("member not found: " + id));
    }
    public boolean existsById(String id){ return repo.existsById(id); }
    public List<MemberDoc> listAll(){ return repo.findAll(Sort.by(Sort.Direction.ASC,"id")); }
    public Page<MemberDoc> list(int page, int size){
        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.ASC,"id"));
        return repo.findAll(pageable);
    }
    public MemberDoc save(MemberDoc m){ return repo.save(m); }

    public Optional<MemberDoc> authenticate(String id, String rawPassword){
        return repo.findById(id).filter(m -> Objects.equals(m.getPassword(), rawPassword));
    }

    public MemberDoc saveMember(MemberDoc member){ return repo.save(member); }

    public MemberDoc register(SignupRequest req){
        MemberDoc m = new MemberDoc();
        m.setId(req.getId());
        m.setPassword(req.getPassword());
        m.setName(req.getName());
        m.setBirthYear(req.getBirthYear());
        m.setPhone(req.getPhone());
        m.setRegion(req.getRegion());
        m.setGender(req.getGender());
        m.setAdmin(0);
        m.setCreatedAt(Instant.now());
        m.setUpdatedAt(Instant.now());
        return repo.save(m);
    }

    public void updateInterests(String userId, List<String> selected){
        MemberDoc m = getOrThrow(userId);

        // 1) 키워드 → (부모,하위) 한글 매핑
        record PS(String p, String s) {}
        Map<String, PS> kw2ps = Map.ofEntries(
                // 주식
                Map.entry("주식",   new PS("주식","기초")),
                Map.entry("ETF",    new PS("주식","ETF")),
                Map.entry("공모주", new PS("주식","공모주")),
                Map.entry("배당",   new PS("주식","배당")),
                Map.entry("리츠",   new PS("주식","리츠")),
                Map.entry("거래량", new PS("주식","거래량")),
                // 금융
                Map.entry("금리",     new PS("금융","금리")),
                Map.entry("대출",     new PS("금융","대출")),
                Map.entry("예금",     new PS("금융","예금")),
                Map.entry("보험",     new PS("금융","보험")),
                Map.entry("환율",     new PS("금융","환율원자재")),
                Map.entry("금융감독원", new PS("금융","규제")),
                Map.entry("비트코인", new PS("금융","가상자산")),
                // 부동산
                Map.entry("부동산", new PS("부동산","개요")),
                Map.entry("아파트", new PS("부동산","아파트")),
                Map.entry("전세",   new PS("부동산","전세")),
                Map.entry("청약",   new PS("부동산","청약")),
                Map.entry("재건축", new PS("부동산","재건축")),
                Map.entry("공시지가", new PS("부동산","정책세금")),
                Map.entry("집값",   new PS("부동산","가격")),
                // 산업
                Map.entry("산업",   new PS("산업","개요")),
                Map.entry("자동차", new PS("산업","전기차")),
                Map.entry("전기차", new PS("산업","전기차")),
                Map.entry("배터리", new PS("산업","전기차")),
                Map.entry("반도체", new PS("산업","반도체")),
                Map.entry("로봇",   new PS("산업","로봇")),
                Map.entry("AI",     new PS("산업","AI인프라")),
                // 글로벌
                Map.entry("미국",   new PS("글로벌","미국")),
                Map.entry("중국",   new PS("글로벌","중국")),
                Map.entry("달러",   new PS("글로벌","환율원자재")),
                Map.entry("무역",   new PS("글로벌","지정학공급망")),
                Map.entry("유가",   new PS("글로벌","환율원자재")),
                Map.entry("나스닥", new PS("글로벌","글로벌시장")),
                Map.entry("IMF",    new PS("글로벌","국제기구")),
                // 일반 거시
                Map.entry("물가", new PS("일반","거시기초")),
                Map.entry("소비", new PS("일반","소비")),
                Map.entry("고용", new PS("일반","노동")),
                Map.entry("임금", new PS("일반","노동")),
                Map.entry("GDP",  new PS("일반","거시기초")),
                Map.entry("경기침체", new PS("일반","경기순환")),
                Map.entry("가계부채", new PS("일반","가계부채"))
        );

        // 2) preferences 준비
        MemberDoc.Preferences prefs = m.getPreferences();
        if (prefs == null) {
            prefs = MemberDoc.Preferences.builder()
                    .explicit(new HashMap<>()).implicit(new HashMap<>()).build();
        }
        Map<String, Map<String, Integer>> explicit =
                (prefs.getExplicit()!=null ? prefs.getExplicit() : new HashMap<>());

        // 3) 선택 누적 (카테고리당 최대 4)
        int capPerSub = 4;
        if (selected != null) {
            for (String kw : selected) {
                PS ps = kw2ps.getOrDefault(kw, new PS("일반","거시기초"));
                explicit.computeIfAbsent(ps.p(), k -> new HashMap<>());
                Map<String,Integer> sub = explicit.get(ps.p());
                sub.put(ps.s(), Math.min(capPerSub, sub.getOrDefault(ps.s(),0)+1));
            }
        }

        // 4) 상위합계 재계산 → interests(하위호환)
        MemberDoc.Interests agg = new MemberDoc.Interests(0,0,0,0,0,0);
        for (var e : explicit.entrySet()){
            int sum = e.getValue().values().stream().mapToInt(Integer::intValue).sum();
            switch (e.getKey()){
                case "글로벌" -> agg.setGlobal(sum);
                case "금융"   -> agg.setFinance(sum);
                case "부동산" -> agg.setEstate(sum);
                case "산업"   -> agg.setIndustry(sum);
                case "주식"   -> agg.setStock(sum);
                case "일반"   -> agg.setGeneral(sum);
            }
        }

        // 5) 저장
        prefs.setExplicit(explicit);
        prefs.setLastUpdated(Instant.now());
        m.setPreferences(prefs);
        m.setInterests(agg);
        m.setUpdatedAt(Instant.now());
        save(m);
    }

    public void applyPreferenceSurvey(String userId, PreferenceSurveyRequest r){
        MemberDoc m = getOrThrow(userId);

        MemberDoc.Preferences prefs = Optional.ofNullable(m.getPreferences())
                .orElse(MemberDoc.Preferences.builder()
                        .explicit(new HashMap<>()).implicit(new HashMap<>()).build());

        // 플랫폼/포털 관련은 기존 그대로(문자열 값이므로 언어 독립)
        if (r.mainSource() != null && !r.mainSource().isBlank()) {
            prefs.setMainSource(r.mainSource());
        }
        MemberDoc.Preferences.Platforms p = Optional.ofNullable(prefs.getPlatforms())
                .orElse(new MemberDoc.Preferences.Platforms(null, new ArrayList<>(), new ArrayList<>(), new ArrayList<>()));
        if (r.portal() != null && !r.portal().isBlank()) p.setPortal(r.portal());
        if (r.sns() != null)   p.setSns(r.sns());
        if (r.video() != null) p.setVideo(r.video());
        if (r.ott() != null)   p.setOtt(r.ott());
        prefs.setPlatforms(p);

        if (r.mainSources() != null) {
            prefs.setMainSources(new ArrayList<>(new LinkedHashSet<>(r.mainSources())));
        }
        if (r.portals() != null) {
            prefs.setPortals(new ArrayList<>(new LinkedHashSet<>(r.portals())));
        }

        prefs.setLastUpdated(Instant.now());
        m.setPreferences(prefs);
        m.setUpdatedAt(Instant.now());
        save(m);
    }
}
