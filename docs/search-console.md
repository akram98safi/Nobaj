# Google Search Console setup

Nobaj publishes its sitemap at `https://nobaj.com/sitemap.xml`. It includes the English and localized landing pages, the three tool pages in all 13 languages, and the English and Arabic privacy, terms, and contact pages.

## Verify the site

1. Add `nobaj.com` as a **Domain property** in Google Search Console and complete the DNS verification with the DNS provider. This covers both HTTP/HTTPS and subdomains.
2. If DNS access is unavailable, add the `https://nobaj.com/` URL-prefix property and choose the HTML tag method.
3. Copy only the verification token (the value of the tag's `content` attribute) into `GOOGLE_SITE_VERIFICATION` in Nobaj's server environment, then restart Nobaj. The public page will emit Google's verification meta tag.
4. In Search Console, submit `https://nobaj.com/sitemap.xml` and inspect the English, Arabic, and one other localized tool URL.

Submitting a sitemap helps Google discover URLs; it does not guarantee that they will be indexed. Use the Page indexing, Search results, and Core Web Vitals reports to follow actual crawling and performance.

Do not commit a verification token to Git. Keep it in the server environment, like other deployment secrets.
