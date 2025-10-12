package com.bgroup.news.member.dto;

import java.util.List;
import java.util.Map;

public record PreferenceSurveyRequest(
        String mainSource,                    // "portal" | "sns" | "youtube" | "ott" | "pressSite"
        String portal,                        // "Naver" | "Daum" | "Google"
        List<String> sns,                     // ["Instagram","X","TikTok"]
        List<String> video,                   // ["YouTube","TikTok"]
        List<String> ott,                     // ["Netflix", ...]
        Map<String, Double> categoryWeights,  // {"economy":1.0,"stock":0.8,...}
        String metro,                         // "수도권"
        String city,                          // "성남"
        Double regionLevel                    // 0.0~1.0
) { }