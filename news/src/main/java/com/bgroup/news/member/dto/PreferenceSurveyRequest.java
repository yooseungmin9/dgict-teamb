package com.bgroup.news.member.dto;

public record PreferenceSurveyRequest(
        String mainSource,
        String portal,

        java.util.List<String> mainSources,
        java.util.List<String> portals,

        java.util.List<String> sns,
        java.util.List<String> video,
        java.util.List<String> ott
) {}