import tkinter as tk
import tkinter.messagebox as mbox
import tkinter.ttk as ttk
import sqlite3
import re
from pathlib import Path

"""
This is a crude attempt at a GUI for updating trade prices.
It needs a lot of love to be less... Shitty.

TODO:
. Add a way to add a new line,
. Add a way to reorder lines,
. Add a Save button,
. Add pre-exit validation (and don't exit if there's a problem),

Thanks to Bryan Okler for solving the focus tracking issue:
http://stackoverflow.com/questions/27055936/python3-tk-scrollbar-and-focus

"""

class Item(object):
    """ Describe a listed, tradeable item """

    def __init__(self, ID, catID, name, displayNo):
        self.ID, self.catID, self.name = ID, catID, name
        self.displayNo = displayNo


class ScrollingCanvas(tk.Frame):
    """
        Tk.Canvas with scrollbar.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.canvas = canvas = tk.Canvas(self, borderwidth=0)
        canvas.grid(row=0, column=0)
        canvas.grid_rowconfigure(0, weight=1)
        canvas.grid_columnconfigure(0, weight=1)

        vsb = tk.Scrollbar(parent,
                    orient=tk.VERTICAL,
                    command=canvas.yview)
        vsb.grid(row=0, column=1)
        vsb.pack(side="right", fill=tk.BOTH, expand=False)

        canvas.configure(yscrollcommand=vsb.set)
        canvas.configure(yscrollincrement=4)

        self.interior = interior = tk.Frame(canvas)
        canvas.create_window(0, 0, window=interior, anchor="nw", tags="interior")
        canvas.bind("<Configure>", self.onConfigure)
        interior.rowconfigure(0, weight=1)
        interior.columnconfigure(0, weight=1)
        interior.columnconfigure(1, weight=1)
        interior.columnconfigure(2, weight=1)
        interior.columnconfigure(3, weight=1)
        interior.columnconfigure(4, weight=1)

        canvas.grid(row=0, column=0)
        canvas.pack(side="left", fill=tk.BOTH, expand=True)

        self.bind_all("<MouseWheel>", self.onMouseWheel)
        canvas.bind_all("<FocusIn>", self.scrollIntoView)

        self.pack(side="left", fill=tk.BOTH, expand=True)


    def onConfigure(self, event):
        """ Handle resizing """

        self.canvas.configure(scrollregion=self.interior.bbox("all"))


    def onMouseWheel(self, event):
        """ Translate mouse wheel inputs to scroll bar motions """

        self.canvas.yview_scroll(int(-1 * (event.delta/4)), "units")


    def scrollIntoView(self, event):
        """ Scroll so that a given widget is in focus """

        canvas = self.canvas
        widget_top = event.widget.winfo_y()
        widget_bottom = widget_top + event.widget.winfo_height()
        canvas_top = canvas.canvasy(0)
        canvas_bottom = canvas_top + canvas.winfo_height()

        if widget_bottom >= canvas_bottom:
            delta = int(canvas_bottom - widget_bottom)
            canvas.yview_scroll(-delta, "units")
        elif widget_top < canvas_top:
            delta = int(widget_top - canvas_top)
            canvas.yview_scroll(delta, "units")


class UpdateGUI(ScrollingCanvas):
    """
        Implements a tk canvas which displays an editor
        for TradeDangerous Price Updates
    """

    def __init__(self, parent, tdb, cmdenv):
        super().__init__(parent)

        width = cmdenv.width or 600
        height = cmdenv.height or 640
        sticky = 1 if cmdenv.alwaysOnTop else 0

        self.tdb = tdb
        self.cmdenv = cmdenv

        self.rowNo = 0
        self.colNo = 0
        self.items = {}
        self.categories = []
        self.itemList = []
        self.itemDisplays = []
        self.results = None
        self.headings = []

        self.createWidgets()

        self.focusOn(0, 0)

        parent.geometry("{}x{}-0+0".format(
                    width+16, height
                ))

        # Allow the window to be always-on-top
        parent.wm_attributes("-topmost", sticky)


    def focusOn(self, displayNo, pos):
        """ Set focus to a widget and select the text in it """

        row = self.itemDisplays[displayNo]
        widget = row[pos][0]
        widget.focus_set()
        widget.selection_range(0, tk.END)


    def query(self, itemName, pos):
        """ Find the cell for a given item name and a position """

        item = self.items[itemName]
        row = self.itemDisplays[item.displayNo]
        return item, row, row[pos][1].get()


    def setValue(self, row, pos, value):
        row[pos][1].set(value)


    def validate(self, item, row, value, pos):
        """ For checking the contents of a widget. TBD """

        return True


    def onShiftTab(self, itemName, pos, event):
        """ Process user pressing Shift+TAB """

        item, row, value = self.query(itemName, pos)
        if not self.validate(item, row, value, pos):
            return "break"
        if pos > 0 or item.displayNo > 0:
            # Natural flow
            return

        self.parent.bell()
        return "break"


    def onTab(self, itemName, pos, event):
        """ Process user pressing TAB """

        item, row, value = self.query(itemName, pos)
        if not self.validate(item, row, value, pos):
            return "break"
        if pos + 1 < len(row):
            return
        if item.displayNo + 1 < len(self.itemDisplays):
            return
        self.parent.bell()
        return "break"


    def onReturn(self, itemName, pos, event):
        """
            When the user hits <Return>, advance to
            the first cell on the next line, or if
            we are at the bottom of the list, beep.
        """
        
        item, row, value = self.query(itemName, pos)
        if not self.validate(item, row, value, pos):
            return "break"
        # advance to the first entry on the next row
        newDisplayNo = item.displayNo + 1
        if newDisplayNo >= len(self.itemDisplays):
            self.parent.bell()
            return "break"

        self.focusOn(newDisplayNo, 0)


    def onUp(self, itemName, pos, event):
        """ Handle the user pressing up, go up a row """

        item, row, value = self.query(itemName, pos)
        if not self.validate(item, row, value, pos):
            return "break"
        # can we go up a line?
        if item.displayNo <= 0:
            self.parent.bell()
            return "break"

        self.focusOn(item.displayNo - 1, pos)


    def onDown(self, itemName, pos, event):
        """ Handle the user pressing down, go down a row """

        item, row, value = self.query(itemName, pos)
        if not self.validate(item, row, value, pos):
            return "break"
        # can we go up a line?
        newDisplayNo = item.displayNo + 1
        if newDisplayNo >= len(self.itemDisplays):
            self.parent.bell()
            return "break"

        self.focusOn(newDisplayNo, pos)


    def endRow(self):
        self.rowNo += 1
        self.colNo = 0


    def addWidget(self, widget, **kwargs):
        widget.grid(row=self.rowNo, column=self.colNo, **kwargs)
        self.colNo += 1
        return widget


    def addLabel(self, text):
        lab = tk.Label(self.interior, text=text)
        return self.addWidget(lab, sticky='W', padx=16)


    def addSection(self, text):
        widget = tk.Label(self.interior, text=text, fg='blue')
        widget.grid(row=self.rowNo, column=0, columnspan=5, sticky='W')
        self.endRow()
        return widget


    def addInput(self, item, defValue, row):
        pos = len(row)

        inputVal = tk.StringVar()
        inputVal.set(str(defValue))

        inputEl = tk.Entry(self.interior,
                width=10,
                justify=tk.RIGHT,
                textvariable=inputVal)
        inputEl.bind('<Shift-Key-Tab>',
                lambda evt: self.onShiftTab(item, pos, evt))
        inputEl.bind('<Key-Tab>',
                lambda evt: self.onTab(item, pos, evt))
        inputEl.bind('<Key-Return>',
                lambda evt: self.onReturn(item, pos, evt))
        inputEl.bind('<Key-Down>',
                lambda evt: self.onDown(item, pos, evt))
        inputEl.bind('<Key-Up>',
                lambda evt: self.onUp(item, pos, evt))
        self.addWidget(inputEl, sticky='E')
        row.append((inputEl, inputVal))


    def addHeadings(self):
        def addHeading(text):
            self.headings.append(text)
            lab = tk.Label(self.interior, text=text, fg='blue')
            self.addWidget(lab, sticky='W', padx=16)
        addHeading("Item")
        addHeading("Paying")
        addHeading("Asking")
        addHeading("Demand")
        addHeading("Supply")
        self.endRow()


    def addItemRow(self, ID, catID, itemName, paying, asking, demand, stock):
        row = []

        displayNo = len(self.itemDisplays)
        item = Item(ID, catID, itemName, displayNo)
        self.items[itemName] = item
        self.itemList.append(item)

        self.addLabel(itemName.upper())
        self.addInput(itemName, paying, row)
        self.addInput(itemName, asking, row)
        self.addInput(itemName, demand, row)
        self.addInput(itemName, stock, row)

        self.itemDisplays.append(row)

        self.endRow()


    def createWidgets(self):
        self.addHeadings()

        tdb, cmdenv = self.tdb, self.cmdenv
        station = cmdenv.startStation
        self.parent.title(station.name())

        db = tdb.getDB()
        db.row_factory = sqlite3.Row
        cur = db.cursor()

        self.categories = self.tdb.categoryByID

        # if the user specified "--all", force listing of all items
        siJoin = "INNER" if not cmdenv.all else "LEFT OUTER"
        stmt = """
                SELECT  item.category_id AS catID,
                        item.item_id AS ID,
                        item.name AS name,
                        IFNULL(sb.price, '') AS paying,
                        IFNULL(ss.price, '') AS asking,
                        IFNULL(sb.units, 0) AS demandUnits,
                        IFNULL(sb.level, 0) AS demandLevel,
                        IFNULL(ss.units, 0) AS stockUnits,
                        IFNULL(ss.level, 0) AS stockLevel
                  FROM  (
                            Category AS cat
                                INNER JOIN Item item
                                    USING (category_id)
                        ) {siJoin} JOIN
                            StationItem si
                                ON (si.item_id = item.item_id
                                    AND si.station_id = ?)
                            LEFT OUTER JOIN StationBuying sb
                                USING (station_id, item_id)
                            LEFT OUTER JOIN StationSelling ss
                                USING (station_id, item_id)
                 ORDER  BY cat.name, si.ui_order, item.name
                """.format(
                            siJoin=siJoin
                    )
        cur.execute(stmt, [station.ID])

        def describeSupply(units, level):
            if not level:
                return ""
            if units == -1 and level == -1:
                return "?"
            if level == -1:
                return "{}?".format(units)
            return "{}{}".format(units, ['L', 'M', 'H'][level-1])

        lastCat = None
        for row in cur:
            cat = row["catID"]
            if cat != lastCat:
                self.addSection(self.categories[cat].name())
                lastCat = cat
            itemName = row["name"]
            paying, asking = row["paying"], row["asking"]
            demand = describeSupply(row["demandUnits"], row["demandLevel"])
            supply = describeSupply(row["stockUnits"], row["stockLevel"])
            self.addItemRow(row["ID"], cat, itemName, paying, asking, demand, supply)


    def getResults(self):
        lastCat = None

        txt = (
                "# Generated by TDGUI\n"
                "\n"
                "@ {stn}\n".format(
                    stn=self.cmdenv.startStation.name(),
                )
            )
        for item in self.itemList:
            if item.catID != lastCat:
                lastCat = item.catID
                txt += (" + {}\n".format(self.categories[lastCat].dbname))

            row = self.itemDisplays[item.displayNo]
            rowvals = [ val[1].get() for val in row ]

            itemName = item.name
            paying = int(rowvals[0] or 0)
            asking = int(rowvals[1] or 0)
            demand = rowvals[2]
            stock  = rowvals[3]

            if not paying and not asking:
                continue

            if paying and not demand:
                demand = "?"

            if asking == 0:
                stock = "-"
            elif not stock:
                stock = "?"

            if re.match('^\d+$', stock):
                if int(stock) != 0:
                    stock += '?'

            txt += ("     {item:<30s} "
                    "{paying:>10} "
                    "{asking:>10} "
                    "{demand:>10} "
                    "{stock:>10}\n".format(
                        item=itemName,
                        paying=paying,
                        asking=asking,
                        demand=demand,
                        stock=stock
                        ))
        self.results = txt


def render(tdb, cmdenv, tmpPath):
    parent = tk.Tk()
    gui = UpdateGUI(parent, tdb, cmdenv)
    gui.mainloop()
    if not gui.results:
        gui.getResults()
    with tmpPath.open("w") as fh:
        print(gui.results, file=fh)

