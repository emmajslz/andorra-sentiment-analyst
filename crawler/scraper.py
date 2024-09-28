import re
import time as tme
import traceback
import sys

import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait

from datetime import datetime

from crawler import utils
from crawler import parser

class AddArticle:

    def __init__(self, crawler_instance, parser_instance, dynamic_methods_instance=None):
        self.crawler = crawler_instance
        self.parser = parser_instance

        if dynamic_methods_instance:
            self.dynamic_methods = dynamic_methods_instance
        else:
            self.dynamic_methods = DynamicMethods(self.crawler)

        self.comments = Comments(self.crawler, self.parser, self.dynamic_methods)
    
    def define_article_id(self, journal: str, date_article: datetime):
        return f"{journal[:2].upper()}{date_article.strftime("%Y%m%d%H%M%S")}"
    
    def add_article_to_dict(self,
                            journal: str,
                            article,
                            article_id: str,
                            date_article: datetime,
                            link: str,
                            soup: BeautifulSoup,
                            term: str,
                            dict_articles: dict,
                            dict_comments: dict):
        # For each article, we use this function to determine wether or not it should be added to the dictionary,
        # get all the attributes we want, all the comments in the article (if there are any) and append all of
        # the information to the dictionary.

        if soup:

            # We get all the attributes we don't already have
            title = self.parser.get_title(journal, article)
            category = self.parser.get_category(journal, article, soup)
            type_article = utils.category_type(category)

            utils.prints('article', date_article=date_article, title=title)

            # We get the content in the article
            content = self.parser.get_content(journal, soup)
            subtitle = self.parser.get_subtitle(journal, soup)
            self.crawler.output.store_article(article_id, title, subtitle, content)

            # We get all the comments in the article with the get_comments(...) function. If there are none,
            # get_comments(...) will return an empty list.
            comments = self.comments.get_comments(journal, link, soup)
            len_comments = len(comments)
            utils.prints('comments', len_comments=len_comments, date_article=date_article)

            # We add a line with all the comment information blank. If there are no comments, the article will only
            # have this line, and if there are comments, we'll have a line that only defines the article.
            dict_articles[article_id] = [self.crawler.NOW,
                                        journal,
                                        term,
                                        date_article,
                                        category,
                                        type_article,
                                        title,
                                        link,
                                        len_comments]
            
            self.crawler.saved_articles.add(article_id)

            # We loop through the list (if it's not empty) and add a new element to the article for each comment,
            # with the comment information at the end.
            for comment in comments:
                comment_id = f"{article_id}-{str(comment[0])}"
                if not comment_id in self.crawler.saved_comments:
                    dict_comments[comment_id] = [article_id,
                                                comment[1],
                                                comment[2],
                                                comment[3],
                                                comment[4],
                                                comment[5],
                                                comment[6],
                                                comment[7]]
                    self.crawler.saved_comments.add(comment_id)

        return dict_articles, dict_comments

class Comments:

    def __init__(self, crawler_instance, parser_instance, dynamic_methods_instance):
        self.crawler = crawler_instance
        self.parser = parser_instance
        self.dynamic_methods = dynamic_methods_instance

    def load_all_comments(self, journal):
        # In the event the comment list has a "Show more" button, we need to load all comment before accessing them

        # We define the location of the "Show more" button
        load_more_loc = {'altaveu': '//div[@class="c-paginator"]/a',
                        'diari': '//a[@class="next_com"]'}

        more_comments = True

        # We only start the loop in case there is a "Show more" button
        # We use a find_elements method that will return an empty list in case there is no button,
        # which will render the condition False
        while more_comments and self.crawler.driver.find_elements(By.XPATH, load_more_loc[journal]):
            try:
                button = WebDriverWait(self.crawler.driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, load_more_loc[journal])))
            except TimeoutException:
                # If the button isn't there, WebDriverWait will raise a TimeoutExeption
                # This means there are no more comments to load
                more_comments = False
            if more_comments:
                # If we were able to find the button, we click it
                self.crawler.driver.execute_script("arguments[0].click();", button)
                # Even though it's better to avoid .sleep(), in this case it's necessary because if we don't wait
                # When we go through the loop again, the load_more_button is going to be found even if it's not there
                # anymore. We can't handle this with normal waits, as we're not waiting for an element to be available,
                # we're waiting for an element to stop being available
                tme.sleep(2)

    def get_comments(self, journal, url, soup):
        # Depending on the journal, we use a method or another to get the comment_list

        match journal:
            case 'altaveu':
                # Comments are loaded dynamically, so we get them with Selenium
                self.dynamic_methods.open_url(journal, url)
                tme.sleep(1)
                # We load all comments
                self.load_all_comments(journal)
                # We create a BeautifulSoup object with the current page_source
                soup = BeautifulSoup(self.crawler.driver.page_source, 'html.parser')
                return self.get_comments_soup(journal, soup)

            case 'diari':
                try:
                    self.dynamic_methods.open_url(journal, url)
                    tme.sleep(1)
                    shadow_host = self.crawler.driver.find_element(By.CSS_SELECTOR, "hyvor-talk-comments")
                    # Use JavaScript to extract the shadow root's inner HTML
                    shadow_dom_html = self.crawler.driver.execute_script("""
                        // Access the shadow root and return its inner HTML
                        return arguments[0].shadowRoot.innerHTML;
                    """, shadow_host)

                    # Create a BeautifulSoup object with the extracted shadow DOM HTML
                    soup = BeautifulSoup(shadow_dom_html, "html.parser")
                    return self.get_comments_soup(journal, soup)
                except:
                    return []

            case 'bondia':
                return self.get_comments_soup(journal, soup)

            case _:
                # If we are not in a journal that has comments, we return an empty list
                return []
        
    def get_comments_soup(self, journal, soup, second_window=False):
        # Once we have the soup, we can create a list of lists with all the comment attributes
        # Each element in comment_list is a comment: a list of attributes

        comment_list = []

        # We get the list of all the comments
        match journal:
            case 'altaveu':
                comments = soup.find_all('div', attrs={"data-type": "comment"})

            case 'diari':
                comments = soup.find_all('div', class_="comment")

            case 'bondia':
                comments_col = soup.find('div', class_="col-span-4 pt-2")
                comments = comments_col.find_all('div', class_="flex flex-col gap-2 bg-primary-200 py-4 px-10")

        if not comments:
            comments = []
        len_comments = len(comments)

        # We loop through the list
        # We use get_comment_attributes(...) to get each comment's info. It returns a list of attributes
        # We append each list of attributes to comment_list, creating a list of lists with all the comments.
        for i in range(0, len_comments):
            comment = comments[i]
            attributes = self.parser.get_comment_attributes(journal, comment, i)
            comment_list.append(attributes)

        # If we have used a second window to look at the comments, we close it
        if second_window:
            self.dynamic_methods.url_in_second_window("close")

        return comment_list

class DynamicMethods:

    def __init__(self, crawler_instance):

        # The crawler_instance has attribute driver, which we'll use to navigate through pages
        self.crawler = crawler_instance

        self.parser = parser.Parser()
        self.add_article = AddArticle(self.crawler, self.parser, self)

    def buttons(self, journal: str) -> None:
        # We click the cookies and notifications buttons in the event we just opened the webpage and there are cookies and
        # notifications pop ups that would not allow us to see the information on the page
        cookies_loc = self.crawler.sources_elements.loc[journal, 'cookies']
        notifs_loc = self.crawler.sources_elements.loc[journal, 'notifs']
        # If the button hasn't been already pressed, journal is in cookies (meaning there is a button to press)
        # and the button is there:
        if not self.crawler.cookies_clicked and cookies_loc != '-' and self.crawler.driver.find_elements(By.XPATH, cookies_loc):
            cookies_accept = self.crawler.driver.find_element(By.XPATH, cookies_loc)
            self.crawler.driver.execute_script("arguments[0].click();", cookies_accept)
            self.crawler.cookies_clicked = True

        if not self.crawler.notifs_clicked and notifs_loc != '-' and self.crawler.driver.find_elements(By.XPATH, notifs_loc):
            notifications = self.crawler.driver.find_element(By.XPATH, notifs_loc)
            self.crawler.driver.execute_script("arguments[0].click();", notifications)
            self.crawler.notifs_clicked = True

    def opening_url_actions(self, journal: str) -> None:  # journal specific !!
        # Each journal has some actions we need to do after opening the url with the driver (sortin, adverts, etc.)

        match journal:
            case 'periodic':
                # If there is an advertisement pop_up that stops us from accessing the journal, we click the "Access journal"
                # button to access the journal
                access = True
                try:
                    access_journal = WebDriverWait(self.crawler.driver, 15).until(EC.presence_of_element_located((
                        By.XPATH, '//div[@class="interstitial__link"]/a')))
                except TimeoutException:
                    access = False

                if access:
                    self.crawler.driver.execute_script("arguments[0].click();", access_journal)
                    self.crawler.driver.implicitly_wait(15)

                self.buttons(journal)

    def open_url(self, journal: str, url: str) -> None:
        
        try:
            self.crawler.driver.get(url)
        except:
            print(f"Cannot access {url} right now. Please try again later.")
            return False
        self.buttons(journal)
        self.opening_url_actions(journal)
        return True

    def get_soup(self, journal: str, url: str = None) -> BeautifulSoup:

        if url:
            success = self.open_url(journal, url)
            if not success:
                return None
        
        soup = BeautifulSoup(self.crawler.driver.page_source, 'html.parser')
        return soup
    
    def url_in_second_window(self, mode: str, url=None) -> None:
        # If we need to, we open a second window on the WebDriver (to be able to keep the information on the current window)

        if mode == "open":
            global window_before
            window_before = self.crawler.driver.window_handles[0]
            self.crawler.driver.execute_script("window.open()")
            second_window = self.crawler.driver.window_handles[1]
            self.crawler.driver.switch_to.window(second_window)
            self.crawler.driver.get(url)

        else:

            self.crawler.driver.close()
            self.crawler.driver.switch_to.window(window_before)    

    def all_articles_selenium(self, journal: str, next_page=None):
        # We look for all the articles on the current page
        # For dynamic webpages -> Selenium
        all_articles_locs = self.crawler.sources_elements.loc[journal, 'all_articles']
        # We wait until we can find the elements to begin
        WebDriverWait(self.crawler.driver, 15).until(EC.presence_of_element_located((By.XPATH, all_articles_locs)))

        # If we are looking for articles after clicking on the "Show more" button, we can't search the whole page
        # but only the articles that are new
        if next_page is None:
            return self.crawler.driver.find_elements(By.XPATH, all_articles_locs)
        else:
            return next_page.find_elements(By.XPATH, '.' + all_articles_locs)
    
class StaticMethods:

    def __init__(self, crawler_instance):

        self.crawler = crawler_instance

        self.parser = parser.Parser()
        self.add_article = AddArticle(self.crawler, self.parser)

    def get_soup(self, url: str) -> BeautifulSoup:

        try:
            response = requests.get(url)
        except:
            print(f"Cannot access {url} right now. Please try again later.")
            return False

        soup = BeautifulSoup(response.text, 'html.parser')
        return soup

""" -- THE DIFFERENT SCRAPERS -> Depending on source --"""
class Altaveu:

    def __init__(self, crawler_instance):

        # We define our crawler (argument) and parser (new object) instances
        self.crawler = crawler_instance
        self.parser = parser.Parser()

        # We get an instance of the different classes to obtain the methods we need
        self.static_methods = StaticMethods(self.crawler)
        self.dynamic_methods = DynamicMethods(self.crawler)
        self.add_article = AddArticle(self.crawler, self.parser, self.dynamic_methods)

        # We define all the variables to store locations or paths that we'll need
        self.next_page = self.crawler.sources_elements.loc['altaveu', 'next_page']

    def numbered_pages(self,
                        journal: str,
                        url: str,
                        date_init: datetime,
                        date_end: datetime,
                        term: str) -> dict:
        # Structure to crawl: Numbered pages
        # Type of webpage: Static (We use beautifulsoup)
        # The page is divided in numbered pages (page 1, page 2, etc.)
        # We loop through the different numbered pages, to get all the articles in each
        # We add every article (list of attributes) that is inside the desired interval to the dictionary

        dict_articles = {}
        dict_comments = {}

        try:
            current_page = 1
            utils.prints('current_page', current_page=current_page)

            # We use the function crawl_current_page to obtain the articles from the First page
            (articles_current_page, comments_current_page, date_in_interval, successful_access) = self.numbered_pages_current_page(journal,
                                                                                                                url,
                                                                                                                date_init,
                                                                                                                date_end,
                                                                                                                term)
            dict_articles.update(articles_current_page)
            dict_comments.update(comments_current_page)

            # We loop through the different numbered pages, until the articles are outside the date interval
            while date_in_interval and successful_access:
                current_page += 1
                utils.prints('current_page', current_page=current_page)
                # We define the next url (next numbered page) thanks to the function numbered_page_url
                next_url = utils.numbered_page_url(journal, url, self.next_page, current_page)
                # We get all the new articles from the new numbered page.
                (articles_current_page, comments_current_page, date_in_interval, successful_access) = self.numbered_pages_current_page(journal,
                                                                                                                next_url,
                                                                                                                date_init,
                                                                                                                date_end,
                                                                                                                term)
                dict_articles.update(articles_current_page)
                dict_comments.update(comments_current_page)
        
        except Exception as e:
            print(f"\n--> There was an error crawling in journal {journal}")
            print(f"ERROR MESSAGE:\n{e}")
            traceback.print_exc()
            print("\n")
        
        return dict_articles, dict_comments
    
    def numbered_pages_current_page(self,
                                    journal: str,
                                    url: str,
                                    date_init: datetime,
                                    date_end: datetime,
                                    term: str):
        
        utils.prints('url', url=url)

        dict_articles = {}
        dict_comments = {}
        date_in_interval = True
        successful_access = True

        soup = self.static_methods.get_soup(url)
        
        if soup:
            try:

                articles = self.parser.all_articles(journal, soup)
                len_articles = len(articles)

                if len_articles == 0:
                    return {}, {}, False, successful_access

                date_article = self.crawler.NOW

                i = 0
                # Same method as scrape_single_page, except in the event we exit the date interval, we'll return a variable
                # date_in_interval = False so the loop in scrape_numbered_pages can stop.
                while date_init <= date_article and i < len_articles and date_in_interval:
                    article = articles[i]
                    link = self.parser.get_link(journal, article)
                    soup = self.static_methods.get_soup(link)
                    date_article = self.parser.get_datetime(journal, article, soup)

                    article_id = self.add_article.define_article_id(journal, date_article)

                    if not article_id in self.crawler.saved_articles:
                        if date_article <= date_end:
                            if date_init <= date_article:
                                dict_articles, dict_comments = self.add_article.add_article_to_dict(journal,
                                                                                                    article,
                                                                                                    article_id,
                                                                                                    date_article,
                                                                                                    link,
                                                                                                    soup,
                                                                                                    term,
                                                                                                    dict_articles,
                                                                                                    dict_comments)
                            else:
                                date_in_interval = False
                    i += 1
                
            except Exception as e:
                print(f"\n--> There was an error crawling in journal {journal}")
                print(f"ERROR MESSAGE:\n{e}")
                traceback.print_exc()
                print("\n")
                date_in_interval = False
        else:
            successful_access = False

        return (dict_articles, dict_comments, date_in_interval, successful_access)

class Forum:

    def __init__(self, crawler_instance):

        # We define our crawler (argument) and parser (new object) instances
        self.crawler = crawler_instance
        self.parser = parser.Parser()

        # We get an instance of the different classes to obtain the methods we need
        self.static_methods = StaticMethods(self.crawler)
        self.dynamic_methods = DynamicMethods(self.crawler)
        self.add_article = AddArticle(self.crawler, self.parser, self.dynamic_methods)

        # We define all the variables to store locations or paths that we'll need
        self.next_page = self.crawler.sources_elements.loc['forum', 'next_page']

    def numbered_pages(self,
                        journal: str,
                        url: str,
                        date_init: datetime,
                        date_end: datetime,
                        term: str) -> dict:
        # Structure to crawl: Numbered pages
        # Type of webpage: Static (We use beautifulsoup)
        # The page is divided in numbered pages (page 1, page 2, etc.)
        # We loop through the different numbered pages, to get all the articles in each
        # We add every article (list of attributes) that is inside the desired interval to the dictionary

        dict_articles = {}
        dict_comments = {}

        try:
            current_page = 1
            utils.prints('current_page', current_page=current_page)

            # We use the function crawl_current_page to obtain the articles from the First page
            (articles_current_page, comments_current_page, date_in_interval, successful_access) = self.numbered_pages_current_page(journal,
                                                                                                                                url,
                                                                                                                                date_init,
                                                                                                                                date_end,
                                                                                                                                term)
            dict_articles.update(articles_current_page)
            dict_comments.update(comments_current_page)

            # We loop through the different numbered pages, until the articles are outside the date interval
            while date_in_interval and successful_access:
                current_page += 1
                utils.prints('current_page', current_page=current_page)
                # We define the next url (next numbered page) thanks to the function numbered_page_url
                next_url = utils.numbered_page_url(journal, url, self.next_page, current_page)
                # We get all the new articles from the new numbered page.
                (articles_current_page, comments_current_page, date_in_interval, successful_access) = self.numbered_pages_current_page(journal,
                                                                                                                next_url,
                                                                                                                date_init,
                                                                                                                date_end,
                                                                                                                term)
                dict_articles.update(articles_current_page)
                dict_comments.update(comments_current_page)
        
        except Exception as e:
            print(f"\n--> There was an error crawling in journal {journal}")
            print(f"ERROR MESSAGE:\n{e}")
            traceback.print_exc()
            print("\n")
        
        return dict_articles, dict_comments
    
    def numbered_pages_current_page(self,
                                    journal: str,
                                    url: str,
                                    date_init: datetime,
                                    date_end: datetime,
                                    term: str):
        # Function used inside scrape_numbered_pages(...)
        # For each numbered page, we'll return a dictionary with all the articles inside the interval
        # We return the variable date_in_interval. If it's False, the loop in scrape_numbered_pages(...) will stop.
        utils.prints('url', url=url)
        dict_articles = {}
        dict_comments = {}
        date_in_interval = True
        successful_access = True

        soup = self.static_methods.get_soup(url)
        
        if soup:
            try:

                articles = self.parser.all_articles(journal, soup)
                len_articles = len(articles)

                if len_articles == 0:
                    return {}, {}, False, successful_access

                date_article = self.crawler.NOW

                i = 0
                # Same method as scrape_single_page, except in the event we exit the date interval, we'll return a variable
                # date_in_interval = False so the loop in scrape_numbered_pages can stop.
                while date_init <= date_article and i < len_articles and date_in_interval:
                    article = articles[i]
                    date_article = self.parser.get_datetime(journal, article)
                    if date_article <= date_end:
                        link = self.parser.get_link(journal, article)
                        soup = self.static_methods.get_soup(link)

                        article_id = self.add_article.define_article_id(journal, date_article)

                        if not article_id in self.crawler.saved_articles:
                            if date_init <= date_article:
                                dict_articles, dict_comments = self.add_article.add_article_to_dict(journal,
                                                                                    article,
                                                                                    article_id,
                                                                                    date_article,
                                                                                    link,
                                                                                    soup,
                                                                                    term,
                                                                                    dict_articles,
                                                                                    dict_comments)
                            else:
                                date_in_interval = False
                    i += 1
                
            except Exception as e:
                print(f"\n--> There was an error crawling in journal {journal}")
                print(f"ERROR MESSAGE:\n{e}")
                traceback.print_exc()
                print("\n")
                date_in_interval = False
        else:
            successful_access = False
        
        return (dict_articles, dict_comments, date_in_interval, successful_access)

class Bondia:

    def __init__(self, crawler_instance):

        # We define our crawler (argument) and parser (new object) instances
        self.crawler = crawler_instance
        self.parser = parser.Parser()

        # We get an instance of the different classes to obtain the methods we need
        self.static_methods = StaticMethods(self.crawler)
        self.dynamic_methods = DynamicMethods(self.crawler)
        self.add_article = AddArticle(self.crawler, self.parser, self.dynamic_methods)

        # We define all the variables to store locations or paths that we'll need
        self.load_next_page = self.crawler.sources_elements.loc['bondia', 'load_next_page']

    def define_next_page_button(self, current_page: int) -> str:
        return f'button[wire\\:click="gotoPage({current_page}, \\\'page\\\')"]'
    
    def numbered_pages(self,
                        journal: str,
                        url: str,
                        date_init: datetime,
                        date_end: datetime,
                        term: str) -> dict:
        # Structure to crawl: Numbered pages
        # Type of webpage: Static (We use beautifulsoup)
        # The page is divided in numbered pages (page 1, page 2, etc.)
        # We loop through the different numbered pages, to get all the articles in each
        # We add every article (list of attributes) that is inside the desired interval to the dictionary
        utils.prints('url', url=url)
        dict_articles = {}
        dict_comments = {}

        try:
            current_page = 1
            more_articles = True
            utils.prints('current_page', current_page=current_page)
            # We use the function crawl_current_page to obtain the articles from the First page
            self.dynamic_methods.open_url(journal, url)
            tme.sleep(15)
            soup = self.dynamic_methods.get_soup(journal)

            (articles_current_page, comments_current_page, date_in_interval, successful_access) = self.numbered_pages_current_page(journal,
                                                                                                            date_init,
                                                                                                            date_end,
                                                                                                            soup,
                                                                                                            term)
            dict_articles.update(articles_current_page)
            dict_comments.update(comments_current_page)

            # We loop through the different numbered pages, until the articles are outside the date interval
            while date_in_interval and successful_access and more_articles:
                current_page += 1
                utils.prints('current_page', current_page=current_page)
                try:
                    # We wait for the button to be available
                    next_page_button_loc = self.define_next_page_button(current_page)

                    next_page_button_loc = WebDriverWait(self.crawler.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, next_page_button_loc)))
                except TimeoutException:
                    # If we couldn't find the button, it means there are no more articles in the page.
                    print(f"COULDN'T FIND THE BUTTON WITH CSS SELECTOR -> {next_page_button_loc}")
                    more_articles = False

                if more_articles:
                    # If there are more articles to look for, we press the button.
                    self.crawler.driver.execute_script("arguments[0].click();", next_page_button_loc)

                    # We wait until the location of the new list of articles is loaded

                    # We get the soup from the current html page
                    # We wait for the next page to load or we will get the soup from the previous page.
                    tme.sleep(15)
                    soup = self.dynamic_methods.get_soup(journal)

                    # We get all the new articles from the new numbered page.
                    (articles_current_page, comments_current_page, date_in_interval, successful_access) = self.numbered_pages_current_page(journal,
                                                                                                                date_init,
                                                                                                                date_end,
                                                                                                                soup,
                                                                                                                term)
                    dict_articles.update(articles_current_page)
                    dict_comments.update(comments_current_page)
        
        except Exception as e:
            print(f"\n--> There was an error crawling in journal {journal}")
            print(f"ERROR MESSAGE:\n{e}")
            traceback.print_exc()
            print("\n")
        
        return dict_articles, dict_comments
    
    def numbered_pages_current_page(self,
                                    journal: str,
                                    date_init: datetime,
                                    date_end: datetime,
                                    soup: BeautifulSoup,
                                    term: str):
        # Function used inside scrape_numbered_pages(...)
        # For each numbered page, we'll return a dictionary with all the articles inside the interval
        # We return the variable date_in_interval. If it's False, the loop in scrape_numbered_pages(...) will stop.
        
        dict_articles = {}
        dict_comments = {}
        date_in_interval = True
        successful_access = True
        
        if soup:
            try:

                articles = self.parser.all_articles(journal, soup)
                len_articles = len(articles)

                if len_articles == 0:
                    return {}, {}, False, successful_access

                date_article = self.crawler.NOW

                i = 0

                # Same method as scrape_single_page, except in the event we exit the date interval, we'll return a variable
                # date_in_interval = False so the loop in scrape_numbered_pages can stop.
                while date_init <= date_article and i < len_articles and date_in_interval:
                    article = articles[i]
                    date_article = self.parser.get_datetime(journal, article)
                    
                    if date_article <= date_end:
                        link = self.parser.get_link(journal, article)
                        soup = self.static_methods.get_soup(link)

                        article_id = self.add_article.define_article_id(journal, date_article)

                        if not article_id in self.crawler.saved_articles:
                            if date_init <= date_article:
                                dict_articles, dict_comments = self.add_article.add_article_to_dict(journal,
                                                                                    article,
                                                                                    article_id,
                                                                                    date_article,
                                                                                    link,
                                                                                    soup,
                                                                                    term,
                                                                                    dict_articles,
                                                                                    dict_comments)
                            else:
                                date_in_interval = False
                    i += 1
                
            except Exception as e:
                print(f"\n--> There was an error crawling in journal {journal}")
                print(f"ERROR MESSAGE:\n{e}")
                traceback.print_exc()
                print("\n")
                date_in_interval = False
        else:
            successful_access = False
        
        return (dict_articles, dict_comments, date_in_interval, successful_access)

class Periodic:

    def __init__(self, crawler_instance):

        # We define our crawler (argument) and parser (new object) instances
        self.crawler = crawler_instance
        self.parser = parser.Parser()

        # We get an instance of the different classes to obtain the methods we need
        self.static_methods = StaticMethods(self.crawler)
        self.dynamic_methods = DynamicMethods(self.crawler)
        self.add_article = AddArticle(self.crawler, self.parser, self.dynamic_methods)

        # We define all the variables to store locations or paths that we'll need

    def single_page(self,
                    journal: str,
                    url: str,
                    date_init: datetime,
                    date_end: datetime,
                    term: str) -> dict:
        # Structure to crawl: Single page
        # Type of webpage: Static/Dynamic (We use beautifulsoup no navigate, but we need selenium to access the url)
        # All the articles are on a single page. We get a single list with all the articles and loop through it
        # We add every article (list of attributes) that is inside the desired interval to the dictionary
        utils.prints('url', url=url)
        dict_articles = {}
        dict_comments = {}

        soup = self.dynamic_methods.get_soup(journal, url)

        if soup:
            try:

                articles = self.parser.all_articles(journal, soup)
                len_articles = len(articles)

                date_article = self.crawler.NOW

                # We loop through the article list to keep only the articles in the interval [date_init, date_end]
                i = 0
                while date_init <= date_article and i < len_articles:
                    article = articles[i]

                    # We get the article's datetime to check if we are inside the interval
                    date_article = self.parser.get_datetime(journal, article)

                    article_id = self.add_article.define_article_id(journal, date_article)

                    if not article_id in self.crawler.saved_articles:
                        if date_init <= date_article <= date_end:
                            # We get the artcle's link to turn into a soup object.
                            # We'll use soup to get the attributes and content we need from inside the article
                            link = self.parser.get_link(journal, article)
                            soup = self.dynamic_methods.get_soup(journal, link)
                            dict_articles, dict_comments = self.add_article.add_article_to_dict(journal,
                                                                                                article,
                                                                                                article_id,
                                                                                                date_article,
                                                                                                link,
                                                                                                soup,
                                                                                                term,
                                                                                                dict_articles,
                                                                                                dict_comments)
                    i += 1
            
            except Exception as e:
                print(f"\n--> There was an error crawling in journal {journal}")
                print(f"ERROR MESSAGE:\n{e}")
                traceback.print_exc()
                print("\n")
        
        return dict_articles, dict_comments

class Ara:

    def __init__(self, crawler_instance):

        # We define our crawler (argument) and parser (new object) instances
        self.crawler = crawler_instance
        self.parser = parser.Parser()

        # We get an instance of the different classes to obtain the methods we need
        self.static_methods = StaticMethods(self.crawler)
        self.dynamic_methods = DynamicMethods(self.crawler)
        self.add_article = AddArticle(self.crawler, self.parser, self.dynamic_methods)

        # We define all the variables to store locations or paths that we'll need
        self.load_more_button = self.crawler.sources_elements.loc['ara', 'load_more_button']
        self.load_next_page = self.crawler.sources_elements.loc['ara', 'load_next_page']

    def load_more_page(self,
                        journal: str,
                        url: str,
                        date_init: datetime,
                        date_end: datetime,
                        term: str) -> dict:
        # Structure to crawl: Load more page
        # Type of webpage: Dynamic (We use Selenium)
        # All the articles are on a single page. There is a "Show more" button at the end which will show more articles
        # each time we press it. We use a loop that gets all the current articles, and presses the button to get more
        # articles until we are outside the interval
        utils.prints('url', url=url)
        dict_articles = {}
        dict_comments = {}

        try:
            soup = self.dynamic_methods.get_soup(journal, url)
            articles = self.parser.all_articles(journal, soup)
            date_article = self.crawler.NOW
            more_articles = True

            i = 0
            # We use a loop that will get the current articles, click the "Show more" button, get the next list of articles...
            while date_init <= date_article and more_articles:
                j = 0
                while date_article >= date_init and j < len(articles):
                    article = articles[j]
                    link = self.parser.get_link(journal, article)
                    soup = self.dynamic_methods.get_soup(journal, link)
                    date_article = self.parser.get_datetime(journal, article, soup)

                    article_id = self.add_article.define_article_id(journal, date_article)

                    if not article_id in self.crawler.saved_articles:
                        if date_init <= date_article <= date_end:
                            dict_articles, dict_comments = self.add_article.add_article_to_dict(journal,
                                                                                                article,
                                                                                                article_id,
                                                                                                date_article,
                                                                                                link,
                                                                                                soup,
                                                                                                term,
                                                                                                dict_articles,
                                                                                                dict_comments)
                    j += 1

                # Each time we press the button, the new articles are inside the tag located in next_page_loc.
                # If the number of tags next_page_loc is smaller than i + 1, we press the button to get more articles
                #self.dynamic_methods.open_url(journal, url)
                while len(self.crawler.driver.find_elements(By.CSS_SELECTOR, self.load_next_page)) < i + 1 and more_articles:
                    try:
                        # We wait for the button to be available
                        load_more_button = WebDriverWait(self.crawler.driver, 15).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, self.load_more_button)))
                    except TimeoutException:
                        # If we couldn't find the button, it means there are no more articles in the page.
                        more_articles = False

                    if more_articles:
                        # If there are more articles to look for, we press the button.
                        utils.prints('loading_more_results')
                        self.crawler.driver.execute_script("arguments[0].click();", load_more_button)

                if more_articles:
                    # We wait until the location of the new list of articles is loaded
                    WebDriverWait(self.crawler.driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR,
                                                                                                 self.load_next_page)))
                    # We get the next list of articles from the current next_page_log tag.
                    soup = self.dynamic_methods.get_soup(journal)
                    articles = self.parser.next_all_articles(journal, soup, i)
                    i += 1

        except Exception as e:
            print(f"\n--> There was an error crawling in journal {journal}")
            print(f"ERROR MESSAGE:\n{e}")
            traceback.print_exc()
            print("\n")

        return dict_articles, dict_comments
    
class Diari:

    def __init__(self, crawler_instance):

        # We define our crawler (argument) and parser (new object) instances
        self.crawler = crawler_instance
        self.parser = parser.Parser()

        # We get an instance of the different classes to obtain the methods we need
        self.static_methods = StaticMethods(self.crawler)
        self.dynamic_methods = DynamicMethods(self.crawler)
        self.add_article = AddArticle(self.crawler, self.parser, self.dynamic_methods)

        # We define all the variables to store locations or paths that we'll need
        self.next_page = None

    def numbered_pages(self,
                        journal: str,
                        url: str,
                        date_init: datetime,
                        date_end: datetime,
                        term: str) -> dict:
        # Structure to crawl: Numbered pages
        # Type of webpage: Static (We use beautifulsoup)
        # The page is divided in numbered pages (page 1, page 2, etc.)
        # We loop through the different numbered pages, to get all the articles in each
        # We add every article (list of attributes) that is inside the desired interval to the dictionary

        dict_articles = {}
        dict_comments = {}

        try:
            current_page = 1
            utils.prints('current_page', current_page=current_page)

            # We use the function crawl_current_page to obtain the articles from the First page
            (articles_current_page, comments_current_page, date_in_interval, successful_access) = self.numbered_pages_current_page(journal,
                                                                                                            url,
                                                                                                            date_init,
                                                                                                            date_end,
                                                                                                            term)
            dict_articles.update(articles_current_page)
            dict_comments.update(comments_current_page)

            # We loop through the different numbered pages, until the articles are outside the date interval
            while date_in_interval and successful_access:
                current_page += 1
                utils.prints('current_page', current_page=current_page)
                # We define the next url (next numbered page) thanks to the function numbered_page_url
                next_url = utils.numbered_page_url(journal, url, self.next_page, current_page)
                # We get all the new articles from the new numbered page.
                (articles_current_page, comments_current_page, date_in_interval, successful_access) = self.numbered_pages_current_page(journal,
                                                                                                                next_url,
                                                                                                                date_init,
                                                                                                                date_end,
                                                                                                                term)
                dict_articles.update(articles_current_page)
                dict_comments.update(comments_current_page)
        
        except Exception as e:
            print(f"\n--> There was an error crawling in journal {journal}")
            print(f"ERROR MESSAGE:\n{e}")
            traceback.print_exc()
            print("\n")
        
        return dict_articles, dict_comments
    
    def numbered_pages_current_page(self,
                                    journal: str,
                                    url: str,
                                    date_init: datetime,
                                    date_end: datetime,
                                    term):
        # Function used inside scrape_numbered_pages(...)
        # For each numbered page, we'll return a dictionary with all the articles inside the interval
        # We return the variable date_in_interval. If it's False, the loop in scrape_numbered_pages(...) will stop.
        utils.prints('url', url=url)
        dict_articles = {}
        dict_comments = {}
        date_in_interval = True
        successful_access = True

        soup = self.static_methods.get_soup(url)
        
        if soup:
            try:

                articles = self.parser.all_articles(journal, soup)
                len_articles = len(articles)

                if len_articles == 0:
                    return {}, {}, False, successful_access

                date_article = self.crawler.NOW

                i = 0
                # Same method as scrape_single_page, except in the event we exit the date interval, we'll return a variable
                # date_in_interval = False so the loop in scrape_numbered_pages can stop.
                while date_init <= date_article and i < len_articles and date_in_interval:
                    article = articles[i]
                    date_article = self.parser.get_datetime(journal, article)

                    article_id = self.add_article.define_article_id(journal, date_article)

                    if not article_id in self.crawler.saved_articles:
                        if date_article <= date_end:
                            link = self.parser.get_link(journal, article)
                            soup = self.static_methods.get_soup(link)
                            if date_init <= date_article:
                                dict_articles, dict_comments = self.add_article.add_article_to_dict(journal,
                                                                                    article,
                                                                                    article_id,
                                                                                    date_article,
                                                                                    link,
                                                                                    soup,
                                                                                    term,
                                                                                    dict_articles,
                                                                                    dict_comments)
                            else:
                                date_in_interval = False
                    i += 1
                
            except Exception as e:
                print(f"\n--> There was an error crawling in journal {journal}")
                print(f"ERROR MESSAGE:\n{e}")
                traceback.print_exc()
                print("\n")
                date_in_interval = False
        else:
            successful_access = False
        
        return (dict_articles, dict_comments, date_in_interval, successful_access)
    
""" -- THE MAIN SCRAPER --"""
class Scraper:

    def __init__(self, crawler_instance):

        self.crawler = crawler_instance
        # crawler_instance has the following attributes:
        #   search_terms: list
        #   date_init:    datetime
        #   date_end:     datetime
        
    def word_to_url(self, journal: str, term: str) -> str:
        # Depending on the word we're looking for, we return an url that goes directly to the search results of that word

        # If the word we're looking for has spaces, we need to separate it and put a character in between, that will change
        # for each journal
        words = term.split(' ')
        word_count = len(words)

        # We define the base strings that, together with the word, will create a valid url
        urls = {'altaveu': "https://www.altaveu.com/cercador.html?search=",
                'periodic': "https://www.elperiodic.ad/cerca?que=",
                'ara': "https://www.ara.ad/cercador?text=",
                'bondia': "https://www.bondia.ad/cercador?search=",
                'diari': "https://www.diariandorra.ad/search/?query=",
                'forum': "https://forum.ad/?s="}
        
        match journal:
            case 'altaveu' | 'diari' | 'bondia':
                url = urls[journal] + words[0]
                i = 1
                while i < word_count:
                    url = url + '+' + words[i]
                    i += 1
            case 'periodic':
                url = urls[journal] + words[0]
                i = 1
                while i < word_count:
                    url = url + "%20" + words[i]
                    i += 1
            case 'ara':
                url = urls[journal] + '"' + words[0]
                i = 1
                while i < word_count:
                    url = url + '%20' + words[i]
                    i += 1
                url = url + '"'
            case 'forum':
                url = urls[journal] + '%22' + words[0]
                i = 1
                while i < word_count:
                    url = url + '+' + words[i]
                    i += 1
                url = url + "%22&submit=Search"

        return url

    def scrape(self, journal: str) -> dict:

        result = {}
        result_comments = {}

        self.crawler.cookies_clicked = False
        self.crawler.notifs_clicked = False

        for term in self.crawler.search_terms:
            utils.prints('term', term=term)
            # already_saved = result
            url = self.word_to_url(journal, term)

            match journal:
                case 'altaveu':
                    # numbered_pages (dynamic comments)
                    articles, comments = Altaveu(self.crawler).numbered_pages(journal,
                                                                                url,
                                                                                self.crawler.date_init,
                                                                                self.crawler.date_end,
                                                                                term)
                    result.update(articles)
                    result_comments.update(comments)

                case 'forum':
                    # numbered_pages
                    articles, comments = Forum(self.crawler).numbered_pages(journal,
                                                                                url,
                                                                                self.crawler.date_init,
                                                                                self.crawler.date_end,
                                                                                term)
                    result.update(articles)
                    result_comments.update(comments)

                case 'bondia':
                    articles, comments = Bondia(self.crawler).numbered_pages(journal,
                                                                                url,
                                                                                self.crawler.date_init,
                                                                                self.crawler.date_end,
                                                                                term)
                    result.update(articles)
                    result_comments.update(comments)

                case 'periodic':
                    # single_page 
                    articles, comments = Periodic(self.crawler).single_page(journal,
                                                                            url,
                                                                            self.crawler.date_init,
                                                                            self.crawler.date_end,
                                                                            term)
                    result.update(articles)
                    result_comments.update(comments)

                case 'ara':
                    # load_more_page
                    articles, comments = Ara(self.crawler).load_more_page(journal,
                                                                                url,
                                                                                self.crawler.date_init,
                                                                                self.crawler.date_end,
                                                                                term)
                    result.update(articles)
                    result_comments.update(comments)

                case 'diari':
                    # next_page
                    articles, comments = Diari(self.crawler).numbered_pages(journal,
                                                                                url,
                                                                                self.crawler.date_init,
                                                                                self.crawler.date_end,
                                                                                term)
                    result.update(articles)
                    result_comments.update(comments)

        return result, result_comments