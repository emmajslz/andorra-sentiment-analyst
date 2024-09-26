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

    elif what == 'no_results':
        print("----------------------------------------------------------------------------------")
        print(f"The search yielded no results.")

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


