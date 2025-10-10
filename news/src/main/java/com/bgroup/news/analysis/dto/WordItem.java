package com.bgroup.news.analysis.dto;

import lombok.*;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class WordItem { private String text; private Integer count; }