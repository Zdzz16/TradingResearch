from core.journal import add_trade, view_journal

# Example: logging a trade you just took
add_trade(
    pair="EURUSD",
    direction="long",
    entry_price=1.0850,
    stop_loss=1.0800,
    take_profit=1.0950,
    reason="MA20 crossover + bounce off support",
    notes="First real journal entry, testing the system"
)

view_journal()