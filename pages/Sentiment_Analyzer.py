import streamlit as st

import re
import os
import shutil
import csv
from datetime import date, datetime, time
import time as tme
from dateutil.relativedelta import relativedelta

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from transformers import BertTokenizer, BertForSequenceClassification
import torch

import main_crawler
import analyze
from crawler import utils

from config import REPO_PATH

class AllStoredSearches:

    def __init__(self):
        self.scrapes_path = os.path.join(REPO_PATH, "data", "scrapes")

    def list_search_dirs(self):

        try:
            search_dirnames = []
            search_directories_df = []
            for dir in os.listdir(self.scrapes_path):
                dirpath = os.path.join(self.scrapes_path, dir)
                if os.path.isdir(dirpath):

                    articles_filepath, comments_filepath = self.get_csv_filepaths(dirpath)
                    articles_count = self.count_lines(articles_filepath)
                    comments_count = self.count_lines(comments_filepath)

                    search_date = dir.split('-')[1]
                    search_directories_df.append({
                        'dirname': dir,
                        'datetime': datetime.strptime(search_date, "%Y%m%d%H%M%S"),
                        'nb_articles': articles_count,
                        'nb_comments': comments_count,
                        'dirpath': dirpath
                    })

                    if articles_count > 0:
                        search_dirnames.append(dir)

            search_directories_df = pd.DataFrame(search_directories_df)

            return search_dirnames, search_directories_df
        
        except Exception as e:
            st.error(f"Error accessing directories: {e}")
            return []
    
    def get_csv_filepaths(self, dirpath: str):

        articles_filepath = os.path.join(dirpath, "articles.csv")
        comments_filepath = os.path.join(dirpath, "comments.csv")

        if not os.path.isfile(articles_filepath):
            articles_filepath = None
        if not os.path.isfile(comments_filepath):
            comments_filepath = None

        return articles_filepath, comments_filepath
        
    def count_lines(self, filepath):
        
        if filepath is None:
            return 0
        
        with open(filepath, 'r', encoding='utf-8') as file:
            # Skip the header
            next(file)  # Skip the header line
            line_count = sum(1 for line in file if line.strip())  # Count only non-empty lines
        return line_count

    def display_available_datasets(self, search_directories_df):

        st.write("These are the available datasets:")

        # Define the custom CSS styles for the table
        table_style = """
        <style>
        table {
            width: 100%;
            border-collapse: collapse;
            font-family: 'Roboto', sans-serif;
            font-size: 12px;
        }
        th {
            background-color: #f0f2f6;
            color: #333;
            text-align: left;
            padding: 12px;
            border-bottom: 2px solid #ddd;
        }
        td {
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }
        tr:hover {background-color: #f5f5f5;}
        a {
            color: #1f77b4;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        </style>
        """
        
        # Create an HTML table with clickable titles
        table_html = """
        <table>
        <tr>
            <th>Directory Name</th>
            <th>Search Date and Time</th>
            <th>Number of Articles</th>
            <th>Number of Comments</th>
            <th>Delete the Directory</th>
        </tr>
        """

        for index, dir in search_directories_df.iterrows():

            # Add the row to the HTML table with the title linked and other columns
            table_html += f"""
            <tr>
                <td>{dir['dirname']}</td>
                <td>{dir['datetime']}</td>
                <td>{dir['nb_articles']}</td>
                <td>{dir['nb_comments']}</td>
                <td><button id={dir['dirname']} onclick="alert(\'You deleted {dir["dirname"]}?\')">Delete</button></td>
            </tr>
            """

        # Close the HTML table tag
        table_html += "</table>"

        # Combine the custom CSS with the table HTML
        full_html = table_style + table_html

        # Display the table
        height = len(search_directories_df) * 50
        st.components.v1.html(full_html, height=height, scrolling=True)

        st.write("These are the available datasets:")


class SelectedData:

    def __init__(self, search_directory_path: str):

        self.dirpath = search_directory_path

        self.articles_filepath = os.path.join(self.dirpath, "articles.csv")
        self.comments_filepath = os.path.join(self.dirpath, "comments.csv")

        self.articles, self.comments = self.get_dataframes()

        if self.articles is not None and self.comments is not None:
            self.articles, self.comments = self.preprocess_data(self.articles, self.comments)
        
    def get_dataframes(self):

        articles = None
        comments = None

        dtype_comments = {
            'comment_in_answer_to': 'str'
            # the other column types will be inferred
        }
        
        try:
            articles = pd.read_csv(self.articles_filepath, parse_dates=['datetime_added', 'datetime_article'])
            comments = pd.read_csv(self.comments_filepath, dtype=dtype_comments, parse_dates=['comment_datetime'])
        
        except:

            st.warning(f"The selected directory has no results stored.\nPlease select another one.")

        return articles, comments
    
    def preprocess_data(self, articles: pd.DataFrame, comments: pd.DataFrame):

        comments['search_term'] = comments.join(articles.set_index('id'), on='article_id', lsuffix='article')['search_term']

        return articles, comments

    def get_summary_stats(self):
        
        search_terms_article_count = self.articles['search_term'].value_counts()
        search_terms_comment_count = self.comments['search_term'].value_counts()

        search_term_counts = pd.merge(search_terms_article_count, search_terms_comment_count, on='search_term', how='outer').fillna(0)

        search_term_counts['count_articles'] = search_term_counts['count_x'].astype(int)
        search_term_counts['count_comments'] = search_term_counts['count_y'].astype(int)

        search_term_counts = search_term_counts.reset_index()[['search_term', 'count_articles', 'count_comments']]

        return search_term_counts[['search_term', 'count_articles', 'count_comments']]
    
    def display_summary(self):
        
        nb_articles = len(self.articles)
        nb_comments = len(self.comments)

        # search_term_counts = self.get_summary_stats()

        st.write(f"Dataset with {nb_articles} articles and {nb_comments} comments.")

    def display_articles(self):

        journals = {
            'altaveu': "L'altaveu",
            'bondia': "Bondia.ad",
            'diari': "Diari d'Andorra"
        }

        # Define the custom CSS styles for the table
        table_style = """
        <style>
        table {
            width: 100%;
            border-collapse: collapse;
            font-family: 'Roboto', sans-serif;
            font-size: 14px;
        }
        th {
            background-color: #f0f2f6;
            color: #333;
            text-align: left;
            padding: 12px;
            border-bottom: 2px solid #ddd;
        }
        td {
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }
        tr:hover {background-color: #f5f5f5;}
        a {
            color: #1f77b4;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        </style>
        """
        
        # Create an HTML table with clickable titles
        table_html = """
        <table>
        <tr>
            <th>Journal</th>
            <th>Date</th>
            <th>Search Term</th>
            <th>Article</th>
            <th>Number of comments</th>
        </tr>
        """

        # Add each row with the title linked
        for index, article in self.articles.iterrows():

            title = article['title']
            link = article['link']
            journal = journals[article['journal']]
            date = article['datetime_article']
            search_term = article['search_term']
            nb_comments = article['nb_of_comments']
            if nb_comments == 0:
                nb_comments = ""
            
            # Add the row to the HTML table with the title linked and other columns
            table_html += f"""
            <tr>
                <td>{journal}</td>
                <td>{date}</td>
                <td>{search_term}</td>
                <td>
                    <a href="{link}" target="_blank">{title}</a>
                </td>
                <td>{nb_comments}</td>
            </tr>
            """

        # Close the HTML table tag
        table_html += "</table>"

        # Combine the custom CSS with the table HTML
        full_html = table_style + table_html

        # Display the table
        st.components.v1.html(full_html, height=500, scrolling=True)


class Predict:

    def __init__(self, results_path: str, articles: pd.DataFrame, comments: pd.DataFrame):
        
        self.results_path = results_path

        self.model = BertForSequenceClassification.from_pretrained("./model")
        self.tokenizer = BertTokenizer.from_pretrained("./model")

        self.articles = articles
        self.comments = comments

        self.existing_predictions = self.get_existing_labels_dataset()

        self.comments = self.define_input_text(self.comments)

    def get_existing_labels_dataset(self):

        self.comments_labeled_filepath = f"{self.results_path}/comments_labeled.csv"
        return os.path.isfile(self.comments_labeled_filepath)

    def define_input_text(self, comments):

        comments['article_title'] = comments.join(self.articles.set_index('id'), on='article_id', lsuffix='comments')['title']
        comments['input_text'] = comments.apply(lambda row: f"[ARTICLE TITLE] {row['article_title']} [COMMENT] {row['comment_content']}", axis=1)
        
        return comments

    def predict_single_label(self, input_text):

        # Set the model to evaluation mode (necessary for inference)
        self.model.eval()

        # Tokenize the input text
        tokenized_input = self.tokenizer(input_text, return_tensors="pt", truncation=True, padding=True)

        # Make predictions
        with torch.no_grad():
            outputs = self.model(**tokenized_input)
            logits = outputs.logits
            predicted_label = torch.argmax(logits, dim=-1).item()  # Get the index of the max logit

        return predicted_label

    def add_predictions_to_comments(self, comments):
        
        labels = {
            0: 'positive',
            1: 'neutral',
            2: 'negative',
            3: 'very-negative'
        }

        progress_bar = st.progress(0)

        comments['predicted_label_code'] = np.nan
        comments['predicted_label'] = np.nan

        len_comments = len(comments)
        for i in range (len_comments):
            comments.loc[i,'predicted_label_code'] = self.predict_single_label(comments.loc[i,'input_text'])
            comments.loc[i,'predicted_label'] = labels[comments.loc[i,'predicted_label_code']]
            progress_bar.progress((i + 1) / len_comments)

        return comments
    
    def make_predictions(self):

        if not self.existing_predictions:
            # make predictions
            self.comments = self.add_predictions_to_comments(self.comments)
            try:
                self.comments.to_csv(self.comments_labeled_filepath, index_label="comment_id", sep=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                self.existing_predictions = True
            except:
                st.warning(f"Couldn't save file {self.comments_labeled_filepath}")
        else:
            # get predictions from existing file
            dtype_comments = {'comment_in_answer_to': 'str'}
            try:
                self.comments = pd.read_csv(self.comments_labeled_filepath, dtype=dtype_comments, parse_dates=['comment_datetime'])
            except:
                st.warning(f"The selected directory has no results stored.\nPlease select another one.")

    def get_label_valuecounts(self):

        all_labels = ['positive', 'neutral', 'negative', 'very-negative']
        label_valuecounts = self.comments.groupby('predicted_label').size().reindex(all_labels, fill_value=0).rename('Frequency')

        return label_valuecounts

    def display_overall_analysis(self):

        label_valuecounts = self.get_label_valuecounts()

        col1, col2= st.columns([2, 1])  # Create two columns for layout
        with col1:
            plt.figure(figsize=(7, 3.5))
            plt.bar(list(label_valuecounts.index), label_valuecounts, color=['#F3EFB2', '#E1D3A6', '#D1C177', '#C6B24A'])
            plt.title("Frequency of each sentiment label.")
            st.pyplot(plt)
        with col2:
            st.write("\n\n")
            st.dataframe(label_valuecounts)

def main():

    st.set_page_config(
        page_title='Sentiment Analysis',
        page_icon="🌐",
        layout='wide',
        initial_sidebar_state='auto' # hides the sidebar on small devices and shows it otherwise
    )

    st.markdown("# Perform Sentiment Analysis on a Saved Dataset.")

    stored_searches = AllStoredSearches()
    search_dirnames, search_directories_df = stored_searches.list_search_dirs()

    stored_searches.display_available_datasets(search_directories_df)

    if 'selected_button' in st.session_state:
        st.write(f"Last clicked button: {st.session_state.selected_button}")

    selected_directory = st.selectbox("Select the directory with the desired data (default is the latest search)", search_dirnames)
    search_directory_path = os.path.join(stored_searches.scrapes_path, selected_directory)

    search = SelectedData(search_directory_path)

    if search.articles is not None:
        
        search.display_summary()

        if 'show_articles' not in st.session_state:
            st.session_state.show_articles = False

        # Handle the button press and toggle state
        if st.button("Show/Hide articles"):
            st.session_state.show_articles = not st.session_state.show_articles  # Toggle the state

        # Conditionally display articles
        if st.session_state.show_articles:
            search.display_articles()

        if search.comments is not None:

            st.markdown("### Sentiment Analysis")
            predict = Predict(search_directory_path, search.articles, search.comments)

            if not predict.existing_predictions:
                st.write("There's no predictions for this dataset.")
                if st.button("Make predictions!"):
                    predict.make_predictions()
            else:
                predict.make_predictions()

            if predict.existing_predictions:
                predict.display_overall_analysis()

if __name__ == "__main__":
    main()