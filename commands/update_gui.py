import tkinter as tk
import tkinter.messagebox as mbox
import tkinter.ttk as ttk
import sqlite3
from pathlib import Path

class Item(object):
    def __init__(self, ID, catID, name, displayNo):
        self.ID, self.catID, self.name = ID, catID, name
        self.displayNo = displayNo


class UpdateFrame(tk.Frame):
    def __init__(self, root, dbPath, stationID):
        tk.Frame.__init__(self, root)

        self.root = root
        self.style = ttk.Style()
        self.style.theme_use("default")

        self.canvas = tk.Canvas(root, borderwidth=0)
        self.canvas.bind_all("<MouseWheel>", self.onMouseWheel)
        self.frame = tk.Frame(self.canvas)
        self.vsb = tk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.create_window((4,4), window=self.frame, anchor="nw", tags="self.frame")

        self.frame.bind("<Configure>", self.onFrameConfigure)

        self.rowNo = 0
        self.colNo = 0
        self.items = {}
        self.categories = []
        self.itemList = []
        self.itemDisplays = []
        self.results = None
        self.headings = []

        self.createWidgets(dbPath, stationID)

        self.focusOn(0, 0)


    def onFrameConfigure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))


    def onMouseWheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta/120)), "units")


    def focusOn(self, displayNo, pos):
        row = self.itemDisplays[displayNo]
        widget = row[pos][0]
        widget.focus_set()
        widget.selection_range(0, tk.END)


    def query(self, itemName, pos):
        item = self.items[itemName]
        row = self.itemDisplays[item.displayNo]
        return item, row, row[pos][1].get()


    def validate(self, item, row, value, pos):
        return True


    def handleShiftTab(self, itemName, pos, event):
        item, row, value = self.query(itemName, pos)
        if not self.validate(item, row, value, pos):
            return
        if pos > 0 or item.displayNo > 0:
            # Natural flow
            return
        self.root.bell()
        return "break"


    def handleTab(self, itemName, pos, event):
        item, row, value = self.query(itemName, pos)
        if not self.validate(item, row, value, pos):
            return
        if pos + 1 < len(row):
            return
        if item.displayNo + 1 < len(self.itemDisplays):
            return
        self.root.bell()
        return "break"


    def handleReturn(self, itemName, pos, event):
        item, row, value = self.query(itemName, pos)
        if not self.validate(item, row, value, pos):
            return
        # advance to the first entry on the next row
        newDisplayNo = item.displayNo + 1
        if newDisplayNo >= len(self.itemDisplays):
            self.root.bell()
            return "break"

        self.focusOn(newDisplayNo, 0)


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
                lambda evt: self.handleShiftTab(item, pos, evt))
        inputEl.bind('<Key-Tab>',
                lambda evt: self.handleTab(item, pos, evt))
        inputEl.bind('<Key-Return>',
                lambda evt: self.handleReturn(item, pos, evt))
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
        addHeading("Stock")
        self.endRow()


    def addItemRow(self, ID, catID, itemName, paying, asking, demand, stock):
        row = []

        displayNo = len(self.itemDisplays)
        item = Item(ID, catID, itemName, displayNo)
        self.items[itemName] = item
        self.itemList.append(item)

        self.addLabel(itemName)
        self.addInput(itemName, paying, row)
        self.addInput(itemName, asking, row)
        self.addInput(itemName, demand, row)
        self.addInput(itemName, stock, row)

        self.itemDisplays.append(row)

        self.endRow()


    def createWidgets(self, dbPath, stationID):
        self.addHeadings()

        db = sqlite3.connect(str(dbPath))
        db.row_factory = sqlite3.Row
        cur = db.cursor()

        cur.execute("""
            SELECT  sys.name, stn.name
              FROM  Station AS stn
                        INNER JOIN System AS sys
                            USING (system_id)
             WHERE  stn.station_id = ?
             LIMIT  1
            """, [stationID])
        (self.sysName, self.stnName) = (cur.fetchone())

        self.root.title("{}/{}".format(self.sysName.upper(), self.stnName))

        cur.execute("""
            SELECT  cat.category_id AS ID,
                    cat.name AS name
              FROM  Category AS cat
              """)
        self.categories = { row["ID"]: row["name"] for row in cur }

        cur.execute("""
            SELECT  item.category_id AS catID,
                    item.item_id AS ID,
                    item.name AS name,
                    IFNULL(sb.price, '') AS paying,
                    IFNULL(ss.price, '') AS asking,
                    IFNULL(sb.units, 0) AS demandUnits,
                    IFNULL(sb.level, 0) AS demandLevel,
                    IFNULL(ss.units, 0) AS stockUnits,
                    IFNULL(ss.level, 0) AS stockLevel
              FROM  Category AS cat
                    INNER JOIN Item item
                        USING (category_id)
                    INNER JOIN StationItem si
                        USING (item_id)
                    LEFT OUTER JOIN StationBuying sb
                        USING (station_id, item_id)
                    LEFT OUTER JOIN StationSelling ss
                        USING (station_id, item_id)
             WHERE  si.station_id = ?
             ORDER  BY cat.name, si.ui_order
                """, [stationID])

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
                self.addSection(self.categories[cat])
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
                "@ {sys}/{stn}\n".format(
                    sys=self.sysName.upper(),
                    stn=self.stnName
                )
            )
        for item in self.itemList:
            if item.catID != lastCat:
                lastCat = item.catID
                txt += (" + {}\n".format(self.categories[lastCat]))

            row = self.itemDisplays[item.displayNo]
            rowvals = [ val[1].get() for val in row ]

            itemName = item.name
            paying = int(rowvals[0] or 0)
            asking = int(rowvals[1] or 0)
            demand = rowvals[2]
            stock  = rowvals[3]

            if asking == 0:
                stock = "-"
            elif asking > 0 and not demand:
                demand = "?"

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


def render(dbPath, stationID, tmpPath):
    root = tk.Tk()
    frame = UpdateFrame(root, dbPath, stationID)
    frame.pack(side="top", fill="both", expand=True)
    frame.mainloop()
    if not frame.results:
        frame.getResults()
    with tmpPath.open("w") as fh:
        print(frame.results, file=fh)


if __name__ == "__main__":
    render(Path("data/TradeDangerous.db"), 374, Path("update.prices"))
    print("- Wrote to update.prices")
