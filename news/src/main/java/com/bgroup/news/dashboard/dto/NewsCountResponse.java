package com.bgroup.news.dashboard.dto;

import java.time.OffsetDateTime;

public class NewsCountResponse {
    public boolean ok = true;
    public String collection;
    public long total;
    public long today;
    public long last7;
    public OffsetDateTime updated_at;

    public NewsCountResponse(String collection, long total, long today, long last7, OffsetDateTime updated_at) {
        this.collection = collection;
        this.total = total;
        this.today = today;
        this.last7 = last7;
        this.updated_at = updated_at;
    }
}
