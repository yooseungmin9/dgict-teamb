package com.bgroup.news.config;

import org.springframework.stereotype.Component;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.ModelAttribute;

/**
 * [입문자용 설명]
 * - 모든 컨트롤러의 뷰 렌더링 전에 공통 헤더용 모델 값을 주입합니다.
 * - 개별 컨트롤러에서 같은 키를 addAttribute 하면 이 기본값을 덮어씁니다.
 */
@ControllerAdvice
@Component
public class GlobalHeaderAttributes {

    @ModelAttribute
    public void injectHeaderDefaults(Model model) {
        model.addAttribute("pageTitle", "EcoNews AI");
        model.addAttribute("subTitle","AI 기반 경제 뉴스 분석");
        model.addAttribute("nav1","대시보드");
        model.addAttribute("nav2","오늘의 뉴스");
        model.addAttribute("nav3","감성 분석");
        model.addAttribute("nav4","글로벌 모니터링");
        model.addAttribute("nav5","트랜드 예측");
        model.addAttribute("nav6","챗봇");
        model.addAttribute("nav7","추천");
    }
}

/**
 * [간단 테스트]
 * - 별도 설정 없이도 헤더 텍스트가 항상 표시됩니다.
 * - 특정 페이지에서 타이틀을 바꾸려면 해당 컨트롤러에서 같은 키로 addAttribute 하세요.
 */
