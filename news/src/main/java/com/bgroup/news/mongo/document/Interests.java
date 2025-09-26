package com.bgroup.news.mongo.document;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.Builder;

/**
 * 회원 관심사 서브문서
 * (MongoDB 내 MemberDoc의 필드로 포함되어 저장됨)
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Interests {

    /** 거시경제 */
    private int goshi;

    /** 국제경제 */
    private int gukje;

    /** 정책/제도 */
    private int jeongchaek;

    /** 산업/기업 */
    private int saneob;

    /** 금융/투자 */
    private int geumyung;

    /** 기타 */
    private int etc;
}
