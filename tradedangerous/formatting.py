"""
Provides a library of mechanisms for formatting output text to ensure consistency across
TradeDangerous and plugin tools,
"""
from __future__ import annotations

import itertools
import typing

if typing.TYPE_CHECKING:
    from typing import Any, Callable, Optional  # noqa


class ColumnFormat:
    """
        Describes formatting of a column to be populated with data.
        
        Member Functions:
            
            text()
                Applies all formatting (except qualifier) to the name to
                produce a correctly sized title field.
            
            format(value)
                Applies all formatting to key(value) to produce a correctly
                sized value field.
        
        Attributes:
            name
                Heading for column to display when calling title()
                e.g. name="Station Name"
            align
                Alignment formatter for .format
                e.g. align='<' or align='>' or align=''
            width
                Numeric value for the width of the column
                e.g. width=5
            qualifier
                Final part of the print format,
                e.g. qualifier='.2f' or qualifier='n'
            pre
                Prefix to the column
            post
                Postfix to the column
            key
                Retrieve the printable name of the item
            pred
                Predicate: Return False to leave this column blank
        
        e.g.
            cols = [
                ColumnFormat("Name", "<", "5", '', key=lambda item:item['name']),
                ColumnFormat("Dist", ">",  "6", ".2f",
                        pre='[',
                        post=']'
                        key=lambda item:item['dist']),
            ]
            rows = [ {'name':'Bob', 'dist':1.5}, {'name':'John', 'dist':23}]
            # print titles
            print(*[col.text() for col in cols])
            for row in rows:
                print(*[col.format(row) for col in cols])
        Produces:
            Name   [ Dist]
            Bob    [ 1.30]
            John   [23.00]
    
    """
    name:       str                 # name of the column
    align:      str                 # format's alignment specifier
    width:      int                 # width specifier
    qualifier:  Optional[str]       # optional format type specifier e.g. '.2f', 's', 'n'
    pre:        Optional[str]       # prefix to the column
    post:       Optional[str]       # postfix to the column
    key:        Callable            # function to retrieve the printable name of the item
    pred:       Callable            # predicate: return False to leave this column blank
    
    def __init__(
            self,
            name,
            align,
            width,
            qualifier=None,
            pre=None,
            post=None,
            key=lambda item: item,
            pred=lambda item: True,
            ) -> None:
        self.name = name
        self.align = align
        self.width = max(int(width), len(name))
        self.qualifier = qualifier or ''
        self.key = key
        self.pre = pre or ''
        self.post = post or ''
        self.pred = pred
    
    def __str__(self) -> str:
        return f'{self.pre}{self.name:{self.align}{self.width}}{self.post}'
    text = __str__
    
    def format(self, value: str) -> str:
        """ Returns the string formatted with a specific value"""
        if not self.pred(value):
            return f'{self.pre}{"":{self.align}{self.width}}{self.post}'
        return f'{self.pre}{self.key(value):{self.align}{self.width}{self.qualifier}}{self.post}'

class RowFormat:
    """
        Describes an ordered collection of ColumnFormats
        for dispay data from rows, such that calling
          rowFmt.format(rowData)
        will return the result of formatting each column
        against rowData.
        
        Member Functions
            
            append(col, [after])
                Adds a ColumnFormatter to the end of the row
                If 'after' is specified, tries to insert
                the new column immediately after the first
                column who's name matches after.
            
            insert(pos, newCol)
                Inserts a ColumnFormatter at position pos in the list
            
            text()
                Returns a list of all the column headings
            
            format(rowData):
                Returns a list of applying rowData to all
                of the columns
    
    """
    columns:        list[ColumnFormat]
    prefix:         str
    
    def __init__(self, prefix: Optional[str] = None):
        self.columns = []
        self.prefix = prefix or ""
    
    def addColumn(self, *args, **kwargs) -> None:
        self.append(ColumnFormat(*args, **kwargs))
    
    def append(self, column: ColumnFormat, after: Optional[str] = None) -> 'RowFormat':
        columns = self.columns
        if after:
            for idx, col in enumerate(columns, 1):
                if col.name == after:
                    columns.insert(idx, column)
                    return self
        columns.append(column)
        return self
    
    def insert(self, pos: int, column: Optional[ColumnFormat]) -> None:
        if column is not None:
            self.columns.insert(pos, column)
    
    def __str__(self) -> str:
        return f"{self.prefix} {' '.join(str(col) for col in self.columns)}"
    
    text = __str__  # alias
    
    def heading(self) -> tuple[str, str]:
        """ Returns a title and the appropriate underline for that text. """
        headline = f"{self}"
        return headline, '-' * len(headline)
    
    def format(self, row_data: Optional[Any]) -> str:
        return f"{self.prefix} {' '.join(col.format(row_data) for col in self.columns)}"

def max_len(iterable, key=lambda item: item):
    iterable, readahead = itertools.tee(iter(iterable))
    try:
        next(readahead)
    except StopIteration:
        return 0
    return max(len(key(item)) for item in iterable)


if __name__ == '__main__':
    rowFmt = RowFormat(). \
                append(ColumnFormat("Name", '<', '8', key=lambda row: row['name'])). \
                append(ColumnFormat("Dist", '>', '6', '.2f', pre='[', post=']', key=lambda row: row['dist']))
    
    rows = [
        { 'name': 'Bob', 'dist': 6.2, 'age': 30 },
        { 'name': 'Dave', 'dist': 42, 'age': 18 },
    ]
    
    def present():
        rowTitle = rowFmt.text()
        print(rowTitle)
        print('-' * len(rowTitle))
        for row in rows:
            print(rowFmt.format(row))
    
    print("Simple usage:")
    present()
    
    # print()
    # print("Adding age ColumnFormat:")
    # rowFmt.append(after='Name', col=ColumnFormat("Age", '>', 3, pre='|', post='|', key=lambda row: row['age']))
    # present()
