/*    */ package com.bgroup.news.config;
/*    */ 
/*    */ import org.springframework.stereotype.Component;
/*    */ import org.springframework.ui.Model;
/*    */ import org.springframework.web.bind.annotation.ControllerAdvice;
/*    */ import org.springframework.web.bind.annotation.ModelAttribute;
/*    */ 
/*    */ 
/*    */ 
/*    */ 
/*    */ 
/*    */ 
/*    */ @ControllerAdvice
/*    */ @Component
/*    */ public class HeaderAttributes
/*    */ {
/*    */   @ModelAttribute
/*    */   public void injectHeaderDefaults(Model model) {
/* 19 */     model.addAttribute("pageTitle", "EcoNews AI");
/* 20 */     model.addAttribute("subTitle", "AI 기반 경제 뉴스 분석");
/* 21 */     model.addAttribute("nav1", "대시보드");
/* 22 */     model.addAttribute("nav2", "오늘의 뉴스");
/* 23 */     model.addAttribute("nav3", "감성 분석");
/* 24 */     model.addAttribute("nav4", "글로벌 모니터링");
/* 25 */     model.addAttribute("nav5", "트랜드 예측");
/* 26 */     model.addAttribute("nav6", "챗봇");
/* 27 */     model.addAttribute("nav7", "추천");
/*    */   }
/*    */ }


/* Location:              C:\Dgict_TeamB_Project\news\build\classes\java\main\myproject.jar!\com\bgroup\news\config\HeaderAttributes.class
 * Java compiler version: 17 (61.0)
 * JD-Core Version:       1.1.3
 */