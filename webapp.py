import streamlit as st

import re
import os
import subprocess
import csv
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

import main_crawler
from crawler import utils

class Scrape:

    def __init__(self) -> None:
        pass

    def parse_inputs(self, search_terms_string: str) -> list:
        search_terms = re.split(r'[,\s]+', search_terms_string.strip())
        return [[term] for term in search_terms]
    
    def setup_search(self, search_terms: list, options: list, search_name: str, results_path: str) -> bool:
        
        try:

            # Writing to search_terms.csv
            search_terms_filepath = f"{results_path}/search_terms.csv"
            with open(search_terms_filepath, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)

                writer.writerows([[search_name]] + search_terms)

            # Writing to search_terms.csv
            sources_filepath = f"{results_path}/sources.csv"
            with open(sources_filepath, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerows(options)

            return True
        
        except:

            return False

    def main_scraper(self, date_init: datetime, date_end: datetime, results_path: str):
            
            today = date.today()
            now = datetime.now()

            input = main_crawler.Input(today, now, results_path)

            chromedriver_loc = input.get_chromedriver_loc()
            sources = input.get_sources()
            sources_out_of_order = input.get_sources_out_of_order()
            sources_elements = input.get_sources_elements()
            search_name, search_terms = input.get_search_terms()

            output = main_crawler.Output(search_name, input.path_to_input)

            crawler = main_crawler.Crawler(chromedriver_loc,
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


def main():

    # subprocess.run(["python", "script.py"])

    st.title("Andorra Sentiment Analyst")

    scrape = Scrape()

    # Button to trigger scraping

    # Search_terms
    st.write("Enter a keyword to scrape relevant information from the Andorran journals.")
    search_terms_string = st.text_area("Enter a list of keywords (separated by commas or new lines):", height=150)
    search_terms = scrape.parse_inputs(search_terms_string)

    if not search_terms:
        st.warning("Please enter at least one keyword.")

    # Date interval
    # Define default dates (e.g., last 7 days)
    default_start = datetime.today() - relativedelta(days=7)
    default_end = datetime.today()

    # User selects a date interval
    date_interval = st.date_input(
        "Select a date range:",
        value=(default_start, default_end),
        min_value=datetime(2000, 1, 1),
        max_value=datetime.today()
    )

    # Validate the date interval
    if isinstance(date_interval, tuple) and len(date_interval) == 2:
        start_date, end_date = date_interval
        if start_date > end_date:
            st.error("Error: Start date must be before end date.")
    else:
        st.warning("Please select a valid date range.")

    st.header("Additional Options")

    # Journals to scrape
    altaveu = st.checkbox("Altaveu.com")
    bondia = st.checkbox("Bondia.ad")
    diari = st.checkbox("Diari d'Andorra")

    # Collect the options into a dictionary for easy handling
    options = [
        ["altaveu", altaveu],
        ["bondia", bondia],
        ["diari", diari]
    ]

    if st.button("Cerca"):

        search_name = "TRY"
        results_path = f"data/scrapes/{search_name}/"

        if not os.path.exists(results_path):
            os.makedirs(results_path, exist_ok=True)

        success = scrape.setup_search(search_terms, options, search_name, results_path)

        if success:
            scrape.main_scraper(start_date, end_date, results_path)
        else:
            st.warning("Please enter a keyword to proceed.")

if __name__ == "__main__":
    main()