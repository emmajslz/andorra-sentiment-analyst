import argparse
import sys
import os
import time as tme

import pandas as pd
import numpy as np

import csv

from datetime import datetime, date, time
from dateutil.relativedelta import relativedelta

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from crawler import utils, scraper

class Input:
    
    def __init__(self, today: date, now: datetime, path: str = None, date_init: datetime = None, date_end: datetime = None):

        self.NOW = now
        self.TODAY = today
    
        if path:
            self.path_to_input = path
            self.date_init = date_init
            self.date_end = date_end

        else:
            self.path_to_input, self.date_init, self.date_end = self.get_args()

        self.check_args(self.path_to_input, self.date_init, self.date_end)
            
        self.path_to_sources = f"{self.path_to_input}sources.csv"
        self.path_to_search_terms = f"{self.path_to_input}search_terms.csv"
        
        self.path_to_chromedriver_loc = 'crawler/path_to_chromedriver.txt'
        self.path_to_sources_out_of_order = 'crawler/sources_out_of_order.txt'
        self.path_to_sources_elements= 'crawler/sources_elements.csv'

    def get_args(self):

        # Default is 1 month back from today's date.
        date_end = self.NOW
        date_init = date_end - relativedelta(months=1)

        # Script arguments
        parser = argparse.ArgumentParser()

        parser.add_argument("path", type=str, help="Path to the desired directory or file")
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

        path = args.path
        if path[-1] != '/':
            path = path + '/'

        return path, date_init, date_end
    
    def check_args(self, path, date_init, date_end):

        if date_init > self.NOW or date_end > self.NOW:
            print(f"Dates cannot be in the future.")
            sys.exit(2)
        if date_init > date_end:
            print(f"Start date cannot be after end date.")
            sys.exit(2)

        if not os.path.exists(path):
            print(f"Invalid path to get inputs -> {path}")
            sys.exit(2)
        else:
            print(f"Getting input files from {path}")

    def get_chromedriver_loc(self) -> str:
        return open(self.path_to_chromedriver_loc, 'r').readline().strip()

    def get_sources(self) -> list:
                
        lines = open(self.path_to_sources, 'r').readlines()
        sources = [line.split(',')[0].strip() for line in lines if line.split(',')[1]]
            
        return sources
    
    def get_sources_out_of_order(self) -> list:
        
        lines = open(self.path_to_sources_out_of_order, 'r').readlines()
        sources_out_of_order = [line.strip() for line in lines]
            
        return sources_out_of_order

    def get_sources_elements(self) -> pd.DataFrame:
        return pd.read_csv(self.path_to_sources_elements, delimiter=';').set_index('source')
    
    def get_search_terms(self):

        lines = open(self.path_to_search_terms, 'r').readlines()
        search_name = lines[0].strip()
        search_terms = [line.strip() for line in lines[1:]]

        return search_name, search_terms


class Output:

    def __init__(self, search_name, output_path, articles_path = False, comments_path = False):

        self.path = output_path
        self.search_name = search_name

        self.articles_path = self.define_articles_path()

        if articles_path:
            self.filepath = f"{self.path}articles"
        else:
            self.filepath = f"{self.path}{self.define_filename()}"
        self.headers = [
            "datetime_added",
            "journal",
            "search_term",
            "datetime_article",
            "category",
            "type",
            "title",
            "link",
            "nb_of_comments"
        ]

        if comments_path:
            self.comments_filepath = f"{self.path}comments"
        else:
            self.comments_filepath = f"{self.path}{self.define_comments_filename()}"
        self.comments_headers = [
            "article_id",
            "comment_author",
            "comment_datetime_displayed",
            "comment_datetime",
            "comment_content",
            "comment_in_answer_to",
            "comment_likes",
            "comment_dislikes"
        ]

        self.check_filepath()

    def define_filename(self) -> str:
        return f"{datetime.now().strftime('%Y%m%d')}_{self.search_name}_articles"
    
    def define_comments_filename(self) -> str:
        return f"{datetime.now().strftime('%Y%m%d')}_{self.search_name}_comments"

    def define_articles_path(self) -> str:

        articles_path = f"{self.path}articles/"

        if not os.path.exists(articles_path):
            os.makedirs(articles_path, exist_ok=True)

        return articles_path

    def check_filepath(self) -> None:

        if not os.path.exists(self.path):
            print(f"Invalid path to store results in -> {self.path}")
            sys.exit(2)
        else:
            print(f"Storing results as -> {self.filepath}.csv")

        if not os.path.exists(self.articles_path):
            print(f"Invalid path to store articles in -> {self.articles_path}")
            sys.exit(2)
        else:
            print(f"Storing articles in -> {self.articles_path}")

        if os.path.exists(f"{self.filepath}.csv"):
            print(f"File {self.filepath}.csv already exists.\nWould you like to override it? [y/n]")
            override = input()
            if override == 'n':
                self.filepath = self.filepath + '_copy'
                self.check_filepath()
      
        if os.path.exists(f"{self.comments_filepath}.csv"):
            print(f"File {self.comments_filepath}.csv already exists.\nWould you like to override it? [y/n]")
            override = input()
            if override == 'n':
                self.comments_filepath = self.comments_filepath + '_copy'
                self.check_filepath()
        
    def store_results(self, results: dict) -> None:
        # We export the data and either append it to existing file or create a new one
        # We create a pandas DataFrame from the dicitonary will all the information

        data_frame = pd.DataFrame.from_dict(results, orient="index", columns=self.headers)

        data_frame.to_csv(f"{self.filepath}.csv", index_label="id", sep=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        print(f"Resulting dataset stored as -> {self.filepath}.csv")
        # data_frame.to_excel(f"{self.filepath}.xlsx", index_label="id")

    def store_comments(self, comments: dict) -> None:
        
        comments_data_frame = pd.DataFrame.from_dict(comments, orient="index", columns=self.comments_headers)

        comments_data_frame.to_csv(f"{self.comments_filepath}.csv", index_label="comment_id", sep=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        print(f"Resulting comments dataset stored as -> {self.comments_filepath}.csv")
        # comments_data_frame.to_excel(f"{self.comments_filepath}.xlsx", index_label="comment_id")

    def store_article(self, id: str, title: str, subtitle: str, content: str) -> None:

        filepath = f"{self.articles_path}{id}.txt"

        with open(filepath, 'w') as file:
            file.write(title + "\n\n")
            file.write(subtitle + "\n\n")
            file.write(content)


class Crawler:
    
    def __init__(self,
                 chromedriver_loc: str,
                 sources: list,
                 sources_out_of_order: list,
                 sources_elements: pd.DataFrame,
                 search_terms: list,
                 date_init: datetime,
                 date_end: datetime,
                 today: date,
                 now: datetime,
                 output_instance: Output,
                 headless: bool = True):

        self.chromedriver_loc = chromedriver_loc
        self.sources = sources
        self.sources_out_of_order = sources_out_of_order
        self.sources_elements = sources_elements
        self.search_terms = search_terms
        self.date_init = date_init
        self.date_end = date_end
        self.TODAY = today
        self.NOW = now
        self.output = output_instance
        self.headless = headless
        
        self.saved_articles = set()
        self.saved_comments = set()

        self.scraper = scraper.Scraper(self)

    def setup_driver(self) -> webdriver:
        # -- We set up the webdriver for the eventual use of selenium --
        # !!!!! -> webdriver needs to be downloaded
        # and its path stated in crawler/path_to_chromedriver.txt

        options = Options()
        if self.headless:
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

        result_articles = {}
        result_comments = {}

        for journal in self.sources:
            utils.prints('searching', journal=journal)
            if journal in self.sources_out_of_order:
                utils.prints('out_of_order', journal=journal)
            else:
                # Use the methods in Scraper to search the for the articles!!!
                articles, comments = self.scraper.scrape(journal)
                result_articles.update(articles)
                result_comments.update(comments)

        self.shutdown_driver()

        return result_articles, result_comments 

def main():

    start_time = tme.time()

    today = date.today()
    now = datetime.now()

    input = Input(today, now)

    chromedriver_loc = input.get_chromedriver_loc()
    sources = input.get_sources()
    sources_out_of_order = input.get_sources_out_of_order()
    sources_elements = input.get_sources_elements()
    search_name, search_terms = input.get_search_terms()
    path_to_input = input.path_to_input
    (date_init, date_end) = (input.date_init, input.date_end)

    output = Output(search_name, path_to_input)

    crawler = Crawler(chromedriver_loc,
                      sources,
                      sources_out_of_order,
                      sources_elements,
                      search_terms,
                      date_init,
                      date_end,
                      today,
                      now,
                      output,
                      headless=True)
    
    articles, comments = crawler.crawl()

    if articles:
        output.store_results(articles)
    else:
        utils.prints('no_results')

    if comments:
        output.store_comments(comments)
    else:
        utils.prints('no_comments')

    print(f"\nTotal execution time: {tme.time() - start_time:.3f}({(tme.time() - start_time)/60:.3f} minutes)")
    
if __name__ == "__main__":
    main()
