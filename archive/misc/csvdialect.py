import csv


class CSVDialect(csv.Dialect):
    """
    Defines the TDCSVDialect class for fine-tuning CSV parsing.
    
    Python's CSV parser uses an Excel dialect for CSV parsing which
    seems to introduce some needless overhead parsing our simpler,
    standard format.
    
    Providing the correct defaults trims away a little inefficiency,
    but it may also protect us against any opinionated future
    changes to the python defaults.
    
    In particular, the current approach causes the CSV parser to
    produce quoted strings with their quotes intact:
        
        csv.reader("'hello'")
            -> "'hello'"
        csv.reader("'hello'", dialect=CSVDialect)
            -> "hello"
    
    Use:
        
        import csv
        from tradedangerous.misc.csvdialect import CSVDialect
        
        old_style = csv.reader(open("data/System.csv", encoding="utf-8"))
        new_style = csv.reader(open("data/System.csv", encoding="utf-8"),
                               dialect=CSVDialect)
        
        print("headers:")
        print("- old:", next(old_style))
        print("- new:", next(new_style))  # no difference
        
        for i, (old, new) in enumerate(zip(old_style, new_style)):
            print(f"{i}: ids={old[0]},{new[0]}; names={old[1]},{new[1]}")
            if i >= 5:
                break
    """
    # comma separator, not tab - it's what the 'c' stands for, damnit Excel.
    delimiter = ","
    # single-quote for non-numeric values
    quotechar = "'"
    # The only escape we support is '' within a quoted string for a literal single-quote
    # ... they term that ... *drum roll* double quote.
    escapechar = None
    doublequote = True  # ... I'm not making this up
    # Unix-style line endings, no old-mac LFCR and no old-dos CRLF please.
    lineterminator = "\n"
    # No whitespace chasing
    skipinitialspace = False
    # We actually expect all non-numerics to be quoted, such as the empty string,
    # but we're happy to tolerate less. Also, if we use the slightly more aggressive
    # quoting, it requires floats to be quoted ... which seems insane.
    quoting = csv.QUOTE_MINIMAL
