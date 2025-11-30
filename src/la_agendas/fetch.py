"""HTTP fetching with robots.txt checking, retries, and timeouts."""

import logging
import time
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class Fetcher:
    """HTTP fetcher with robots.txt support and retries."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 60,
        user_agent: str = "la-county-agendas-scraper/0.1.0",
        rate_limit: float = 2.0,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.user_agent = user_agent
        self.rate_limit = rate_limit  # requests per second
        self.last_request_time = 0.0
        self.robots_parser = None
        self._check_robots()

    def _check_robots(self) -> None:
        """Check robots.txt and initialize parser."""
        try:
            robots_url = urljoin(self.base_url, "/robots.txt")
            rp = robotparser.RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            self.robots_parser = rp
            if not rp.can_fetch(self.user_agent, self.base_url):
                logger.warning(
                    f"robots.txt disallows fetching {self.base_url} for {self.user_agent}"
                )
            else:
                logger.info(f"robots.txt allows fetching {self.base_url}")
        except Exception as e:
            logger.warning(f"Could not fetch robots.txt: {e}. Proceeding anyway.")

    def _rate_limit_wait(self) -> None:
        """Wait to respect rate limit."""
        now = time.time()
        elapsed = now - self.last_request_time
        min_interval = 1.0 / self.rate_limit
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def fetch(self, url: str) -> tuple[str, bytes]:
        """
        Fetch URL and return (content_type, content).
        Raises exception on failure after retries.
        """
        # Check robots.txt if available
        if self.robots_parser and not self.robots_parser.can_fetch(
            self.user_agent, url
        ):
            logger.warning(f"robots.txt disallows fetching {url}")
            # Don't raise, but log warning

        self._rate_limit_wait()

        headers = {"User-Agent": self.user_agent}
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";")[0]
                return content_type, response.content
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching {url}: {e}")
            raise

    def fetch_html(self, url: str) -> str:
        """Fetch URL and return HTML as string."""
        content_type, content = self.fetch(url)
        if "html" not in content_type.lower() and "text" not in content_type.lower():
            logger.warning(
                f"Unexpected content-type {content_type} for {url}, treating as HTML"
            )
        return content.decode("utf-8", errors="replace")

    def is_same_domain(self, url: str) -> bool:
        """Check if URL is on the same domain as base_url."""
        base_domain = urlparse(self.base_url).netloc
        url_domain = urlparse(url).netloc
        return base_domain == url_domain

