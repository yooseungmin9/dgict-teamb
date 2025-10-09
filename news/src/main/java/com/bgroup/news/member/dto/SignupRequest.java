package com.bgroup.news.member.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class SignupRequest {
    private String id;
    private String password;
    private String name;
    private Integer birthYear;
    private String phone;
    private String region;
    private String gender;
}
