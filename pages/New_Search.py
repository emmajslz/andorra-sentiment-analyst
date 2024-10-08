import streamlit as st

import re
import os
import csv
from datetime import date, datetime, time
from dateutil.relativedelta import relativedelta

import main_crawler
import analyze
from crawler import utils

class Scrape:

    def __init__(self) -> None:
        utils.running_from_st()
    
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

        input = main_crawler.Input(today, now, results_path, date_init, date_end)

        chromedriver_loc = input.get_chromedriver_loc()
        sources = input.get_sources()
        sources_out_of_order = input.get_sources_out_of_order()
        sources_elements = input.get_sources_elements()
        search_name, search_terms = input.get_search_terms()
        path_to_input = input.path_to_input
        (date_init, date_end) = (input.date_init, input.date_end)

        output = main_crawler.Output(search_name, path_to_input, articles_path=True, comments_path=True)

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
            if comments:
                output.store_comments(comments)
            else:
                utils.prints('no_comments')
                return True, False
        else:
            utils.prints('no_results')
            return False, False


class Search:

    def __init__(self) -> None:
        pass

    def parse_inputs(self, search_terms_string: str) -> list:
        search_terms = re.split(r'[,\n]+', search_terms_string.strip())
        return [[term] for term in search_terms]

    def get_search_terms(self):

        # Search_terms
        st.markdown("### Enter a list of search terms")
        search_terms_string = st.text_area("Enter the list separated by commas or new lines:", height=150)
        search_terms = self.parse_inputs(search_terms_string)

        return search_terms
    
    def get_date_interval(self):

        # Date interval
        # Define default dates (e.g., last 7 days)
        default_start = datetime.now() - relativedelta(days=7)
        default_end = datetime.now()

        # User selects a date interval
        st.markdown("### Enter a date interval")
        date_interval = st.date_input(
            "Select a start and end date:",
            value=(default_start, default_end),
            min_value=datetime(2000, 1, 1),
            max_value=datetime.now()
        )

        # Validate the date interval
        if isinstance(date_interval, tuple) and len(date_interval) == 2:
            date_init, date_end = date_interval
            if date_init > date_end:
                st.error("Error: Start date must be before end date.")
        else:
            st.warning("Please select a valid date range.")     

        if isinstance(date_init, date):
            date_init = datetime.combine(date_init, time(0, 0, 0))
        if isinstance(date_end, date):
            if date_end == date.today():
                date_end = datetime.combine(date_end, datetime.now().time())
            else:
                date_end = datetime.combine(date_end, time(23, 59, 59))

        return date_init, date_end

    def select_journals(self):

        st.markdown("### Select the journals to look in")
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

        return options

def main():

    st.set_page_config(
        page_title='New article search',
        page_icon="🌐",
        layout='wide',
        initial_sidebar_state='auto' # hides the sidebar on small devices and shows it otherwise
    )

    st.markdown("# New article search")

    # ------------------------------------------------------------------------------------------------------
    # Define Search and get Scraping parameters
    # ------------------------------------------------------------------------------------------------------

    search = Search()
    # Search_terms
    search_terms = search.get_search_terms()

    # Date interval
    date_init, date_end = search.get_date_interval()

    # Journal options
    options = search.select_journals()

    # ------------------------------------------------------------------------------------------------------

    if st.button("Search"):

        # Create a placeholder for the warning
        search_status_placeholder = st.empty()
        results_message_placeholder = st.empty()

        # Display a warning message before the process starts
        with search_status_placeholder:
            st.warning("DO NOT QUIT OR REFRESH THIS PAGE WHILE THE SEARCH IS IN PROGRESS!")

        with st.spinner("Performing search"):

            search_name = f"SEARCH-{datetime.now().strftime("%Y%m%d%H%M%S")}"
            results_path = f"data/scrapes/{search_name}/"

            if not os.path.exists(results_path):
                os.makedirs(results_path, exist_ok=True)

            scrape = Scrape()
            success = scrape.setup_search(search_terms, options, search_name, results_path)

            if success:

                utils.setup_scraping_updates()
                articles, comments = scrape.main_scraper(date_init, date_end, results_path)

            else:
                st.warning("Please enter the correct parameters to proceed.")
        
        # Display a warning message before the process starts
        with search_status_placeholder:
            st.success(f"Search completed!")
        with results_message_placeholder:
            if articles and not comments:
                st.warning(f"The articles had no comments. Articles dataset stored in directory {search_name}")
            elif not articles and not comments:
                st.error(f"The search yielded no results.")
            else:
                 st.success(f"Results were stored in directory {search_name}")


if __name__ == "__main__":
    main()