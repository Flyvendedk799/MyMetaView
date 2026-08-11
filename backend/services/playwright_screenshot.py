"""Playwright-based screenshot service for capturing website screenshots."""
import logging
import json
import os
import threading
import time
from typing import Tuple, List, Dict, Any, Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError, Page, Playwright, Browser

logger = logging.getLogger(__name__)


def chromium_launch_kwargs() -> Dict[str, Any]:
    """Launch kwargs shared by every Chromium we start.

    PLAYWRIGHT_CHROMIUM_EXECUTABLE lets deployments point at a system
    Chromium when the Playwright-managed download is absent (self-hosted
    setups, dev sandboxes with a preinstalled browser).

    CAPTURE_IGNORE_TLS_ERRORS=true adds --ignore-certificate-errors, for
    development behind TLS-intercepting proxies. Never enable in production.
    """
    args = list(BrowserPool.BROWSER_ARGS)
    if os.getenv("CAPTURE_IGNORE_TLS_ERRORS", "").lower() in ("1", "true", "yes"):
        args.append("--ignore-certificate-errors")
    kwargs: Dict[str, Any] = {"headless": True, "args": args}
    executable = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE", "").strip()
    if executable and os.path.exists(executable):
        kwargs["executable_path"] = executable
    # Chromium ignores HTTP(S)_PROXY env vars; forward them explicitly when a
    # deployment opts in (egress-proxied networks, dev sandboxes).
    if os.getenv("CAPTURE_USE_ENV_PROXY", "").lower() in ("1", "true", "yes"):
        proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or ""
        if proxy:
            bypass = os.getenv("NO_PROXY") or os.getenv("no_proxy") or "localhost,127.0.0.1"
            kwargs["proxy"] = {"server": proxy, "bypass": bypass}
    return kwargs


# =============================================================================
# BROWSER POOL - Maintain warm Chromium instances for faster screenshots
# =============================================================================

class BrowserPool:
    """Pool of warm Chromium browser instances with semaphore concurrency control."""

    _instance: Optional['BrowserPool'] = None
    _lock = threading.Lock()

    POOL_SIZE = 2
    BROWSER_ARGS = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--single-process",
        "--no-zygote"
    ]

    def __init__(self):
        self._browsers: list = []
        self._semaphore = threading.Semaphore(self.POOL_SIZE)
        self._playwright: Optional[Playwright] = None
        self._initialized = False
        self._init_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> 'BrowserPool':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _ensure_initialized(self):
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            try:
                self._playwright = sync_playwright().start()
                for _ in range(self.POOL_SIZE):
                    browser = self._playwright.chromium.launch(**chromium_launch_kwargs())
                    self._browsers.append(browser)
                self._initialized = True
                logger.info(f"BrowserPool initialized with {self.POOL_SIZE} browsers")
            except Exception as e:
                logger.warning(f"BrowserPool init failed, will use on-demand browsers: {e}")
                self._initialized = False
                # Stop the half-started Playwright instance. Leaving it running
                # makes the on-demand fallback's own sync_playwright() in this
                # thread fail with "Sync API inside the asyncio loop".
                if self._playwright is not None:
                    try:
                        self._playwright.stop()
                    except Exception:
                        pass
                    self._playwright = None
                self._browsers.clear()

    def acquire(self) -> Optional[Browser]:
        """Acquire a browser from the pool. Returns None if pool not available."""
        try:
            self._ensure_initialized()
        except Exception:
            return None

        if not self._initialized or not self._browsers:
            return None

        acquired = self._semaphore.acquire(timeout=5)
        if not acquired:
            return None

        with self._init_lock:
            for browser in self._browsers:
                if browser.is_connected():
                    return browser
            # All browsers dead, try to recreate
            try:
                browser = self._playwright.chromium.launch(**chromium_launch_kwargs())
                self._browsers.append(browser)
                return browser
            except Exception:
                self._semaphore.release()
                return None

    def release(self):
        """Release a browser back to the pool."""
        self._semaphore.release()

    def shutdown(self):
        """Shutdown all browsers and playwright."""
        with self._init_lock:
            for browser in self._browsers:
                try:
                    browser.close()
                except Exception:
                    pass
            self._browsers.clear()
            if self._playwright:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
            self._initialized = False


# =============================================================================
# COOKIE POPUP HANDLING
# =============================================================================

# Common cookie consent button selectors (ordered by specificity)
COOKIE_ACCEPT_SELECTORS = [
    # Generic accept buttons
    'button[id*="accept"]',
    'button[class*="accept"]',
    'a[id*="accept"]',
    'a[class*="accept"]',
    '[data-testid*="accept"]',
    '[data-action*="accept"]',
    
    # Common cookie consent platforms
    # OneTrust
    '#onetrust-accept-btn-handler',
    '.onetrust-accept-btn-handler',
    '#accept-recommended-btn-handler',
    
    # Cookiebot
    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
    '#CybotCookiebotDialogBodyButtonAccept',
    'a#CybotCookiebotDialogBodyLevelButtonAccept',
    
    # Cookie Consent (Osano)
    '.cc-btn.cc-allow',
    '.cc-accept-all',
    '.cc-dismiss',
    
    # Quantcast
    '.qc-cmp2-summary-buttons button[mode="primary"]',
    '.qc-cmp-button',
    
    # Didomi
    '#didomi-notice-agree-button',
    '.didomi-continue-without-agreeing',
    
    # TrustArc / TRUSTe
    '.trustarc-agree-btn',
    '.truste-consent-button',
    '#truste-consent-button',
    
    # Termly
    '[data-tid="banner-accept"]',
    '.t-acceptAllButton',
    
    # CookieYes
    '[data-cky-tag="accept-button"]',
    '.cky-btn-accept',
    
    # GDPR Cookie Compliance
    '.moove-gdpr-infobar-allow-all',
    
    # Cookie Notice
    '#cookie-notice .cn-set-cookie',
    '#cookie-notice .cn-accept-cookie',
    
    # Borlabs Cookie
    '.borlabs-cookie button[data-cookie-accept]',
    
    # Complianz
    '.cmplz-accept',
    '.cmplz-btn.cmplz-accept',
    
    # Generic patterns (try these last)
    'button:has-text("Accept")',
    'button:has-text("Accept All")',
    'button:has-text("Accept all")',
    'button:has-text("Accept Cookies")',
    'button:has-text("Accept cookies")',
    'button:has-text("Allow")',
    'button:has-text("Allow All")',
    'button:has-text("Allow all")',
    'button:has-text("I Accept")',
    'button:has-text("I agree")',
    'button:has-text("I Agree")',
    'button:has-text("Got it")',
    'button:has-text("OK")',
    'button:has-text("Agree")',
    'button:has-text("Agree & Continue")',
    'button:has-text("Continue")',
    'button:has-text("Close")',
    'a:has-text("Accept")',
    'a:has-text("Accept All")',
    'a:has-text("I Agree")',
    
    # European language variants
    'button:has-text("Akzeptieren")',  # German
    'button:has-text("Accepter")',  # French
    'button:has-text("Aceptar")',  # Spanish
    'button:has-text("Accetta")',  # Italian
    'button:has-text("Godkänn")',  # Swedish
    'button:has-text("Aceitar")',  # Portuguese
    'button:has-text("Akkoord")',  # Dutch
]

# CSS selectors for cookie banners to hide
COOKIE_BANNER_HIDE_SELECTORS = [
    # OneTrust
    '#onetrust-banner-sdk',
    '#onetrust-consent-sdk',
    '.onetrust-pc-dark-filter',
    
    # Cookiebot
    '#CybotCookiebotDialog',
    '#CybotCookiebotDialogBodyUnderlay',
    
    # Cookie Consent
    '.cc-window',
    '.cc-banner',
    '.cc-overlay',
    
    # Quantcast
    '.qc-cmp2-container',
    '#qc-cmp2-ui',
    
    # Didomi
    '#didomi-host',
    '#didomi-notice',
    
    # TrustArc
    '.truste-banner',
    '#truste-consent-track',
    
    # Termly
    '[data-tid="banner"]',
    '#termly-code-snippet-support',
    
    # CookieYes
    '.cky-consent-container',
    '.cky-modal',
    
    # Generic patterns
    '[class*="cookie-banner"]',
    '[class*="cookie-consent"]',
    '[class*="cookie-notice"]',
    '[class*="cookie-popup"]',
    '[class*="cookie-modal"]',
    '[class*="gdpr-banner"]',
    '[class*="gdpr-consent"]',
    '[class*="gdpr-notice"]',
    '[class*="consent-banner"]',
    '[class*="consent-modal"]',
    '[class*="privacy-banner"]',
    '[class*="privacy-notice"]',
    '[id*="cookie-banner"]',
    '[id*="cookie-consent"]',
    '[id*="cookie-notice"]',
    '[id*="cookie-popup"]',
    '[id*="gdpr-banner"]',
    '[id*="gdpr-consent"]',
    '[id*="consent-banner"]',
    '[id*="privacy-banner"]',
    
    # Overlay/backdrop
    '[class*="cookie-overlay"]',
    '[class*="consent-overlay"]',
    '[class*="modal-backdrop"]',
]


def dismiss_cookie_popups(page: Page, timeout: int = 3000) -> bool:
    """
    Attempt to dismiss cookie consent popups by clicking accept buttons.
    
    Args:
        page: Playwright page object
        timeout: Maximum time to wait for each button (ms)
        
    Returns:
        True if a cookie popup was dismissed, False otherwise
    """
    dismissed = False
    
    for selector in COOKIE_ACCEPT_SELECTORS:
        try:
            # Check if element exists and is visible
            element = page.query_selector(selector)
            if element and element.is_visible():
                # Try to click it
                element.click(timeout=timeout)
                logger.info(f"🍪 Dismissed cookie popup using selector: {selector}")
                dismissed = True
                # Wait for popup to disappear
                page.wait_for_timeout(500)
                break
        except Exception as e:
            # Element might not be clickable or selector didn't match
            continue
    
    return dismissed


def hide_cookie_banners(page: Page) -> int:
    """
    Hide cookie banners using CSS injection (fallback method).
    
    Args:
        page: Playwright page object
        
    Returns:
        Number of elements hidden
    """
    hidden_count = 0
    
    # Build CSS to hide all cookie banners
    css_rules = []
    for selector in COOKIE_BANNER_HIDE_SELECTORS:
        css_rules.append(f'{selector} {{ display: none !important; visibility: hidden !important; opacity: 0 !important; }}')
    
    # Add rule to remove any fixed overlays that might be blocking content
    css_rules.append('''
        body.cookie-banner-open { overflow: auto !important; }
        html.cookie-banner-open { overflow: auto !important; }
        .modal-open { overflow: auto !important; }
    ''')
    
    css_content = '\n'.join(css_rules)
    
    try:
        # Inject CSS to hide banners
        page.add_style_tag(content=css_content)
        
        # Also try to remove elements directly for more aggressive hiding
        script = '''
        () => {
            const selectors = ''' + json.dumps(COOKIE_BANNER_HIDE_SELECTORS[:20]) + ''';
            let count = 0;
            selectors.forEach(selector => {
                try {
                    document.querySelectorAll(selector).forEach(el => {
                        el.style.display = 'none';
                        el.style.visibility = 'hidden';
                        el.remove();
                        count++;
                    });
                } catch (e) {}
            });
            
            // Also remove any elements with cookie-related attributes
            document.querySelectorAll('[aria-label*="cookie" i], [aria-label*="consent" i], [aria-label*="gdpr" i]').forEach(el => {
                el.style.display = 'none';
                count++;
            });
            
            // Remove body scroll lock
            document.body.style.overflow = 'auto';
            document.documentElement.style.overflow = 'auto';
            
            return count;
        }
        '''
        
        hidden_count = page.evaluate(script)
        
        if hidden_count > 0:
            logger.info(f"🍪 Hidden {hidden_count} cookie-related elements via CSS/JS")
            
    except Exception as e:
        logger.warning(f"Failed to hide cookie banners: {e}")
    
    return hidden_count


def handle_cookie_popups(page: Page) -> bool:
    """
    Main function to handle cookie popups on a page.
    
    First tries to dismiss popups by clicking accept buttons,
    then falls back to hiding them with CSS.
    
    Args:
        page: Playwright page object
        
    Returns:
        True if any cookie handling was performed
    """
    handled = False
    
    # Wait a moment for any lazy-loaded popups to appear
    page.wait_for_timeout(1000)
    
    # First, try to click accept buttons (preferred method)
    if dismiss_cookie_popups(page):
        handled = True
    
    # Then, hide any remaining banners with CSS
    if hide_cookie_banners(page) > 0:
        handled = True
    
    # Small delay to let any animations finish
    if handled:
        page.wait_for_timeout(500)
    
    return handled


def capture_screenshot(url: str) -> bytes:
    """
    Uses Playwright Chromium to generate an accurate screenshot of a webpage.
    Returns raw PNG bytes. Uses BrowserPool for warm browser reuse when available.

    Args:
        url: URL to capture screenshot of

    Returns:
        Raw image bytes (PNG format)

    Raises:
        Exception: If screenshot capture fails with descriptive error message
    """
    # Try BrowserPool first for faster startup
    pool = BrowserPool.get_instance()
    pooled_browser = pool.acquire()

    if pooled_browser:
        try:
            return _capture_screenshot_with_browser(pooled_browser, url)
        except Exception:
            pool.release()
            raise
        finally:
            pool.release()

    # Fallback: launch a fresh browser
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(**chromium_launch_kwargs())
            except Exception as e:
                logger.error(f"Failed to launch browser for {url}: {e}")
                raise Exception(f"Failed to start browser: {str(e)}")

            try:
                return _capture_screenshot_with_browser(browser, url)
            finally:
                browser.close()

    except Exception as e:
        if "Failed to" not in str(e) and "error" not in str(e).lower():
            logger.error(f"Unexpected error capturing screenshot for {url}: {e}")
            raise Exception(f"Failed to capture screenshot: {str(e)}")
        raise


def _capture_screenshot_with_browser(browser: Browser, url: str) -> bytes:
    """Core screenshot logic using an already-launched browser."""
    page = browser.new_page(
        viewport={"width": 1200, "height": 630},
        device_scale_factor=2
    )

    try:
        try:
            # Try domcontentloaded first (fastest)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(1500)
            except PlaywrightTimeoutError:
                logger.warning(f"DOMContentLoaded timeout for {url}, trying 'load' strategy")
                page.goto(url, wait_until="load", timeout=15000)
                page.wait_for_timeout(2000)
        except PlaywrightTimeoutError as e:
            logger.error(f"Page navigation timeout for {url} (both strategies failed): {e}")
            raise Exception(f"Page load timeout: The website took too long to load. Please try again or check if the URL is accessible.")
        except PlaywrightError as e:
            logger.error(f"Playwright error navigating to {url}: {e}")
            error_msg = str(e)
            if "net::ERR_CERT_AUTHORITY_INVALID" in error_msg or "SSL" in error_msg:
                raise Exception(f"SSL certificate error: The website's certificate is invalid or self-signed. Cannot capture screenshot.")
            elif "net::ERR_NAME_NOT_RESOLVED" in error_msg:
                raise Exception(f"DNS error: Could not resolve the domain name. Please check the URL.")
            elif "net::ERR_CONNECTION_REFUSED" in error_msg:
                raise Exception(f"Connection refused: The website is not accessible. Please check if the URL is correct.")
            else:
                raise Exception(f"Failed to load page: {error_msg}")

        # HANDLE COOKIE POPUPS before screenshot
        try:
            cookie_handled = handle_cookie_popups(page)
            if cookie_handled:
                logger.info(f"Cookie popup handled for {url}")
        except Exception as e:
            logger.warning(f"Cookie popup handling failed (non-critical): {e}")

        # Capture viewport screenshot
        try:
            screenshot = page.screenshot(type="png", full_page=False)
        except Exception as e:
            logger.error(f"Screenshot capture failed for {url}: {e}")
            raise Exception(f"Failed to capture screenshot: {str(e)}")

        return screenshot

    finally:
        page.close()


def _extract_scientific_dom(page: Page) -> Dict[str, Any]:
    """
    Injects JS to extract the structural truth of the page.
    Finds the biggest texts, CTAs, and images, returning their exact computed styles and coordinates.
    """
    script = """
    () => {
        const getComputedStyleData = (el) => {
            const styles = window.getComputedStyle(el);
            return {
                fontSize: styles.fontSize,
                fontWeight: styles.fontWeight,
                fontFamily: styles.fontFamily,
                color: styles.color,
                backgroundColor: styles.backgroundColor,
                textAlign: styles.textAlign,
                lineHeight: styles.lineHeight,
                borderRadius: styles.borderRadius,
                display: styles.display
            };
        };

        const getRectData = (el) => {
            const rect = el.getBoundingClientRect();
            return {
                x: rect.x + window.scrollX,
                y: rect.y + window.scrollY,
                width: rect.width,
                height: rect.height,
                visible: rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).opacity !== "0"
            };
        };

        // 1. Analyze typography hierarchy
        const texts = Array.from(document.querySelectorAll('h1, h2, h3, p, span, a'))
            .filter(el => {
                const rect = el.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 && el.textContent.trim().length > 0;
            })
            .map(el => {
                const style = window.getComputedStyle(el);
                const fontSizePx = parseFloat(style.fontSize);
                return {
                    tagName: el.tagName.toLowerCase(),
                    text: el.textContent.trim(),
                    fontSizePx: fontSizePx,
                    isBold: parseInt(style.fontWeight) > 600 || style.fontWeight === 'bold',
                    rect: getRectData(el),
                    styles: getComputedStyleData(el)
                };
            })
            // Sort by size (biggest first)
            .sort((a, b) => b.fontSizePx - a.fontSizePx);

        // 2. Identify potential CTAs/Buttons
        const buttons = Array.from(document.querySelectorAll('button, a, input[type="submit"], [role="button"]'))
            .filter(el => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                // Buttons generally have background colors different from transparent, and some padding
                return rect.width > 20 && rect.height > 10 && 
                       el.textContent.trim().length > 0 &&
                       style.display !== 'none' &&
                       style.opacity !== '0';
            })
            .map(el => {
                const text = el.textContent.trim() || el.value || '';
                return {
                    tagName: el.tagName.toLowerCase(),
                    text: text,
                    rect: getRectData(el),
                    styles: getComputedStyleData(el),
                    href: el.href || null
                };
            });

        // 3. Identify main images
        const images = Array.from(document.querySelectorAll('img, svg'))
            .filter(el => {
                const rect = el.getBoundingClientRect();
                return rect.width > 50 && rect.height > 50; // Ignore tiny icons initially
            })
            .map(el => {
                return {
                    tagName: el.tagName.toLowerCase(),
                    src: el.src || null,
                    alt: el.alt || null,
                    rect: getRectData(el),
                    area: getRectData(el).width * getRectData(el).height
                };
            })
            .sort((a, b) => b.area - a.area); // Largest first

        // Helper: Is element in the hero section? (Top 800px)
        const inHero = (rect) => rect.y < 800 && rect.visible;

        return {
            pageWidth: document.documentElement.scrollWidth,
            pageHeight: document.documentElement.scrollHeight,
            viewportWidth: window.innerWidth,
            viewportHeight: window.innerHeight,
            hierarchy: {
                primary_headline: texts.find(t => inHero(t.rect) && t.tagName.match(/h1|h2/i)) || texts[0],
                secondary_headlines: texts.filter(t => inHero(t.rect) && t.fontSizePx > 18).slice(1, 4),
            },
            interaction: {
                ctas: buttons.filter(b => inHero(b.rect)).slice(0, 5)
            },
            media: {
                hero_images: images.filter(i => inHero(i.rect)).slice(0, 3)
            },
            raw_top_texts: texts.slice(0, 10)
        };
    }
    """
    try:
        # Wrap evaluation in a race with a timeout
        logger.info("🧬 Extracting scientific DOM boundaries...")
        # Note: Playwright's evaluate is synchronous but respects the page timeout
        # However, for safety we can wrap the script to return early if it bogs down
        # For now, evaluate with a reasonably guarded try/except block.
        return page.evaluate(script)
    except PlaywrightTimeoutError:
        logger.warning("🧬 Scientific DOM extraction TIMED OUT. Page might be too complex. Proceeding with empty DOM struct.")
        return {}
    except Exception as e:
        logger.warning(f"Failed to extract scientific DOM boundaries: {e}")
        return {}


# Playwright's sync API objects are bound to the thread that created them.
# All captures therefore run on ONE persistent worker thread: warm pool
# browsers stay usable across requests instead of dying with "cannot switch
# to a different thread" on every capture after the first.
from concurrent.futures import ThreadPoolExecutor as _CaptureExecutorCls

_capture_executor = _CaptureExecutorCls(max_workers=1, thread_name_prefix="mmv-capture")


def capture_screenshot_and_html(url: str) -> Tuple[bytes, str, Dict[str, Any]]:
    """
    Capture screenshot, HTML content, and Scientific DOM Mapping from a webpage.
    Uses BrowserPool for warm browser reuse when available.

    Thread-safe: dispatches to the dedicated capture thread, so callers may
    invoke it from any thread (FastAPI worker threads, per-attempt executors).

    Args:
        url: URL to capture

    Returns:
        Tuple of (screenshot_bytes, html_content, dom_data_dict)

    Raises:
        Exception: If capture fails with descriptive error message
    """
    if threading.current_thread().name.startswith("mmv-capture"):
        # Already on the capture thread (nested call) — run directly.
        return _capture_screenshot_and_html_pinned(url)
    return _capture_executor.submit(_capture_screenshot_and_html_pinned, url).result()


def _capture_screenshot_and_html_pinned(url: str) -> Tuple[bytes, str, Dict[str, Any]]:
    """Capture implementation; must only run on the dedicated capture thread."""
    # Try BrowserPool first for faster startup
    pool = BrowserPool.get_instance()
    pooled_browser = pool.acquire()

    if pooled_browser:
        try:
            return _capture_screenshot_and_html_with_browser(pooled_browser, url)
        finally:
            pool.release()

    # Fallback: launch a fresh browser
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(**chromium_launch_kwargs())
            except Exception as e:
                logger.error(f"Failed to launch browser for {url}: {e}")
                raise Exception(f"Failed to start browser: {str(e)}")

            try:
                return _capture_screenshot_and_html_with_browser(browser, url)
            finally:
                browser.close()

    except Exception as e:
        if "Failed to" not in str(e) and "error" not in str(e).lower():
            logger.error(f"Unexpected error capturing screenshot/HTML for {url}: {e}")
            raise Exception(f"Failed to capture screenshot: {str(e)}")
        raise


# A realistic browser identity: headless Chromium's default UA gets many sites
# to serve bot walls, interstitials, or stripped-down pages, which then get
# faithfully screenshotted and described.
CAPTURE_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
CAPTURE_HEADERS = {"Accept-Language": "en-US,en;q=0.9"}


def _capture_screenshot_and_html_with_browser(browser: Browser, url: str) -> Tuple[bytes, str, Dict[str, Any]]:
    """Core screenshot+HTML capture logic using an already-launched browser."""
    page = browser.new_page(
        viewport={"width": 1200, "height": 630},
        device_scale_factor=2,
        user_agent=CAPTURE_USER_AGENT,
        extra_http_headers=CAPTURE_HEADERS,
    )

    try:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(1500)
        except PlaywrightTimeoutError as e:
            logger.warning(f"DOMContentLoaded timeout for {url}, trying 'load' strategy: {e}")
            try:
                page.goto(url, wait_until="load", timeout=15000)
                page.wait_for_timeout(2000)
            except PlaywrightTimeoutError as e2:
                logger.error(f"Page navigation timeout for {url} (both strategies failed): {e2}")
                raise Exception(f"Page load timeout: The website took too long to load.")
        except PlaywrightError as e:
            logger.error(f"Playwright error navigating to {url}: {e}")
            error_msg = str(e)
            if "net::ERR_CERT_AUTHORITY_INVALID" in error_msg or "SSL" in error_msg:
                # SSL fallback: retry with ignore_https_errors
                logger.warning(f"SSL error for {url}, retrying with ignore_https_errors")
                try:
                    page.close()
                    page = browser.new_page(
                        viewport={"width": 1200, "height": 630},
                        device_scale_factor=2,
                        user_agent=CAPTURE_USER_AGENT,
                        extra_http_headers=CAPTURE_HEADERS,
                        ignore_https_errors=True
                    )
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(1500)
                except Exception:
                    raise Exception(f"SSL certificate error: {error_msg}")
            elif "net::ERR_NAME_NOT_RESOLVED" in error_msg:
                raise Exception(f"DNS error: Could not resolve the domain name.")
            else:
                raise Exception(f"Failed to load page: {error_msg}")

        # HANDLE COOKIE POPUPS before screenshot
        try:
            cookie_handled = handle_cookie_popups(page)
            if cookie_handled:
                logger.info(f"Cookie popup handled for {url}")
        except Exception as e:
            logger.warning(f"Cookie popup handling failed (non-critical): {e}")

        # Extract Scientific DOM
        try:
            dom_data = _extract_scientific_dom(page)
        except Exception as e:
            logger.error(f"Failed to extract DOM data for {url}: {e}")
            dom_data = {}

        # Capture screenshot and HTML
        try:
            screenshot = page.screenshot(type="png", full_page=False)
            html_content = page.content()
        except Exception as e:
            logger.error(f"Failed to capture screenshot/HTML for {url}: {e}")
            raise Exception(f"Failed to capture screenshot: {str(e)}")

        return screenshot, html_content, dom_data

    finally:
        page.close()

