import io
from typing import Any, Iterator
from tools.parsers.lib import data

import scrapy
from scrapy import http

from tools.spiders.lib import spider
from tools.parsers import google

_INDEX_PAGE_URL = 'https://sustainability.google/reports/'


class GoogleSpider(spider.BoaViztaSpider):

    name = 'Google'

    start_urls = [_INDEX_PAGE_URL]

    import json

    def parse(self, response: http.Response, **unused_kwargs: Any) -> Iterator[scrapy.Request]:
        # Step 1: Extract JSON data embedded in HTML
        json_text = response.xpath('//script[@id="initial-data"]/text()').get()

        if not json_text:
            self.logger.error("No initial-data JSON found on the page.")
            return

        data_blob = json.loads(json_text)

        # Step 2: Navigate JSON to find product environment reports
        try:
            report_items = data_blob['allRepoItems']
        except KeyError:
            self.logger.error("Expected 'allRepoItems' key not found in JSON.")
            return

        self.logger.info(f"Found {len(report_items)} report items in initial-data JSON.")

        for item in report_items:
            # Filter only Product Environment Reports
            if item.get('repoCategory') == "Product Environment Reports":
                url = item.get('repoFileUrl')
                if not url:
                    continue
                report_url = response.urljoin(url)

                if self._should_skip(report_url):
                    continue

                yield scrapy.Request(report_url, callback=self.parse_carbon_footprint)


    def parse_main_js(self, response: http.Response, **unused_kwargs: Any) -> Iterator[scrapy.Request]:
        # Step 2: Extract HTML from JavaScript
        # Google embeds the HTML into JS string, like: t=decodeURIComponent("<div>...</div>")
        html_content = response.text

        # Regex to extract HTML string
        match = re.search(r'decodeURIComponent\("(.+?)"\)', html_content)
        if match:
            html_encoded = match.group(1)
            html_decoded = html.unescape(html_encoded)
            fake_response = response.replace(body=html_decoded)

            # Step 3: Parse the HTML snippet as a normal response
            for link in fake_response.css('a[href$=".pdf"]::attr(href)'):
                pdf_url = response.urljoin(link.get())
                if self._should_skip(pdf_url):
                    continue
                yield scrapy.Request(pdf_url, callback=self.parse_carbon_footprint)
        else:
            self.logger.error("No HTML content found inside main.js.")


    def parse_carbon_footprint(
        self, response: http.Response, **unused_kwargs: Any,
    ) -> Iterator[Any]:
        """Parse a Google Product Carbon footprint document."""
        for device in google.parse(io.BytesIO(response.body), response.url):
            device.data['sources'] = response.url
            device.data['sources_hash'] = data.md5(io.BytesIO(response.body))
            yield device.reorder().data
