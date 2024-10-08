from datetime import date, datetime, timedelta, time
from dateutil.relativedelta import relativedelta

import streamlit as st
import io
import sys

STREAMLIT = False

def running_from_st():

    global STREAMLIT

    STREAMLIT = True


def setup_scraping_updates():

    global MESSAGE_STYLE
    global MESSAGE_BOX
    global MESSAGES

    MESSAGE_STYLE = """
    <style>
    .message-box {
        width: 100%;
        height: 500px;
        overflow-y: scroll;
        border: 1px solid #ccc;
        padding: 10px;
        font-family: monospace;
        font-size: 14px;
        background-color: #f9f9f9;
    }
    </style>
    """

    MESSAGE_BOX = st.empty()
    st.markdown(MESSAGE_STYLE, unsafe_allow_html=True)

    MESSAGES = []

def print_scraping_update(message):

    global MESSAGE_STYLE
    global MESSAGE_BOX
    global MESSAGES

    message_list = message.split('\n')

    for message in message_list:
        # Add a new message to the list
        MESSAGES.append(message)

        # Update the message box with the latest messages
        message_html = "<br>".join(MESSAGES)
        MESSAGE_BOX.markdown(f"<div class='message-box'>{message_html}</div>", unsafe_allow_html=True)


def prints(what: str,
           term: str=None,
           journal: str=None,
           len_comments: int=None,
           date_article: datetime=None,
           title: str=None,
           date_init: datetime=None,
           date_end: datetime=None,
           search_terms: list=None,
           url: str=None,
           current_page: int=None) -> None:
    
    '''
    Function to print status updates to the standard output.
    '''

    names = {'altaveu': "L'Altaveu",
            'periodic': "Periòdic d'Andorra",
            'ara': "Ara Andorra",
            'bondia': "Bondia.ad",
            'diari': "Diari d'Andorra",
            'forum': "fòrum.ad"}
    
    match what:
        case 'mode':
            message = "----------------------------------------------------------------------------------"
            message = message + f"\nSearching articles with the following search terms: {search_terms}"
            message = message + f"\nSearching articles between {date_init.strftime("%Y-%m-%d - %H:%M")} and {date_end.strftime("%Y-%m-%d - %H:%M")}"

        case 'searching':
            message = "----------------------------------------------------------------------------------"
            message = message + f"\nSearching at {names[journal]}"

        case 'term':
            message = f"--> SEARCHING TERM {term} ..."

        case 'comments':
            if len_comments == 1:
                message = f"       -{len_comments} comment"
            elif len_comments > 1:
                message = f"       -> {len_comments} comments"

        case 'article':
            message = f"    - {date_article} -> {title}"

        case 'out_of_order':
            message = f":( Under maintenance. {names[journal]} is currently out of order."
            message = message + f"\n--> Searching methods are currently being updated."

        case 'no_results':
            message = "----------------------------------------------------------------------------------"
            message = message + f"\nThe search yielded no results."

        case 'no_comments':
            message = "----------------------------------------------------------------------------------"
            message = message + f"\nThe articles had no comments."

        case 'url':
            message = f"URL: {url} ..."

        case 'current_page':
            message = f"CURRENT PAGE -> {current_page}"

        case 'loading_more_results':
            message = f"LOADING MORE RESULTS..."

    if STREAMLIT:

        # captured_output = buffer.getvalue()
        # print_scraping_update(captured_output)
        # sys.stdout = sys.__stdout__

        print_scraping_update(message)

    else:

        print(message)

def string_to_datetime(string: str, date_format: str, formatted: bool, multiple_formats: bool) -> datetime:
    # We convert the string that we obtained from the web into a datetime object.

    # If formatted == True, we can simply use strptime to go from string to datetime
    if formatted:
        # If there are multiple formats, we check each one until we get the correct one and can use strptime(..)
        if multiple_formats:
            for fmt in date_format:
                try:
                    return datetime.strptime(string, fmt)
                except ValueError:
                    pass
        else:
            return datetime.strptime(string, date_format)
        
def category_type(category: str) -> str:
        # We define 'type', to classify the different articles depending on their category.
        match category:
            case 'opinio':
                return "opinion"
            case 'reportatge':
                return "report"
            case 'vinyetes' | "portada a portada":
                return "image"
            case 'video' | 'editorial':
                return category
            case 'entrevista' | "la_contra" | "la_perla":
                return "interview"
            case _:
                return "article"

def numbered_page_url(journal: str, url: str, add_on: str, current_page: int) -> str:
    # In numbered pages, we return a string with the next url to look for (next numbered page)
    # Generally, this means a similar url with an added string at the end and the page's number.
    match journal:
        case 'altaveu' | 'bondia':
            return url + add_on + str(current_page)
        case 'forum':
            return url[:16] + add_on + str(current_page) + url[16:]
        case 'diari':
            return url[:35] + str(current_page) + url[35:]


