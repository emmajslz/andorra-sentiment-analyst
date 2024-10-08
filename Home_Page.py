import streamlit as st

import re
import os
import csv
from datetime import date, datetime, time
from dateutil.relativedelta import relativedelta

import main_crawler
from crawler import utils
  
def main():

    st.set_page_config(
        page_title='Andorra Sentiment Analyzer',
        page_icon="🌐",
        layout='wide',
        initial_sidebar_state='auto' # hides the sidebar on small devices and shows it otherwise
    )

    st.title("🌐 Andorra Sentiment Analyzer")
    st.write("""
    
    - **New search**: Perform a new search on the Andorran press, based on different search terms.
    - **Sentiment Analyzer**: Perform Sentiment Analysis on obtained datasets.
    
    Use the sidebar to navigate between pages.
    """)

if __name__ == "__main__":
    main()