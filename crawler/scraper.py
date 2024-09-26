import time as tme
import traceback

import requests
from bs4 import BeautifulSoup

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait


class Scraper:

    def __init__(self, crawler_instance):
        self.crawler = crawler_instance

    def scrape(self, source: str) -> dict:
        dict = {}
        return dict