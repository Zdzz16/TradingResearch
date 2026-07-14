import yfinance as yf

def get_data(ticker, start, end):
    """
    Downloads historical price data and cleans it up.
    ticker: e.g. "EURUSD=X"
    start/end: date strings like "2024-01-01"
    Returns a clean DataFrame with Open, High, Low, Close, Volume columns.
    """
    data = yf.download(ticker, start=start, end=end, auto_adjust=True)
    data.columns = data.columns.droplevel(1)
    return data