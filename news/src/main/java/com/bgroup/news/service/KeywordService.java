/*    */ package com.bgroup.news.service;
/*    */ 
/*    */ import org.springframework.beans.factory.annotation.Value;
/*    */ import org.springframework.stereotype.Service;
/*    */ import org.springframework.web.reactive.function.client.WebClient;
/*    */ import reactor.core.publisher.Mono;
/*    */ 
/*    */ 
/*    */ @Service
/*    */ public class KeywordService
/*    */ {
/*    */   private final WebClient webClient;
/*    */   
/*    */   public KeywordService(WebClient.Builder builder, @Value("${fastapi.base-url}") String baseUrl) {
/* 15 */     this.webClient = builder.baseUrl(baseUrl).build();
/*    */   }
/*    */   
/*    */   public Mono<String> fetchKeywords() {
/* 19 */     return this.webClient.get()
/* 20 */       .uri("/keywords", new Object[0])
/* 21 */       .retrieve()
/* 22 */       .bodyToMono(String.class);
/*    */   }
/*    */ }


/* Location:              C:\Dgict_TeamB_Project\news\build\classes\java\main\myproject.jar!\com\bgroup\news\service\KeywordService.class
 * Java compiler version: 17 (61.0)
 * JD-Core Version:       1.1.3
 */