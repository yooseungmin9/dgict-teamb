package com.bgroup.news.recommend.service;

import com.bgroup.news.member.domain.MemberDoc;
import org.springframework.stereotype.Service;

import java.util.*;

@Service
public class PreferenceKeywords {

    private static final Map<String, List<String>> GLOSS = Map.ofEntries(
            // industry
            Map.entry("industry/semiconductor", List.of("AI 반도체","HBM","파운드리","TSMC","삼성전자")),
            Map.entry("industry/auto_ev",       List.of("전기차","배터리","자율주행","충전 인프라")),
            Map.entry("industry/robotics",      List.of("로봇","물류자동화","AMR","협동로봇")),
            Map.entry("industry/_misc",         List.of("산업","성장산업","신산업")),
            // finance
            Map.entry("finance/monetary",       List.of("금리","연준","기준금리","점도표")),
            Map.entry("finance/_misc",          List.of("금융","금리동향")),
            // stock
            Map.entry("stock/etf",              List.of("ETF","인덱스 투자","테마 ETF")),
            Map.entry("stock/_misc",            List.of("주식","시장전망")),
            // global
            Map.entry("global/fx_commodities",  List.of("달러","유가","구리","금")),
            Map.entry("global/_misc",           List.of("글로벌 경제","세계 경기"))
    );

    /** explicit*2 + implicit*1 → 상위 N 서브카테고리에서 대표 키워드 최대 M개 */
    public List<String> buildSeeds(MemberDoc me, int topSubcats, int maxKeywords) {
        Map<String, Integer> subScore = new HashMap<>();

        if (me != null && me.getPreferences() != null) {
            var ex = Optional.ofNullable(me.getPreferences().getExplicit()).orElse(Map.of());
            var im = Optional.ofNullable(me.getPreferences().getImplicit()).orElse(Map.of());

            ex.forEach((parent, submap) ->
                    submap.forEach((sub, v) -> subScore.merge(key(parent, sub), safeInt(v) * 2, Integer::sum)));
            im.forEach((parent, submap) ->
                    submap.forEach((sub, v) -> subScore.merge(key(parent, sub), safeInt(v), Integer::sum)));
        } else if (me != null && me.getInterests() != null) {
            addIfPositive(subScore, "industry/_misc", me.getInterests().getIndustry());
            addIfPositive(subScore, "stock/_misc",    me.getInterests().getStock());
            addIfPositive(subScore, "finance/_misc",  me.getInterests().getFinance());
            addIfPositive(subScore, "global/_misc",   me.getInterests().getGlobal());
        }

        if (subScore.isEmpty()) return List.of();

        List<String> top = subScore.entrySet().stream()
                .sorted(Map.Entry.<String,Integer>comparingByValue().reversed())
                .limit(topSubcats)
                .map(Map.Entry::getKey)
                .toList();

        List<String> seeds = new ArrayList<>();
        for (String k : top) {
            List<String> kws = GLOSS.getOrDefault(k, List.of(k.substring(k.indexOf('/') + 1)));
            for (String w : kws) {
                if (!seeds.contains(w)) seeds.add(w);
                if (seeds.size() >= maxKeywords) break;
            }
            if (seeds.size() >= maxKeywords) break;
        }
        return seeds;
    }

    private static String key(String parent, String sub) { return parent + "/" + sub; }
    private static void addIfPositive(Map<String,Integer> m, String k, Integer v) {
        if (v != null && v > 0) m.put(k, v);
    }
    private static int safeInt(Integer x) { return x == null ? 0 : x; }
}