package com.bgroup.news.analysis.dto;

import lombok.*;

@Data
@AllArgsConstructor
@NoArgsConstructor
@Builder
public class CommentItem { private String text; private String emotion; }