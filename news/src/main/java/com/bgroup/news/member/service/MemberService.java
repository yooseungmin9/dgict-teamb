package com.bgroup.news.member.service;

import com.bgroup.news.member.domain.MemberDoc;
import com.bgroup.news.member.dto.PreferenceSurveyRequest;
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

    public Optional<MemberDoc> findById(String id) { return repo.findById(id); }
    public MemberDoc getOrThrow(String id) {
        return repo.findById(id).orElseThrow(() -> new NoSuchElementException("member not found: " + id));
    }
    public boolean existsById(String id) { return repo.existsById(id); }
    public List<MemberDoc> listAll() { return repo.findAll(Sort.by(Sort.Direction.ASC, "id")); }
    public Page<MemberDoc> list(int page, int size) {
        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.ASC, "id"));
        return repo.findAll(pageable);
    }
    public MemberDoc save(MemberDoc m) { return repo.save(m); }

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

        // 1) 키워드 → (parent, sub) 매핑
        record PS(String p, String s) {}
        Map<String, PS> kw2ps = Map.ofEntries(
                // stock
                Map.entry("주식", new PS("stock","equity_basic")),
                Map.entry("ETF", new PS("stock","etf")),
                Map.entry("공모주", new PS("stock","ipo")),
                Map.entry("배당", new PS("stock","dividend")),
                Map.entry("리츠", new PS("stock","reits")),
                Map.entry("거래량", new PS("stock","trading")),
                // finance
                Map.entry("금리", new PS("finance","monetary")),
                Map.entry("대출", new PS("finance","credit")),
                Map.entry("예금", new PS("finance","deposit")),
                Map.entry("보험", new PS("finance","insurance")),
                Map.entry("환율", new PS("finance","fx")),
                Map.entry("금융감독원", new PS("finance","regulation")),
                Map.entry("비트코인", new PS("finance","crypto")),
                // estate
                Map.entry("부동산", new PS("estate","overview")),
                Map.entry("아파트", new PS("estate","residential")),
                Map.entry("전세", new PS("estate","lease")),
                Map.entry("청약", new PS("estate","subscription")),
                Map.entry("재건축", new PS("estate","redevelopment")),
                Map.entry("공시지가", new PS("estate","policy_tax")),
                Map.entry("집값", new PS("estate","price")),
                // industry
                Map.entry("산업", new PS("industry","overview")),
                Map.entry("자동차", new PS("industry","auto_ev")),
                Map.entry("전기차", new PS("industry","auto_ev")),
                Map.entry("배터리", new PS("industry","auto_ev")),
                Map.entry("반도체", new PS("industry","semiconductor")),
                Map.entry("로봇", new PS("industry","robotics")),
                Map.entry("AI", new PS("industry","ai_infra")),
                // global
                Map.entry("미국", new PS("global","us")),
                Map.entry("중국", new PS("global","china")),
                Map.entry("달러", new PS("global","fx_commodities")),
                Map.entry("무역", new PS("global","geopolitics_supplychain")),
                Map.entry("유가", new PS("global","fx_commodities")),
                Map.entry("나스닥", new PS("global","markets_global")),
                Map.entry("IMF", new PS("global","institutions")),
                // general
                Map.entry("물가", new PS("general","macro_basic")),
                Map.entry("소비", new PS("general","consumer")),
                Map.entry("고용", new PS("general","labor")),
                Map.entry("임금", new PS("general","labor")),
                Map.entry("GDP", new PS("general","macro_basic")),
                Map.entry("경기침체", new PS("general","cycle")),
                Map.entry("가계부채", new PS("general","household_debt"))
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
                PS ps = kw2ps.get(kw);
                if (ps == null) continue;
                explicit.computeIfAbsent(ps.p(), k -> new HashMap<>());
                Map<String,Integer> sub = explicit.get(ps.p());
                sub.put(ps.s(), Math.min(capPerSub, sub.getOrDefault(ps.s(),0)+1));
            }
        }

        // 4) 상위합계 재계산 → interests 갱신(하위호환)
        MemberDoc.Interests agg = new MemberDoc.Interests(0,0,0,0,0,0);
        for (var e : explicit.entrySet()){
            int sum = e.getValue().values().stream().mapToInt(Integer::intValue).sum();
            switch (e.getKey()){
                case "global"   -> agg.setGlobal(sum);
                case "finance"  -> agg.setFinance(sum);
                case "estate"   -> agg.setEstate(sum);
                case "industry" -> agg.setIndustry(sum);
                case "stock"    -> agg.setStock(sum);
                case "general"  -> agg.setGeneral(sum);
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

        MemberDoc.Preferences prefs = m.getPreferences();
        if (prefs == null) {
            prefs = MemberDoc.Preferences.builder()
                    .explicit(new HashMap<>())
                    .implicit(new HashMap<>())
                    .build();
        }

        // mainSource
        if (r.mainSource() != null && !r.mainSource().isBlank()) {
            prefs.setMainSource(r.mainSource());
        }

        // platforms
        MemberDoc.Preferences.Platforms p = prefs.getPlatforms();
        if (p == null) p = new MemberDoc.Preferences.Platforms(null, new ArrayList<>(), new ArrayList<>(), new ArrayList<>());
        if (r.portal() != null) p.setPortal(r.portal());
        if (r.sns() != null)    p.setSns(r.sns());
        if (r.video() != null)  p.setVideo(r.video());
        if (r.ott() != null)    p.setOtt(r.ott());
        prefs.setPlatforms(p);

        // categoryWeights (0.0~1.0로 정규화 가정)
        if (r.categoryWeights() != null && !r.categoryWeights().isEmpty()) {
            prefs.setCategoryWeights(r.categoryWeights());
        }

        // regionInterest
        MemberDoc.Preferences.RegionInterest ri = prefs.getRegionInterest();
        if (ri == null) ri = new MemberDoc.Preferences.RegionInterest(null, null, null);
        if (r.metro() != null)      ri.setMetro(r.metro());
        if (r.city() != null)       ri.setCity(r.city());
        if (r.regionLevel() != null)ri.setLevel(r.regionLevel());
        prefs.setRegionInterest(ri);

        // 타임스탬프
        prefs.setLastUpdated(Instant.now());
        m.setPreferences(prefs);
        m.setUpdatedAt(Instant.now());
        save(m);
    }
}