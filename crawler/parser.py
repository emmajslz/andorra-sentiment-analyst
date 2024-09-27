import unidecode
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

class Parser:

    def __init__(self):
        return None

    def all_articles(self, journal: str, soup: BeautifulSoup) -> list:

        locs = {
            'altaveu': ('div', "c-news-list__wrapper"),
            'periodic': ('li', re.compile("item article article_llistat.*")),
            'bondia': ('div', "flex flex-col gap-1"),
            'forum': ('article', re.compile("^entry author-.* post-.*")),
            'ara': ('article', "ara-card ara-card--article"),
            'diari': ('article', "c-article c-article--lateral size-12")
        }

        if journal == 'bondia':
            soup = soup.find('section', class_="col-span-12")

        return soup.find_all(locs[journal][0], class_=locs[journal][1])
    
    def next_all_articles(self, journal: str, soup: BeautifulSoup, i) -> list:

        match journal:
            case 'ara':
                next_pages = soup.find('div', class_="next-page").find_all('div', class_="page-container")[i]
                return self.all_articles(journal, next_pages)

    def get_datetime(self, journal: str, article, soup: BeautifulSoup = None) -> datetime:
        # We look for the article's datetime (current element on the list)

        # In some cases, we'll need to look for the category inside the article (once we get the link).
        # We use the function get_category_in_article(journal, soup) to achieve this

        # We define the date formats to pass as argument for the function string_to_datetime(string, date_format)
        date_formats = {'altaveu': "%d/%m/%Y (%H:%M CET)",
                        'periodic': "%d.%m.%Y - %H:%M h",
                        'ara': "%Y-%m-%dT%H:%M:%S",
                        'bondia': "%Y-%m-%d %H:%M:%S",
                        'diari': "%d.%m.%Y | %H:%M",
                        'forum': ["%d/%m/%y %H:%M", "%d/%m/%Y %H:%M"]}

        # Variables that will indicate to the string_to_datetime(string, date_format) function how it should proceed
        # formatted is True if the string we obtain from the web can be turned into a datetime object
        # with the strptime method
        formatted = True
        # multiple_format is True if dates can be in different formats.
        multiple_formats = False

        match journal:
            case 'altaveu':
                date_string = self.get_datetime_in_article(journal, soup)
            case 'periodic':
                date_string = article.a.div.time.string
            case 'ara':
                date_string = self.get_datetime_in_article(journal, soup)
            case 'bondia':
                date_string = article.find('div', class_="flex flex-row gap-2 italic text-sm").span.text
            case 'diari':
                date_string = article.find('time', class_="c-article__date").text.strip()
            case 'forum':
                date_string = article.div.div.time.string
                multiple_formats = True

        # We use the string_to_datetime(...) function to return a datetime object.
        # We .strip() the text to avoid unnecessary spaces at the beggining or the end.
        return utils.string_to_datetime(date_string.strip(), date_formats[journal], formatted, multiple_formats)

    def get_link(self, journal: str, article) -> str:

        match journal:
            case 'altaveu':
                return article.h2.a['href']
            case 'periodic':
                return article.a['href']
            case 'ara':
                return article.a['href']
            case 'bondia':
                return article.find('a')['href'].strip()
            case 'diari':
                return article.find('h2', class_="c-article__title").a['href']
            case 'forum':
                return article.div.div.header.h2.a['href']

    def get_title(self, journal: str, article):
        # We look for the article's title (current element on the list)

        match journal:
            case 'altaveu':
                return article.h2.a.string
            case 'periodic':
                return article.a.div.h2.string
            case 'ara':
                return article.a['title']
            case 'bondia':
                return article.find('a').text.strip()
            case 'diari':
                return article.find('h2', class_="c-article__title").a.text.strip()
            case 'forum':
                return article.div.div.header.h2.a.string

    def get_category(self, journal, article, soup):
        # We look for the article's category (current element on the list)

        # In some cases, we'll need to look for the category inside the article (once we get the link).
        # We use the function get_category_in_article(journal, soup) to achieve this

        match journal:
            case 'altaveu':
                category = article.p.a.string
            case 'periodic':
                # the article's attribute class in this case is a list. If there are only three elements on this list, it means
                # the article has category "noticia". If there are more than three elements, the fourth element will determine
                # the article's cateogory. Fourth element is a string: article_category
                category = article['class']
                if len(category) == 3:
                    category = "notícia"
                else:
                    category = category[3][8:]
            case 'ara':
                category = article.div.div.a.text
            case 'bondia':
                category = article.div.div.div.text
            case 'diari':
                category = article.find('h2', class_="c-article__title").a['href'].split('/')[3]
            case 'forum':
                # The 8th element on the list is the category.
                if len(article['class']) > 8:
                    category = article['class'][8][9:]
                else:
                    # In this case, some articles do not have a category informed. We leave category as blank.
                    category = ""

        # We use unidecode to get rid of special characters (à, é, etc.) and .lower() to get rid of caps.
        # The idea is for the categories to be as similar as possible between journals
        return unidecode.unidecode(category.lower())

    # -- Inside the article -----------------------
    def get_datetime_in_article(self, journal: str, soup: BeautifulSoup) -> str:
        # In the event that the datetime isn't available in the main article list, we open the article to get it.

        match journal:
            case 'altaveu':
                return soup.find('time', attrs={'class': "c-mainarticle__time"}).string
            case 'diari':
                return soup.find('meta', attrs={'property': "article:modified_time"})['content']
            case 'ara':
                return soup.find('meta', attrs={'property': "article:modified_time"})['content'].split('+')[0]

    def get_content(self, journal, soup):
        # We look for the content of the article and the subtitle in case it has one.
        # only altaveu, periodic, and ara have subtitle

        # We define the location of the content in a dictionary, in the form:
        # tags = {journal : [[loc_subtitle], [loc_content]]}

        locs = {'altaveu':  [['h2', 'class', "c-mainarticle__subtitle"],
                            ['div', 'class', "c-mainarticle__body"]],

                'periodic': [['h2', 'class', "noticia-header__subtitle"],
                            ['div', 'class', "noticia-main__content"]],

                'ara':      [['h2', 'class', "subtitle"],
                            ['div', 'class', "ara-body"]],

                'bondia':   [[], ['div', 'property',
                                re.compile(".*content:encoded")]],

                'diari':    [[],
                            ['div', 'class', "c-detail__body"]],

                'forum':    [[],
                            ['div', 'class', "entry-the-content"]]}

        subtitle = ""
        content = ""

        # Subtitle:
        if locs[journal][0]:
            if soup.find(locs[journal][0][0], attrs={locs[journal][0][1]: locs[journal][0][2]}):
                subtitle = soup.find(locs[journal][0][0], attrs={locs[journal][0][1]: locs[journal][0][2]}).text

        # Content:
        if journal == "altaveu" and soup.find('div', class_="c-mainarticle__opening"):
            # In l'Altaveu, we have to first find the opening in case there's one, as that is part of the content of the
            # article
            opening = soup.find('div', class_="c-mainarticle__opening").text
            content = opening + soup.find(locs[journal][1][0],
                                        attrs={locs[journal][1][1]: locs[journal][1][2]}).text.strip()
        elif journal == "diari":
            paragraphs = soup.find('div', class_="c-detail__body").find_all('p')
            content = '\n'.join([par.text for par in paragraphs])
        elif soup.find(locs[journal][1][0], attrs={locs[journal][1][1]: locs[journal][1][2]}):
            content = soup.find(locs[journal][1][0], attrs={locs[journal][1][1]: locs[journal][1][2]}).text.strip()

        return subtitle, content

    # -- Comments ------------------------
    def get_comment_attributes(self, journal, comment):
        # For each comment, we look for the desired attributes and return them as a list

        # We define the date_formats we'll have to pass as arguments to the string_to_datetime(...) function
        date_format = {'altaveu': "Fa x",
                    'diari': "(%d/%m/%y %H:%M)",
                    'bondia': "%Y-%m-%dT%H:%M:%S"}

        if journal == "altaveu":

            comment_id = int(comment.find(
                'div', class_="comment_buttons").find('a', class_="valuation up like")["data-comment-vote"])
            author  = comment.find('div', class_="comment_info").strong.string
            og_date_time = comment.find('div', class_="comment_info").small.string
            # We pass formatted=False because the date cannot be parsed with strptime(..)
            # We pass multiple_formats=False because there are no multiple date formats to test
            date_time = utils.string_to_datetime(og_date_time, date_format[journal], formatted=False, multiple_formats=False)
            # We use .strip() to avoid unnecessary spaces at the beggining and end of the string
            content = comment.find('div', class_="comment_text").string.strip()
            in_answer_to = self.get_parent_id(journal, comment)
            likes = int(comment.find('div', class_="comment_buttons").find('a', class_="valuation up like").string)
            dislikes = int(comment.find('div', class_="comment_buttons").find('a', class_="valuation down dislike").string)

        elif journal == "diari":

            comment_id = int(comment.find('div', class_="comment").p['id'].split('-')[1])
            author = comment.find('p', class_="author").strong.string
            og_date_time = comment.find('p', class_="author").em.string
            # We pass formatted=True because the date can be parsed with strptime(..)
            # We pass multiple_formats=False because there are no multiple date formats to test
            date_time = utils.string_to_datetime(og_date_time, date_format[journal], formatted=True, multiple_formats=False)
            # In this case, the content can also have the parent comment in it. Because we do not want this, we use
            # .split('\n') and we choose the last element of the list to only obtain the current comment's content
            content = comment.find('div', class_="comment").p.span.text.strip().split('\n')
            content = content[len(content) - 1].strip()
            in_answer_to = self.get_parent_id(journal, comment)
            # We leave likes and dislikes as blank because these attributes do not exist in this journal
            likes = ""
            dislikes = ""

        elif journal == "bondia":

            comment_id = int(comment['about'].split('/')[2].split('#')[0])
            author = comment.find('span', class_="username").string
            og_date_time = comment.find('span', attrs={'property': "dc:date dc:created"})['content'].split('+')[0]
            # We pass formatted=True because the date can be parsed with strptime(..)
            # We pass multiple_formats=False because there are no multiple date formats to test
            date_time = utils.string_to_datetime(og_date_time, date_format[journal], formatted=True, multiple_formats=False)
            content = comment.find('div', attrs={'property': "content:encoded"}).text.strip()
            in_answer_to = self.get_parent_id(journal, comment)
            # We leave likes and dislikes as blank because these attributes do not exist in this journal
            likes = ""
            dislikes = ""

        return [comment_id, author, og_date_time, date_time, content, in_answer_to, likes, dislikes]
    
    def get_parent_id(self, journal, comment):
        # For each comment, this function will determine if it's a child comment (in answer to another comment)
        # and return the parent comment's ID. In case it isn't, we'll return ""

        if journal == "altaveu":

            parent_element = comment.parent

            # The comment is a child comment if the parent_element['class'] is "children"
            if parent_element['class'] == "children":
                parent_comment = parent_element.parent
                return int(parent_comment.find(
                    'div', class_="comment_buttons").find('a', class_="valuation up like")['data-comment-vote'])
            else:
                return ""

        if journal == "diari":

            # The comment is a child comment if it has a tag <a class="ancla-referencia">
            if comment.find_all('a', class_="ancla_referencia"):
                return int(comment.find('a', class_="ancla_referencia")['onmouseover'].split('(')[1].split(',')[0])
            else:
                return ""

        if journal == "bondia":

            parent_element = comment.parent

            # The comment is a child comment if the parent_element['class'] starts with 'indented' (first element on list)
            if parent_element['class'][0] == 'indented':
                return int(comment.find(
                    'span', attrs={'resource': re.compile("/comment.*")})['resource'].split('/')[2].split('#')[0])
            else:
                return ""
