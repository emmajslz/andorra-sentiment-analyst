import re
import time as tme
import traceback

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
    
    def add_article_to_dict(self,
                            journal: str,
                            article,
                            date_article: datetime,
                            link: str,
                            soup: BeautifulSoup,
                            dict_articles: dict,
                            date_end: datetime,
                            already_saved=None,
                            term=None) -> dict:
        # For each article, we use this function to determine wether or not it should be added to the dictionary,
        # get all the attributes we want, all the comments in the article (if there are any) and append all of
        # the information to the dictionary.
        # Because we look in different places, we use the already_saved argument. We pass the already existing dictionary
        # and only add the article to the current dictionary if it isn't already in already_saved.
        
        new_article = False
        # We get all the attributes we don't already have
        title = self.parser.get_title(journal, article)
        category = self.parser.get_category(journal, article, soup)
        type_article = utils.category_type(category)
        
        # We construct the article id
        id = journal + "-" + str(date_article) + "-" + title

        # We check if the article isn't in already_saved.
        if (already_saved is None) or not (id in already_saved):

            # We get the content in the article
            subtitle, content = self.parser.get_content(journal, soup)

            utils.prints('article', date_article=date_article, title=title)

            # We add a line with all the comment information blank. If there are no comments, the article will only
            # have this line, and if there are comments, we'll have a line that only defines the article.
            dict_articles[id] = [self.crawler.NOW, journal, term, date_article, category, type_article,
                                title, link, subtitle, content,
                                "", "", "", "", "", "", "", ""]
            # We use new_article = True, when we print the comment information, we won't print the article as
            # it's already added.
            new_article = True

            # We get all the comments in the article with the get_comments(...) function. If there are none,
            # get_comments(...) will return an empty list.
            comments = self.comments.get_comments(journal, link, soup)
            utils.prints('comments', len_comments=len(comments), date_article=date_article, new_article=new_article)
            # We loop through the list (if it's not empty) and add a new element to the article for each comment,
            # with the comment information at the end.
            for comment in comments:
                dict_articles[id + "-" + str(comment[0])] = [self.crawler.NOW, journal, term, date_article,
                                                             category, type_article,
                                                             title, link, subtitle, content,
                                                             comment[0], comment[1], comment[2], comment[3],
                                                             comment[4], comment[5], comment[6], comment[7]]

        return dict_articles

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

        if journal == "altaveu":
            # Comments are loaded dynamically, so we get them with Selenium
            self.dynamic_methods.open_url(journal, url)
            # We load all comments
            self.load_all_comments(journal)
            # We create a BeautifulSoup object with the current page_source
            soup = BeautifulSoup(self.crawler.driver.page_source, 'html.parser')
            return self.get_comments_soup(journal, soup)

        elif journal == "diari":
            # Because we are already using Selenium to get the articles, we need to open a different window to get the
            # article's comments, as to keep the current window intact and be able to keep using it.
            self.dynamic_methods.url_in_second_window('open', url)
            # We load all comments
            self.load_all_comments(journal)
            # We create a BeautifulSoup object with the current page_source
            soup = BeautifulSoup(self.crawler.driver.page_source, 'html.parser')
            return self.get_comments_soup(journal, soup, second_window=True)

        elif journal == "bondia":
            # As the comments in this journal are not loaded dynamically, we can directly use the current soup object
            # to get the comment_list
            return self.get_comments_soup(journal, soup)

        else:
            # If we are not in a journal that has comments, we return an empty list
            return []
        
    def get_comments_soup(self, journal, soup, second_window=False):
        # Once we have the soup, we can create a list of lists with all the comment attributes
        # Each element in comment_list is a comment: a list of attributes

        comment_list = []

        # We get the list of all the comments
        if journal == "altaveu":
            comments = soup.find_all('div', attrs={"data-type": "comment"})
        elif journal == "diari":
            if soup.find_all('div', class_="lst-com con brr"):
                comments = soup.find('div', class_="lst-com con brr").ul.find_all('li', class_=re.compile("con.*"))
            else:
                comments = []
        elif journal == "bondia":
            comments = soup.find_all('div', attrs={'class': re.compile("comment.*"), 'typeof': "sioc:Post sioct:Comment"})

        len_comments = len(comments)

        # We loop through the list
        # We use get_comment_attributes(...) to get each comment's info. It returns a list of attributes
        # We append each list of attributes to comment_list, creating a list of lists with all the comments.
        for i in range(0, len_comments):
            comment = comments[i]
            attributes = self.parser.get_comment_attributes(journal, comment)
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

        # We define the locations of the buttons to press in each journal as XPATHs
        self.cookies = {'altaveu': '//*[contains(text(), "AGREE")]',
                        'diari': '//button[@class="cky-btn cky-btn-accept"]',
                        'ara': '//button[@id="didomi-notice-agree-button"]',
                        'ser': '//button[@id="didomi-notice-agree-button"]'}

        self.notifs = {'altaveu': '//button[@class="align-right secondary slidedown-button"]',
                        'periodic': '//button[@class="align-right secondary slidedown-button"]',
                        'dairi': '//div[@class="cancel-notification"]'}
    
        # Load more button locations
        self.load_more_button = {'ara': 'button[class="ara-button secondary"]'}
        self.load_next_page = {'ara': 'div[class="page-container"]'}

        # All articles locs
        # We define the location of the articles for each journal as XPATHs
        self.all_articles_locs = {"ara": '//article[@class="ara-card ara-card--article"]',
                                  "diari": '//ul[@class="tir-f1 con resultadosBusquedaBS"]/li',
                                  "ser": '//div[@class="queryly_item_row"]'}

    def buttons(self, journal: str) -> None:
        # We click the cookies and notifications buttons in the event we just opened the webpage and there are cookies and
        # notifications pop ups that would not allow us to see the information on the page

        # If the button hasn't been already pressed, journal is in cookies (meaning there is a button to press)
        # and the button is there:
        if not self.crawler.cookies_clicked and journal in self.cookies and self.crawler.driver.find_elements(By.XPATH, self.cookies[journal]):
            cookies_accept = self.crawler.driver.find_element(By.XPATH, self.cookies[journal])
            self.crawler.driver.execute_script("arguments[0].click();", cookies_accept)
            self.crawler.cookies_clicked = True

        if not self.crawler.notifs_clicked and journal in self.notifs and self.crawler.driver.find_elements(By.XPATH, self.notifs[journal]):
            notifications = self.crawler.driver.find_element(By.XPATH, self.notifs[journal])
            self.crawler.driver.execute_script("arguments[0].click();", notifications)
            self.crawler.notifs_clicked = True

    def opening_url_actions(self, journal: str, term: str = None) -> None:  # journal specific !!
        # Each journal has some actions we need to do after opening the url with the driver (sortin, adverts, etc.)

        match journal:
            case 'diari':
                # We look for the search box
                search_box = self.crawler.driver.find_element(By.XPATH, '//input[@placeholder="Paraula a buscar"]')
                # We input the word on the search box
                search_box.send_keys('"' + term + '"')
                # We look for the "search" button
                search_button = self.crawler.driver.find_element(By.XPATH, '//input[@id="busc_btn"]')
                # We click it
                self.crawler.driver.execute_script("arguments[0].click();", search_button)
                # In this particular case, we have to use hard waits like .sleep(5) because of this journal's dynamic DOM
                # (see documentation)
                tme.sleep(5)
            case 'ser':
                # We change the sort order so we can loop through the articles correctly
                order = Select(self.crawler.driver.find_element(By.ID, 'sortby'))
                order.select_by_value('date')
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
            if self.open_url(journal, url):
                soup = BeautifulSoup(self.crawler.driver.page_source, 'html.parser')
                return soup
            else:
                return None
        else:
            return BeautifulSoup(self.crawler.driver.page_source, 'html.parser')
    
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

        # We wait until we can find the elements to begin
        WebDriverWait(self.crawler.driver, 15).until(EC.presence_of_element_located((By.XPATH, self.all_articles_locs[journal])))

        # If we are looking for articles after clicking on the "Show more" button, we can't search the whole page
        # but only the articles that are new
        if next_page is None:
            return self.crawler.driver.find_elements(By.XPATH, self.all_articles_locs[journal])
        else:
            return next_page.find_elements(By.XPATH, '.' + self.all_articles_locs[journal])
    
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
                              already_saved=None,
                              term=None) -> dict:
        # Structure to crawl: Numbered pages
        # Type of webpage: Static (We use beautifulsoup)
        # The page is divided in numbered pages (page 1, page 2, etc.)
        # We loop through the different numbered pages, to get all the articles in each
        # We add every article (list of attributes) that is inside the desired interval to the dictionary

        dict_articles = {}

        try:
            current_page = 1

            # We use the function crawl_current_page to obtain the articles from the First page
            (articles_current_page, date_in_interval, successful_access) = self.numbered_pages_current_page(journal,
                                                                                                            url,
                                                                                                            date_init,
                                                                                                            date_end,
                                                                                                            already_saved)
            dict_articles.update(articles_current_page)

            # We loop through the different numbered pages, until the articles are outside the date interval
            while date_in_interval and successful_access:
                current_page += 1
                # We define the next url (next numbered page) thanks to the function numbered_page_url
                next_url = utils.numbered_page_url(journal, url, self.next_page, current_page)
                # We get all the new articles from the new numbered page.
                (articles_current_page, date_in_interval, successful_access) = self.numbered_pages_current_page(journal,
                                                                                                                next_url,
                                                                                                                date_init,
                                                                                                                date_end,
                                                                                                                already_saved,
                                                                                                                term=term)
                dict_articles.update(articles_current_page)
        
        except Exception as e:
            print(f"\n--> There was an error crawling in journal {journal}")
            print(f"ERROR MESSAGE:\n{e}")
            traceback.print_exc()
            print("\n")
        
        return dict_articles   
    
    def numbered_pages_current_page(self,
                                    journal: str,
                                    url: str,
                                    date_init: datetime,
                                    date_end: datetime,
                                    already_saved=None,
                                    term=None):
        # Function used inside scrape_numbered_pages(...)
        # For each numbered page, we'll return a dictionary with all the articles inside the interval
        # We return the variable date_in_interval. If it's False, the loop in scrape_numbered_pages(...) will stop.

        dict_articles = {}
        date_in_interval = True
        successful_access = True

        soup = self.static_methods.get_soup(url)
        
        if soup:
            try:

                articles = self.parser.all_articles(journal, soup)
                len_articles = len(articles)

                if len_articles == 0:
                    return {}, False, successful_access

                date_article = self.crawler.NOW

                i = 0
                # Same method as scrape_single_page, except in the event we exit the date interval, we'll return a variable
                # date_in_interval = False so the loop in scrape_numbered_pages can stop.
                while date_init <= date_article and i < len_articles and date_in_interval:
                    article = articles[i]
                    link = self.parser.get_link(journal, article)
                    soup = self.static_methods.get_soup(link)
                    date_article = self.parser.get_datetime(journal, article, soup)
                    if date_article <= date_end:
                        if date_init <= date_article:
                            dict_articles = self.add_article.add_article_to_dict(journal, article, date_article, link, soup,
                                                                    dict_articles, date_end, already_saved, term)
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
        
        return (dict_articles, date_in_interval, successful_access)

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
                        already_saved=None,
                        term=None) -> dict:
        # Structure to crawl: Numbered pages
        # Type of webpage: Static (We use beautifulsoup)
        # The page is divided in numbered pages (page 1, page 2, etc.)
        # We loop through the different numbered pages, to get all the articles in each
        # We add every article (list of attributes) that is inside the desired interval to the dictionary

        dict_articles = {}

        try:
            current_page = 1

            # We use the function crawl_current_page to obtain the articles from the First page
            (articles_current_page, date_in_interval, successful_access) = self.numbered_pages_current_page(journal,
                                                                                                            url,
                                                                                                            date_init,
                                                                                                            date_end,
                                                                                                            already_saved)
            dict_articles.update(articles_current_page)

            # We loop through the different numbered pages, until the articles are outside the date interval
            while date_in_interval and successful_access:
                current_page += 1
                # We define the next url (next numbered page) thanks to the function numbered_page_url
                next_url = utils.numbered_page_url(journal, url, self.next_page, current_page)
                # We get all the new articles from the new numbered page.
                (articles_current_page, date_in_interval, successful_access) = self.numbered_pages_current_page(journal,
                                                                                                                next_url,
                                                                                                                date_init,
                                                                                                                date_end,
                                                                                                                already_saved,
                                                                                                                term=term)
                dict_articles.update(articles_current_page)
        
        except Exception as e:
            print(f"\n--> There was an error crawling in journal {journal}")
            print(f"ERROR MESSAGE:\n{e}")
            traceback.print_exc()
            print("\n")
        
        return dict_articles   
    
    def numbered_pages_current_page(self,
                                    journal: str,
                                    url: str,
                                    date_init: datetime,
                                    date_end: datetime,
                                    already_saved=None,
                                    term=None):
        # Function used inside scrape_numbered_pages(...)
        # For each numbered page, we'll return a dictionary with all the articles inside the interval
        # We return the variable date_in_interval. If it's False, the loop in scrape_numbered_pages(...) will stop.

        dict_articles = {}
        date_in_interval = True
        successful_access = True

        soup = self.static_methods.get_soup(url)
        
        if soup:
            try:

                articles = self.parser.all_articles(journal, soup)
                len_articles = len(articles)

                if len_articles == 0:
                    return {}, False, successful_access

                date_article = self.crawler.NOW

                i = 0
                # Same method as scrape_single_page, except in the event we exit the date interval, we'll return a variable
                # date_in_interval = False so the loop in scrape_numbered_pages can stop.
                while date_init <= date_article and i < len_articles and date_in_interval:
                    article = articles[i]
                    link = self.parser.get_link(journal, article)
                    soup = self.static_methods.get_soup(link)
                    date_article = self.parser.get_datetime(journal, article, soup)
                    if date_article <= date_end:
                        if date_init <= date_article:
                            dict_articles = self.add_article.add_article_to_dict(journal, article, date_article, link, soup,
                                                                    dict_articles, date_end, already_saved, term)
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
        
        return (dict_articles, date_in_interval, successful_access)

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
        self.next_page = self.crawler.sources_elements.loc['bondia', 'next_page']

    def numbered_pages(self,
                              journal: str,
                              url: str,
                              date_init: datetime,
                              date_end: datetime,
                              already_saved=None,
                              term=None) -> dict:
        # Structure to crawl: Numbered pages
        # Type of webpage: Static (We use beautifulsoup)
        # The page is divided in numbered pages (page 1, page 2, etc.)
        # We loop through the different numbered pages, to get all the articles in each
        # We add every article (list of attributes) that is inside the desired interval to the dictionary

        dict_articles = {}

        try:
            current_page = 1

            # We use the function crawl_current_page to obtain the articles from the First page
            (articles_current_page, date_in_interval, successful_access) = self.numbered_pages_current_page(journal,
                                                                                                            url,
                                                                                                            date_init,
                                                                                                            date_end,
                                                                                                            already_saved)
            dict_articles.update(articles_current_page)

            # We loop through the different numbered pages, until the articles are outside the date interval
            while date_in_interval and successful_access:
                current_page += 1
                # We define the next url (next numbered page) thanks to the function numbered_page_url
                next_url = utils.numbered_page_url(journal, url, self.next_page[journal], current_page)
                # We get all the new articles from the new numbered page.
                (articles_current_page, date_in_interval, successful_access) = self.numbered_pages_current_page(journal,
                                                                                                            next_url,
                                                                                                            date_init,
                                                                                                            date_end,
                                                                                                            already_saved,
                                                                                                            term=term)
                dict_articles.update(articles_current_page)
        
        except Exception as e:
            print(f"\n--> There was an error crawling in journal {journal}")
            print(f"ERROR MESSAGE:\n{e}")
            traceback.print_exc()
            print("\n")
        
        return dict_articles
    
    def numbered_pages_current_page(self,
                                    journal: str,
                                    url: str,
                                    date_init: datetime,
                                    date_end: datetime,
                                    already_saved=None,
                                    term=None):
        # Function used inside scrape_numbered_pages(...)
        # For each numbered page, we'll return a dictionary with all the articles inside the interval
        # We return the variable date_in_interval. If it's False, the loop in scrape_numbered_pages(...) will stop.

        dict_articles = {}
        date_in_interval = True
        successful_access = True

        soup = self.get_soup(url)
        
        if soup:
            try:

                articles = self.parser.all_articles(journal, soup)
                len_articles = len(articles)

                if len_articles == 0:
                    return {}, False, successful_access

                date_article = self.crawler.NOW

                i = 0
                # Same method as scrape_single_page, except in the event we exit the date interval, we'll return a variable
                # date_in_interval = False so the loop in scrape_numbered_pages can stop.
                while date_init <= date_article and i < len_articles and date_in_interval:
                    article = articles[i]
                    link = self.parser.get_link(journal, article)
                    soup = self.get_soup(link)
                    date_article = self.parser.get_datetime(journal, article, soup)
                    if date_article <= date_end:
                        if date_init <= date_article:
                            dict_articles = self.add_article.add_article_to_dict(journal, article, date_article, link, soup,
                                                                    dict_articles, date_end, already_saved, term)
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
        
        return (dict_articles, date_in_interval, successful_access)

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
                    already_saved=None,
                    term=None) -> dict:
        # Structure to crawl: Single page
        # Type of webpage: Static/Dynamic (We use beautifulsoup no navigate, but we need selenium to access the url)
        # All the articles are on a single page. We get a single list with all the articles and loop through it
        # We add every article (list of attributes) that is inside the desired interval to the dictionary

        dict_articles = {}

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

                    # We get the artcle's link to turn into a soup object.
                    # We'll use soup to get the attributes and content we need from inside the article
                    link = self.parser.get_link(journal, article)
                    soup = self.dynamic_methods.get_soup(journal, link)

                    # We get the article's datetime to check if we are inside the interval
                    date_article = self.parser.get_datetime(journal, article, soup)

                    # If the atricle is in the desired interval, we use add_article_to_dict(...) to add it to the dictionary
                    if date_init <= date_article <= date_end:
                        dict_articles = self.add_article.add_article_to_dict(journal,article, date_article, link, soup,
                                                                            dict_articles, date_end, already_saved, term)
                    i += 1
            
            except Exception as e:
                print(f"\n--> There was an error crawling in journal {journal}")
                print(f"ERROR MESSAGE:\n{e}")
                traceback.print_exc()
                print("\n")
        
        return dict_articles

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
                                already_saved=None,
                                term=None):
        # Structure to crawl: Load more page
        # Type of webpage: Dynamic (We use Selenium)
        # All the articles are on a single page. There is a "Show more" button at the end which will show more articles
        # each time we press it. We use a loop that gets all the current articles, and presses the button to get more
        # articles until we are outside the interval

        dict_articles = {}

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
                    if date_init <= date_article <= date_end:
                        dict_articles = self.add_article.add_article_to_dict(journal, article, date_article, link, soup,
                                                                            dict_articles, date_end, already_saved, term)
                    j += 1

                # Each time we press the button, the new articles are inside the tag located in next_page_loc.
                # If the number of tags next_page_loc is smaller than i + 1, we press the button to get more articles
                self.dynamic_methods.open_url(journal, url)
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

        return dict_articles
    
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
    
class Ser:

    def __init__(self, crawler_instance):

        # We define our crawler (argument) and parser (new object) instances
        self.crawler = crawler_instance
        self.parser = parser.Parser()

        # We get an instance of the different classes to obtain the methods we need
        self.static_methods = StaticMethods(self.crawler)
        self.dynamic_methods = DynamicMethods(self.crawler)
        self.add_article = AddArticle(self.crawler, self.parser, self.dynamic_methods)

        # We define all the variables to store locations or paths that we'll need

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
                'forum': "https://forum.ad/?s=",
                'ser': "https://cadenaser.com/buscar/?query="}
        
        match journal:
            case 'altaveu' | 'ser' | 'diari' | 'bondia':
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

        self.crawler.cookies_clicked = False
        self.crawler.notifs_clicked = False

        for term in self.crawler.search_terms:
            utils.prints('term', term=term)
            already_saved = result
            url = self.word_to_url(journal, term)
            utils.prints('url', url=url)
            match journal:
                case 'altaveu' | 'forum':
                    # numbered_pages (dynamic comments)
                    result.update(Altaveu(self.crawler).numbered_pages(journal,
                                                                        url,
                                                                        self.crawler.date_init,
                                                                        self.crawler.date_end,
                                                                        already_saved,
                                                                        term))
                case 'forum':
                    # numbered_pages
                    result.update(Forum(self.crawler).numbered_pages(journal,
                                                                        url,
                                                                        self.crawler.date_init,
                                                                        self.crawler.date_end,
                                                                        already_saved,
                                                                        term))
                case 'bondia':
                    result.update(Bondia(self.crawler).numbered_pages(journal,
                                                                url,
                                                                self.crawler.date_init,
                                                                self.crawler.date_end,
                                                                already_saved,
                                                                term))
                case 'periodic':
                    # single_page 
                    result.update(Periodic(self.crawler).single_page(journal,
                                                                url,
                                                                self.crawler.date_init,
                                                                self.crawler.date_end,
                                                                already_saved,
                                                                term))
                case 'ara':
                    # load_more_page
                    result.update(Ara(self.crawler).load_more_page(journal,
                                                                url,
                                                                self.crawler.date_init,
                                                                self.crawler.date_end,
                                                                already_saved,
                                                                term))
                case 'diari' | 'ser':
                    # next_page
                    result.update({})

        return result