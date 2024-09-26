import argparse
import sys
import os
import time as tme

import pandas as pd
import numpy as np

from datetime import datetime, date, time
from dateutil.relativedelta import relativedelta

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from crawler import utils, scraper

class Input:
    
    def __init__(self, today: date, now: datetime):

        self.path_to_chromedriver_loc = 'crawler/path_to_chromedriver.txt'
        self.path_to_sources = 'data/sources.csv'
        self.path_to_sources_out_of_order = 'crawler/sources_out_of_order.txt'
        self.path_to_search_terms = 'data/search_terms.csv'

        self.NOW = now
        self.TODAY = today

    def get_chromedriver_loc(self) -> str:
        return open(self.path_to_chromedriver_loc, 'r').readline().strip()

    def get_sources(self) -> list:
                
        lines = open(self.path_to_sources, 'r').readlines()
        sources = [line.split(',')[0].strip() for line in lines if "yes" in line.split(',')[1]]
            
        return sources
    
    def get_sources_out_of_order(self) -> list:
        
        lines = open(self.path_to_sources_out_of_order, 'r').readlines()
        sources_out_of_order = [line.strip() for line in lines]
            
        return sources_out_of_order
    
    def get_search_terms(self) -> list:

        lines = open(self.path_to_search_terms, 'r').readlines()
        search_terms = [line.strip() for line in lines]

        return search_terms
    
    def get_date_interval(self) -> tuple:

        # Gets the start and end date of the desired interval from the command line arguments

        # Default is 1 month back from today's date.
        date_end = self.NOW
        date_init = date_end - relativedelta(months=1)

        # Script arguments
        parser = argparse.ArgumentParser()

        parser.add_argument('-i', type=str, metavar="date_init", help="Initial date of the interval we want to observe")
        parser.add_argument('-e', type=str, metavar="date_end", help="Final date of the interval we want to observe")

        args = parser.parse_args()       

        if args.e is not None:
            date_end = datetime.strptime(args.e, '%Y%m%d').date()
            if date_end == self.TODAY:
                date_end = datetime.combine(date_end, self.NOW.time())
            else:
                date_end = datetime.combine(date_end, time(23, 59, 59))
            date_init = date_end - relativedelta(months=1)
        if args.i is not None:
            date_init = datetime.strptime(args.i, '%Y%m%d')

        return (date_init, date_end)

class Output:

    def __init__(self):

        self.path = 'data/scraping_results/'
        self.filepath = f"{self.path}{self.define_filename()}"
        self.headers = [
            "Datetime added",
            "Journal",
            "Found by",
            "Datetime",
            "Category",
            "Type",
            "Title",
            "Link",
            "Subtitle",
            "Content",
            "Comment ID",
            "Comment author",
            "Comment datetime displayed",
            "Comment datetime",
            "Comment content",
            "Comment in answer to",
            "Comment likes",
            "Comment dislikes"
        ]

        self.check_filepath()

    def define_filename(self) -> str:
        return f"{datetime.now().strftime('%Y%m%d')}_results"

    def check_filepath(self) -> None:

        if not os.path.exists(self.path):
            print(f"Invalid path to store results in -> {self.path}")
            sys.exit(2)
        if os.path.exists(f"{self.filepath}.csv"):
            print(f"File {self.filepath}.csv already exists.\nWould you like to override it? [y/n]")
            override = input()
            if override == 'n':
                self.filepath = self.filepath + '_copy'
                self.check_filepath()

    def store_results(self, results: dict) -> None:
        # We export the data and either append it to existing file or create a new one
        # We create a pandas DataFrame from the dicitonary will all the information

        data_frame = pd.DataFrame.from_dict(results, orient="index", columns=self.headers)

        data_frame.to_csv(f"{self.filepath}.csv")
        #data_frame.to_excel(f"{self.filepath}.xlsx")

class Crawler:
    
    def __init__(self,
                 chromedriver_loc: str,
                 sources: list,
                 sources_out_of_order: list,
                 search_terms: list,
                 date_init: datetime,
                 date_end: datetime,
                 today: date,
                 now: datetime):

        self.chromedriver_loc = chromedriver_loc
        self.sources = sources
        self.sources_out_of_order = sources_out_of_order
        self.search_terms = search_terms
        self.date_init = date_init
        self.date_end = date_end
        self.TODAY = today
        self.NOW = now

        self.scraper = scraper.Scraper(self)

    def setup_driver(self) -> webdriver:
        # -- We set up the webdriver for the eventual use of selenium --
        # !!!!! -> webdriver needs to be downloaded
        # and its path stated in crawler/path_to_chromedriver.txt

        options = Options()
        options.add_argument('--headless')
        options.add_argument("enable-automation")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-extensions")
        options.add_argument("--dns-prefetch-disable")
        options.add_argument("--disable-gpu")

        s = Service(self.chromedriver_loc)
        driver = webdriver.Chrome(service=s, options=options)

        return driver
    
    def shutdown_driver(self) -> dict:
        self.driver.close()
        self.driver.quit()
    
    def crawl(self) -> dict:

        utils.prints('mode', date_init=self.date_init, date_end=self.date_end, search_terms=self.search_terms)

        self.driver = self.setup_driver()

        results = {}

        for journal in self.sources:
            utils.prints('searching', journal=journal)
            if journal in self.sources_out_of_order:
                utils.prints('out_of_order', journal=journal)
            else:
                # Use the methods in Scraper to search the for the articles!!!
                results.update(self.scraper.scrape(journal))

        self.shutdown_driver()

        return results

def main():

    today = date.today()
    now = datetime.now()

    input = Input(today, now)

    chromedriver_loc = input.get_chromedriver_loc()
    sources = input.get_sources()
    sources_out_of_order = input.get_sources_out_of_order()
    search_terms = input.get_search_terms()
    (date_init, date_end) = input.get_date_interval()

    output = Output()

    crawler = Crawler(chromedriver_loc, sources, sources_out_of_order, search_terms, date_init, date_end, today, now)
    results = crawler.crawl()

    if results:
        output.store_results(results)
    else:
        utils.prints('no_results')
    
if __name__ == "__main__":
    main()
