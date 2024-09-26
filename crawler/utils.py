from datetime import date, datetime, timedelta, time
from dateutil.relativedelta import relativedelta

def prints(what,
           term=None,
           journal=None,
           len_comments=None,
           date_article=None,
           title=None,
           new_article=False,
           date_init=None,
           date_end=None,
           search_terms=None):
    
    '''
    Function to print status updates to the standard output.
    '''

    names = {'altaveu': "L'Altaveu",
            'periodic': "Periòdic d'Andorra",
            'ara': "Ara Andorra",
            'bondia': "Bondia.ad",
            'diari': "Diari d'Andorra",
            'forum': "fòrum.ad",
            'ser': "Cadena Ser Andorra"}
    
    if what == 'mode':
        print("----------------------------------------------------------------------------------")
        print(f"Searching articles with the following search terms: {search_terms}")
        print("Searching articles between",
            date_init.strftime("%Y-%m-%d - %H:%M"),
            "and",
            date_end.strftime("%Y-%m-%d - %H:%M"))

    elif what == 'searching':
        print("----------------------------------------------------------------------------------")
        print("Searching at", names[journal])

    elif what == 'term':
        print(f"--> SEARCHING TERM {term} ...")

    elif what == 'comments':
        if new_article:
            if len_comments == 1:
                print(len_comments, "comment")
            elif len_comments > 1:
                print(len_comments, "comments")

    elif what == 'article':
        print("    -", date_article, "->", title)

    elif what == 'out_of_order':
        print(f":( Under maintenance. {names[journal]} is currently out of order.")
        print("--> Searching methods are currently being updated.")