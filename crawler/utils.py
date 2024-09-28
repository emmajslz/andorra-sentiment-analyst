from datetime import date, datetime, timedelta, time
from dateutil.relativedelta import relativedelta

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
            print("----------------------------------------------------------------------------------")
            print(f"Searching articles with the following search terms: {search_terms}")
            print("Searching articles between",
                date_init.strftime("%Y-%m-%d - %H:%M"),
                "and",
                date_end.strftime("%Y-%m-%d - %H:%M"))

        case 'searching':
            print("----------------------------------------------------------------------------------")
            print("Searching at", names[journal])

        case 'term':
            print(f"--> SEARCHING TERM {term} ...")

        case 'comments':
            if len_comments == 1:
                print(f"       -{len_comments} comment")
            elif len_comments > 1:
                print(f"       -> {len_comments} comments")

        case 'article':
            print("    -", date_article, "->", title)

        case 'out_of_order':
            print(f":( Under maintenance. {names[journal]} is currently out of order.")
            print("--> Searching methods are currently being updated.")

        case 'no_results':
            print("----------------------------------------------------------------------------------")
            print(f"The search yielded no results.")

        case 'no_comments':
            print("----------------------------------------------------------------------------------")
            print(f"The articles had no comments.")

        case 'url':
            print(f"URL: {url} ...")

        case 'current_page':
            print(f"CURRENT PAGE -> {current_page}")

        case 'loading_more_results':
            print(f"LOADING MORE RESULTS...")


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


