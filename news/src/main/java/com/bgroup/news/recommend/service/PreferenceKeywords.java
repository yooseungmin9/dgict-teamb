package com.bgroup.news.recommend.service;

import com.bgroup.news.member.domain.MemberDoc;

import java.util.*;
import java.util.stream.Collectors;

public class PreferenceKeywords {

    // 대표 키워드(간단 세트)
    private static final Map<String, List<String>> CATEGORY_KEYWORDS = new LinkedHashMap<>() {{
        put("증권", List.of("주식","코스피","ETF","공모주","배당","리츠","거래량"));
        put("금융", List.of("금리","대출","예금","보험","환율","금융감독원","비트코인"));
        put("부동산", List.of("부동산","아파트","전세","청약","재건축","공시지가","집값"));
        put("산업", List.of("산업","자동차","반도체","전기차","배터리","로봇","AI"));
        put("글로벌경제", List.of("미국","중국","달러","무역","유가","나스닥","IMF"));
        put("일반", List.of("물가","소비","고용","임금","GDP","경기침체","가계부채"));
    }};

    public static List<String> build(MemberDoc.Interests it) {
        if (it == null) return List.of();

        Map<String, Integer> score = Map.of(
                "글로벌경제", nz(it.getGlobal()),
                "금융", nz(it.getFinance()),
                "부동산", nz(it.getEstate()),
                "산업", nz(it.getIndustry()),
                "증권", nz(it.getStock()),
                "일반", nz(it.getGeneral())
        );

        // 상위 3개 카테고리 → 카테고리당 2개 키워드씩
        List<String> topCats = score.entrySet().stream()
                .sorted((a,b) -> Integer.compare(b.getValue(), a.getValue()))
                .limit(3)
                .map(Map.Entry::getKey)
                .collect(Collectors.toList());

        List<String> kws = new ArrayList<>();
        for (String c : topCats) {
            List<String> list = CATEGORY_KEYWORDS.getOrDefault(c, List.of());
            kws.addAll(list.stream().limit(2).toList());
        }
        return kws.stream().distinct().limit(10).toList();
    }

    private static int nz(Integer v){ return v == null ? 0 : v; }
}