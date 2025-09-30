package com.bgroup.news.dto;

import lombok.Data;
import java.util.List;
import java.util.Map;

@Data
public class YoutubeResponse {
    private int count;
    private List<Item> items;
    private String nextPageToken;
    private String prevPageToken;

    @Data
    public static class Item {
        private String videoId;
        private String title;
        private String channelTitle;
        private String publishedAt;
        private String thumbnail;
        private String url;
        private Map<String, String> statistics; // viewCount, likeCount, commentCount
    }
}
