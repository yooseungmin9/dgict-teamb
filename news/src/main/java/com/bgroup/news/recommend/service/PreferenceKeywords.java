package com.bgroup.news.recommend.service;

import com.bgroup.news.member.domain.MemberDoc;
import org.springframework.stereotype.Service;

import java.util.*;

@Service
public class PreferenceKeywords {

    /** 한글 정규 키: "부모/하위" */
    private static final Map<String, List<String>> GLOSS = Map.ofEntries(
            // 금융
            Map.entry("금융/금리",       List.of("금리","연준","기준금리","점도표")),
            Map.entry("금융/대출",       List.of("대출","신용대출","신용점수","대출금리","DSR")),
            Map.entry("금융/_기타",      List.of("금융","금리동향","대출규제")),
            // 주식
            Map.entry("주식/ETF",        List.of("ETF","인덱스 투자","테마 ETF")),
            Map.entry("주식/_기타",      List.of("주식","시장전망")),
            // 산업
            Map.entry("산업/반도체",     List.of("AI 반도체","HBM","파운드리","TSMC","삼성전자")),
            Map.entry("산업/전기차",     List.of("전기차","배터리","자율주행","충전 인프라")),
            Map.entry("산업/로봇",       List.of("로봇","물류자동화","AMR","협동로봇")),
            Map.entry("산업/_기타",      List.of("산업","성장산업","신산업")),
            // 글로벌
            Map.entry("글로벌/환율원자재", List.of("달러","유가","구리","금")),
            Map.entry("글로벌/_기타",    List.of("글로벌 경제","세계 경기")),
            // 부동산(선택)
            Map.entry("부동산/_기타",    List.of("부동산","아파트","전세","청약","집값"))
    );

    /** 기존 영문/혼합 표기를 만나도 한글 정규 키로 수렴 (레거시 호환용) */
    private static final Map<String, String> ALIAS = Map.ofEntries(
            // parent
            Map.entry("finance", "금융"), Map.entry("financial", "금융"),
            Map.entry("stock", "주식"),   Map.entry("stocks", "주식"),
            Map.entry("industry", "산업"),Map.entry("industries", "산업"),
            Map.entry("global", "글로벌"),Map.entry("estate","부동산"),
            // sub
            Map.entry("monetary", "금리"), Map.entry("interest", "금리"),
            Map.entry("credit", "대출"),   Map.entry("loan","대출"), Map.entry("loans","대출"),
            Map.entry("etf","ETF"),
            Map.entry("semiconductor","반도체"),
            Map.entry("auto_ev","전기차"),
            Map.entry("robotics","로봇"),
            Map.entry("fx_commodities","환율원자재"),
            Map.entry("_misc","_기타"), Map.entry("misc","_기타")
    );

    /** explicit*2 + implicit*1 → 상위 N 서브카테고리에서 대표 키워드 최대 M개 */
    public List<String> buildSeeds(MemberDoc me, int topSubcats, int maxKeywords) {
        Map<String,Integer> subScore = new HashMap<>();

        if (me != null && me.getPreferences() != null) {
            var ex = Optional.ofNullable(me.getPreferences().getExplicit()).orElse(Map.of());
            var im = Optional.ofNullable(me.getPreferences().getImplicit()).orElse(Map.of());

            ex.forEach((parent, submap) ->
                    submap.forEach((sub, v) ->
                            subScore.merge(key(canon(parent), canon(sub)), safeInt(v) * 2, Integer::sum)));
            im.forEach((parent, submap) ->
                    submap.forEach((sub, v) ->
                            subScore.merge(key(canon(parent), canon(sub)), safeInt(v), Integer::sum)));
        } else if (me != null && me.getInterests() != null) {
            addIfPositive(subScore, key("산업","_기타"),   me.getInterests().getIndustry());
            addIfPositive(subScore, key("주식","_기타"),   me.getInterests().getStock());
            addIfPositive(subScore, key("금융","_기타"),   me.getInterests().getFinance());
            addIfPositive(subScore, key("글로벌","_기타"), me.getInterests().getGlobal());
            addIfPositive(subScore, key("부동산","_기타"), me.getInterests().getEstate());
        }

        if (subScore.isEmpty()) return List.of();

        List<String> top = subScore.entrySet().stream()
                .sorted(Map.Entry.<String,Integer>comparingByValue().reversed())
                .limit(topSubcats).map(Map.Entry::getKey).toList();

        List<String> seeds = new ArrayList<>();
        for (String k : top) {
            List<String> kws = GLOSS.getOrDefault(k, List.of(k.substring(k.indexOf('/')+1)));
            for (String w : kws) {
                if (!seeds.contains(w)) seeds.add(w);
                if (seeds.size() >= maxKeywords) break;
            }
            if (seeds.size() >= maxKeywords) break;
        }
        return seeds;
    }

    private static String canon(String t){
        if (t == null) return "_기타";
        String s = t.trim();
        // 영문 별칭 → 한글 정규
        s = ALIAS.getOrDefault(s, s);
        return s.isEmpty() ? "_기타" : s;
    }
    private static String key(String p, String s){ return p + "/" + s; }
    private static void addIfPositive(Map<String,Integer> m, String k, Integer v){ if (v!=null && v>0) m.merge(k,v,Integer::sum); }
    private static int safeInt(Integer x){ return x==null?0:x; }
}
