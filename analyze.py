from transformers import BertTokenizer, BertForSequenceClassification
import torch
import streamlit as st

import pandas as pd

class Process:

    def __init__(self, results_path: str):

        self.results_path = results_path
        self.comments_path = f"{results_path}comments.csv"
        self.articles_path = f"{results_path}articles.csv"

    def preprocess_data(self):

        dtype_comments = {
            'comment_in_answer_to': 'str'
            # the other column types will be inferred
        }
        
        articles = pd.read_csv(self.articles_path, parse_dates=['datetime_added', 'datetime_article'])
        comments = pd.read_csv(self.comments_path, dtype=dtype_comments, parse_dates=['comment_datetime'])

        comments['article_title'] = comments.join(articles.set_index('id'), on='article_id', lsuffix='comments')['title']
        comments['input_text'] = comments.apply(lambda row: f"[ARTICLE TITLE] {row['article_title']} [COMMENT] {row['comment_content']}", axis=1)
        
        return comments[['input_text']]
        

class Predict:

    def __init__(self, results_path: str):

        self.comments = Process(results_path).preprocess_data()

        self.model = BertForSequenceClassification.from_pretrained("./model")
        self.tokenizer = BertTokenizer.from_pretrained("./model")

    def predict_sentiment(self, input_text):

        # Set the model to evaluation mode (necessary for inference)
        self.model.eval()

        # Tokenize the input text
        inputs = self.tokenizer(input_text, padding=True, truncation=True, return_tensors="pt", max_length=128)

        # Make predictions
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            prediction = torch.argmax(logits, axis=1)

        return prediction

    def predict_all_comments(self):
        
        labels = {
            0: 'positive',
            1: 'neutral',
            2: 'negative',
            3: 'very-negative'
        }

        labels = []

        for comment in self.comments.values:
            prediction = self.predict_sentiment(comment)
            label = labels[prediction]
            st.write(label)
            labels.append(label)

        return labels
