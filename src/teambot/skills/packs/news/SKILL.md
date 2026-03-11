---
name: news
description: "Look up the latest news for the user from specified news sites. Provides authoritative URLs for politics, finance, society, world, tech, sports, and entertainment. Use web_fetch for direct URL retrieval and summarize the fetched content."
---

# News Reference

When the user asks for "latest news", "what's in the news today", or "news in category X", use the **web_fetch** tool with the categories and URLs below, then extract headlines and key points from the fetched page content and reply to the user.

## Categories and Sources

| Category      | Source                    | URL |
|---------------|---------------------------|-----|
| **Politics**  | People's Daily · CPC News | https://cpc.people.com.cn/ |
| **Finance**   | China Economic Net        | http://www.ce.cn/ |
| **Society**   | China News · Society      | https://www.chinanews.com/society/ |
| **World**     | CGTN                      | https://www.cgtn.com/ |
| **Tech**      | Science and Technology Daily | https://www.stdaily.com/ |
| **Sports**    | CCTV Sports               | https://sports.cctv.com/ |
| **Entertainment** | Sina Entertainment   | https://ent.sina.com.cn/ |

## How to Use (web_fetch)

1. **Clarify the user's need**: Determine which category or categories (politics / finance / society / world / tech / sports / entertainment), or pick 1–2 to fetch.
2. **Pick the URL**: Use the URL from the table for that category; for multiple categories, repeat the steps below for each URL.
3. **Fetch the page**: Call **web_fetch** with:
   ```json
   {"url": "https://www.chinanews.com/society/"}
   ```
   Replace `url` with the corresponding URL from the table.
4. **Extract the content**: Use the returned page content to identify headlines, dates, and summaries.
5. **Summarize the reply**: Organize a short list (headline + one or two sentences + source) by time or importance; if a site is unreachable or times out, say so and suggest another source.

## Notes

- Page structure may change when sites are updated; if extraction fails, say so and suggest the user open the link directly.
- When visiting multiple categories, call `web_fetch` separately for each URL to avoid mixing content from different pages.
- You may include the original link in the reply so the user can open it.
