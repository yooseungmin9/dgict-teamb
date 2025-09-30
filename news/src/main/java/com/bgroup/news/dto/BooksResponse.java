package com.bgroup.news.dto;

import lombok.Data;
import java.util.List;

@Data
public class BooksResponse {
    private int count;
    private List<BookItem> items;

    @Data
    public static class BookItem {
        private String title;
        private String author;
        private String pubDate;
        private String link;
        private String cover;
    }
}
