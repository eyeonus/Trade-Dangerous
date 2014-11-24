import tkinter as tk
import tkinter.messagebox as mbox
import tkinter.ttk as ttk
import sqlite3
import re
from pathlib import Path

class Item(object):
    """ Describe a listed, tradeable item """

    def __init__(self, ID, catID, name, displayNo):
        self.ID, self.catID, self.name = ID, catID, name
        self.displayNo = displayNo


class UpdateGUI(tk.Canvas):
    """
        Implements a tk canvas which displays an editor
        for TradeDangerous Price Updates
    """

    def __init__(self, root, tdb, cmdenv):
        width = cmdenv.width or 512
        height = cmdenv.height or 640
        sticky = 1 if cmdenv.alwaysOnTop else 0

        super().__init__(root, borderwidth=0, width=width, height=height)
        root.geometry("{}x{}-0+0".format(
                    width+32, height
                ))

        self.root = root
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

        # Allow the window to be always-on-top
        root.wm_attributes("-topmost", sticky)

        self.bind_all("<MouseWheel>", self.onMouseWheel)
        self.vsb = tk.Scrollbar(root,
                            orient=tk.VERTICAL,
                            command=self.yview)
        self.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")

        self.frame = tk.Frame(self)
        self.frame.bind("<Configure>", self.onFrameConfigure)
        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)

        self.createWidgets()

        self.focusOn(0, 0)

        self.create_window((4,4), window=self.frame, anchor="nw", tags="self.frame")
        self.pack(fill=tk.BOTH, expand=True)



    def onFrameConfigure(self, event):
        """ Handle the <Configure> event for the frame """

        self.configure(scrollregion=self.bbox("all"))


    def onMouseWheel(self, event):
        """ Translate mouse wheel inputs to scroll bar motions """

        self.yview_scroll(int(-1 * (event.delta/120)), "units")


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


    def validate(self, item, row, value, pos):
        """ For checking the contents of a widget. TBD """

        return True


    def onShiftTab(self, itemName, pos, event):
        """ Process user pressing Shift+TAB """

        item, row, value = self.query(itemName, pos)
        if not self.validate(item, row, value, pos):
            return
        if pos > 0 or item.displayNo > 0:
            # Natural flow
            return

        self.root.bell()
        return "break"


    def onTab(self, itemName, pos, event):
        """ Process user pressing TAB """

        item, row, value = self.query(itemName, pos)
        if not self.validate(item, row, value, pos):
            return
        if pos + 1 < len(row):
            return
        if item.displayNo + 1 < len(self.itemDisplays):
            return
        self.root.bell()
        return "break"


    def onReturn(self, itemName, pos, event):
        """
            When the user hits <Return>, advance to
            the first cell on the next line, or if
            we are at the bottom of the list, beep.
        """
        
        item, row, value = self.query(itemName, pos)
        if not self.validate(item, row, value, pos):
            return
        # advance to the first entry on the next row
        newDisplayNo = item.displayNo + 1
        if newDisplayNo >= len(self.itemDisplays):
            self.root.bell()
            return "break"

        self.focusOn(newDisplayNo, 0)


    def onUp(self, itemName, pos, event):
        """ Handle the user pressing up, go up a row """

        item, row, value = self.query(itemName, pos)
        if not self.validate(item, row, value, pos):
            return
        # can we go up a line?
        if item.displayNo <= 0:
            self.root.bell()
            return "break"

        self.focusOn(item.displayNo - 1, pos)


    def onDown(self, itemName, pos, event):
        """ Handle the user pressing down, go down a row """

        item, row, value = self.query(itemName, pos)
        if not self.validate(item, row, value, pos):
            return
        # can we go up a line?
        newDisplayNo = item.displayNo + 1
        if newDisplayNo >= len(self.itemDisplays):
            self.root.bell()
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
        lab = tk.Label(self.frame, text=text)
        return self.addWidget(lab, sticky='W', padx=16)


    def addSection(self, text):
        widget = tk.Label(self.frame, text=text, fg='blue')
        widget.grid(row=self.rowNo, column=0, columnspan=5, sticky='W')
        self.endRow()
        return widget


    def addInput(self, item, defValue, row):
        pos = len(row)

        inputVal = tk.StringVar()
        inputVal.set(str(defValue))

        inputEl = tk.Entry(self.frame,
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
            lab = tk.Label(self.frame, text=text, fg='blue')
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
        self.root.title(station.name())

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
    root = tk.Tk()
    gui = UpdateGUI(root, tdb, cmdenv)
    gui.mainloop()
    if not gui.results:
        gui.getResults()
    with tmpPath.open("w") as fh:
        print(gui.results, file=fh)


if __name__ == "__main__":
    render(Path("data/TradeDangerous.db"), 374, Path("update.prices"))
    print("- Wrote to update.prices")

