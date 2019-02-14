class TradeException(Exception):
    """
        Distinguishes runtime logical errors (such as no data for what you
        queried) from programmatic errors (such as Oliver accessing a hash
        with the wrong type of key).
        
        TradeExcepts should be caught by the program and displayed in the
        most user friendly way possible.
    """
    pass