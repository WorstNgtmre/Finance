import json
import yfinance as yf
from newsapi import NewsApiClient
import google.generativeai as genai


## VALUES
stock1 = "AAPL"

with open(r"C:\Users\rodri\Documentos\Finance\claves.json","r") as k:
    claves = json.load(k)
genai.configure(api_key=claves["gemini"])

def get_stock_data(ticker: str):
    
    ## Fetches the latest stock data for a given ticker symbol.
    
    try:

        stock = yf.Ticker(ticker)
       
        # Get the current price
        current_price = stock.info.get('currentPrice', 'N/A')
        print(f"\nCurrent Price: {current_price}\n")
        
        return stock.info

    except Exception as e:
        print(f"Could not fetch data for {ticker}. Error: {e}")

def get_stock_history(ticker: str):

    # Get historical market data for the last 5 days
    try:
        
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
       
        print(f"--- Recent Data for {ticker} ---")
        print(hist)

    except Exception as e:
        print(f"Could not get data from {ticker}. Error:{e}")

def analyse_stock_data(data: dict):
    try:
        analist_recomendation = data.get("recommendationKey")
        current_price = data.get("currentPrice")
        fifty_day_average = data.get('fiftyDayAverage')
        volume = data.get('volume')
        average_volume_10_days = data.get('averageVolume10days')


    except Exception as e:
        print(f"Could not analyse data. Error: {e}")


"""


def get_financial_news(query):
    
    ### Get news

    try:
        # Get the top headlines
        # We search for the query, in English, sorted by relevance
        top_headlines = newsapi.get_everything(q=query,
                                               language='en',
                                               sort_by='publishedAt', ## GET MOST RECENT NEWS
                                               page_size=5) # Get the 5 most relevant articles


        print(f"--- Recent News for '{query}' ---")
        if top_headlines['totalResults'] > 0:
            for article in top_headlines['articles']:
                print(f"Title: {article['title']}" + f" Date: {article['publishedAt']}")
                ## print(f"Title: {article['publishedAt']}")
                print(f"Source: {article['source']['name']}")
                print("-" * 20)
        else:
            print("No news articles found.")
       
    except Exception as e:
        print(f"Could not fetch news. Error: {e}")



"""