from playwright.sync_api import Browser, Page, Playwright, sync_playwright


class LocalBrowser:
    def __init__(self):
        self.playwright: Playwright = sync_playwright().start()
        self.browser: Browser = self.playwright.chromium.launch()

    def new_page(self) -> Page:
        return self.browser.new_page()

    def close(self):
        self.browser.close()
        self.playwright.stop()

    def get_browser(self) -> Browser:
        return self.browser

    def get_page(self) -> Page:
        return self.new_page()


browser = LocalBrowser()

