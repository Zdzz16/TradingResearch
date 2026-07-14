def ma_crossover(data, window=20):
    """
    Flags days where Close crosses above its N-day moving average.
    Returns the full data with extra columns: MA, Signal, NewSignal.
    """
    data = data.copy()  # avoid modifying the original data by accident
    data[f"MA{window}"] = data["Close"].rolling(window=window).mean()
    data["Signal"] = data["Close"] > data[f"MA{window}"]
    prev_signal = data["Signal"].shift(1, fill_value=False)
    data["NewSignal"] = data["Signal"] & (~prev_signal)
    return data