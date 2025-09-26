/*    */ package com.bgroup.news.config;
/*    */ 
/*    */ import org.springframework.beans.factory.annotation.Value;
/*    */ import org.springframework.context.annotation.Bean;
/*    */ import org.springframework.context.annotation.Configuration;
/*    */ import org.springframework.http.codec.ClientCodecConfigurer;
/*    */ import org.springframework.web.reactive.function.client.ExchangeStrategies;
/*    */ import org.springframework.web.reactive.function.client.WebClient;
/*    */ 
/*    */ 
/*    */ 
/*    */ @Configuration
/*    */ public class WebClientConfig
/*    */ {
/*    */   @Bean
/*    */   public WebClient fastApiClient(@Value("${fastapi.base-url}") String baseUrl) {
/* 17 */     ExchangeStrategies strategies = ExchangeStrategies.builder().codecs(c -> c.defaultCodecs().maxInMemorySize(2097152)).build();
/*    */     
/* 19 */     return WebClient.builder()
/* 20 */       .baseUrl(baseUrl)
/* 21 */       .exchangeStrategies(strategies)
/* 22 */       .build();
/*    */   }
/*    */ }


/* Location:              C:\Dgict_TeamB_Project\news\build\classes\java\main\myproject.jar!\com\bgroup\news\config\WebClientConfig.class
 * Java compiler version: 17 (61.0)
 * JD-Core Version:       1.1.3
 */