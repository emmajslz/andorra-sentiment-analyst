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

    # Create three columns
    col1, col2, col3 = st.columns(3)

    # Add content to each column
    with col1:
        st.header("L'altaveu")
        st.components.v1.iframe("https://www.altaveu.com", height=600)

    with col2:
        st.header("Bondia.ad")
        st.components.v1.iframe("https://www.bondia.ad", height=600)

    with col3:
        st.header("El Diari d'Andorra")
        st.components.v1.iframe("https://www.diariandorra.ad",  height=600)

if __name__ == "__main__":
    main()