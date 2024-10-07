#!/bin/sh

input_path="data/scrapes/$1/"

# python main_crawler.py $input_path -i $2 > $input_path$1.log 2>&1 &
python main_crawler.py $input_path -i $2
