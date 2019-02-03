from __future__ import absolute_import, with_statement, print_function, division, unicode_literals
import itertools

class ColumnFormat(object):
    """
        Describes formatting of a column to be populated with data.

        Member Functions:

            str()
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
            print(*[col.str() for col in cols])
            for row in rows:
                print(*[col.format(row) for col in cols])
        Produces:
            Name   [ Dist]
            Bob    [ 1.30]
            John   [23.00]

    """
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
            ):
        self.name = name
        self.align = align
        self.width = max(int(width), len(name))
        self.qualifier = qualifier or ''
        self.key = key
        self.pre = pre or ''
        self.post = post or ''
        self.pred = pred


    def str(self):
        return '{pre}{title:{align}{width}}{post}'.format(
                title=self.name,
                align=self.align, width=self.width,
                pre=self.pre, post=self.post,
            )


    def format(self, value):
        if self.pred(value):
            return '{pre}{value:{align}{width}{qual}}{post}'.format(
                    value=self.key(value),
                    align=self.align, width=self.width,
                    qual=self.qualifier,
                    pre=self.pre, post=self.post,
                )
        else:
            return '{pre}{value:{align}{width}}{post}'.format(
                value="",
                align=self.align, width=self.width,
                pre=self.pre, post=self.post,
            )


class RowFormat(object):
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

            str()
                Returns a list of all the column headings

            format(rowData):
                Returns a list of applying rowData to all
                of the columns

    """
    def __init__(self, prefix=None):
        self.columns = []
        self.prefix = prefix or ""


    def addColumn(self, *args, **kwargs):
        self.append(ColumnFormat(*args, **kwargs))


    def append(self, column, after=None):
        columns = self.columns
        if after:
            for idx, col in enumerate(columns, 1):
                if col.name == after:
                    columns.insert(idx, column)
                    return self
        columns.append(column)
        return self


    def insert(self, pos, column):
        if column is not None:
            self.columns.insert(pos, column)


    def str(self):
        return self.prefix + ' '.join(col.str() for col in self.columns)


    def heading(self):
        headline = self.str()
        return headline, '-' * len(headline)


    def format(self, rowData):
        return self.prefix + ' '.join(col.format(rowData) for col in self.columns)

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
        rowTitle = rowFmt.str()
        print(rowTitle)
        print('-' * len(rowTitle))
        for row in rows:
            print(rowFmt.format(row))

    print("Simple usage:")
    present()

    print()
    print("Adding age ColumnFormat:")

    rowFmt.append(after='Name', col=ColumnFormat("Age", '>', 3, pre='|', post='|', key=lambda row: row['age']))
    present()