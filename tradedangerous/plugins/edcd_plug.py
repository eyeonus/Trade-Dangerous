import csv
import pathlib

from .. import cache, transfers, csvexport
from ..tradedb import Category, Item
from . import PluginException, ImportPluginBase

class ImportPlugin(ImportPluginBase):
    """
    Download and process EDCD CSV-file(s)
    """
    
    pluginOptions = {
        'local':      "Use local EDCD CSV-files.",
        'csvs':       "Download and process all EDCD CSV-files.",
        'shipyard':   "Download and process EDCD shipyard.csv",
        'commodity':  "Download and process EDCD commodity.csv",
        'outfitting': "Download and process EDCD outfitting.csv",
    }
    
    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)
    
    def check_local_edcd(self):
        """
            Check local DB against EDCD
        """
        tdb, tdenv = self.tdb, self.tdenv
        
        tdCategories = list()
        for catID, catTD in sorted(tdb.categories(), key=lambda x: x[1].dbname):
            tdCategories.append(catTD.dbname)
            if catTD.dbname not in self.edcdCategories:
                tdenv.WARN("Category '{}' not in EDCD", catTD.dbname)
            
            for itemTD in sorted(catTD.items, key=lambda x: x.dbname):
                itemEDCD = self.edcdItems.get(itemTD.dbname, None)
                if not itemEDCD:
                    tdenv.DEBUG0("Item '{}' not in EDCD", itemTD.fullname)
                else:
                    if catTD.dbname != itemEDCD.category.dbname:
                        tdenv.WARN("Item '{}' has different category "
                            "'{}' (TD) != '{}' (EDCD)",
                            itemTD.dbname,
                            catTD.dbname, itemEDCD.category.dbname
                        )
        self.tdCategories = tdCategories
    
    def update_item_order(self, db):
        """
            Update the ui_order of the items
        """
        sqlStmt = (
            "SELECT category_id, name"
             " FROM Category"
            " ORDER BY name"
        )
        itmStmt = (
            "SELECT item_id, name"
             " FROM Item"
            " WHERE category_id = ?"
            " ORDER BY name"
        )
        updStmt = (
            "UPDATE Item"
              " SET ui_order = ?"
            " WHERE item_id = ?"
        )
        for catID, catName in db.execute(sqlStmt):
            itmOrder = 0
            for itmID, itmName in db.execute(itmStmt, [ catID ]):
                itmOrder += 1
                db.execute(updStmt, [ itmOrder, itmID ])
    
    def check_edcd_local(self):
        """
            Check EDCD items against local DB
        """
        tdb, tdenv = self.tdb, self.tdenv
        
        addItem = 0
        updItem = 0
        addCategory = 0
        
        commit = False
        db = tdb.getDB()
        for catNameEDCD in sorted(self.edcdCategories):
            catEDCD = self.edcdCategories[catNameEDCD]
            if catEDCD.dbname not in self.tdCategories:
                tdenv.NOTE("New category '{}'", catEDCD.dbname)
                sqlStmt = "INSERT INTO Category(name) VALUES(?)"
                
                tdenv.DEBUG0("SQL-Statement: {}", sqlStmt)
                tdenv.DEBUG0("SQL-Values: {}", [ catEDCD.dbname ])
                
                db.execute(sqlStmt, [ catEDCD.dbname ])
                addCategory += 1
                commit = True
            
            # Check EDCD items against local DB
            for itemEDCD in sorted(catEDCD.items, key=lambda x: x.dbname):
                itemTD = tdb.itemByName.get(itemEDCD.dbname, None)
                if not itemTD:
                    itemTD = tdb.itemByFDevID.get(itemEDCD.fdevID, None)
                    if itemTD:
                        tdenv.WARN(
                            "Item '{}' has different name '{}' (TD) != '{} '(EDCD).",
                            itemEDCD.fdevID, itemTD.dbname, itemEDCD.dbname
                        )
                    else:
                        tdenv.NOTE("New Item '{}'", itemEDCD.fullname)
                        insColumns = [
                            "name",
                            "category_id",
                            "fdev_id"
                        ]
                        insValues = [
                            itemEDCD.dbname,
                            catEDCD.dbname,
                            itemEDCD.fdevID
                        ]
                        if itemEDCD.avgPrice:
                            insColumns.append('avg_price')
                            insValues.append(itemEDCD.avgPrice)
                        sqlStmt = (
                            "INSERT INTO Item({}) VALUES(?,"
                                "(SELECT category_id "
                                   "FROM Category WHERE name = ?),?{})"
                            .format(
                                ",".join(insColumns),
                                ",?" if itemEDCD.avgPrice else ""
                            )
                        )
                        tdenv.DEBUG0("SQL-Statement: {}", sqlStmt)
                        tdenv.DEBUG0("SQL-Values: {}", insValues)
                        
                        db.execute(sqlStmt, insValues)
                        addItem += 1
                        commit = True
                else:
                    updValues = list()
                    updColumns = list()
                    if itemEDCD.avgPrice and itemTD.avgPrice != itemEDCD.avgPrice:
                        updColumns.append('avg_price')
                        updValues.append(itemEDCD.avgPrice)
                    if not itemTD.fdevID:
                        updColumns.append('fdev_id')
                        updValues.append(itemEDCD.fdevID)
                    else:
                        if itemTD.fdevID != itemEDCD.fdevID:
                            tdenv.WARN(
                                "Item '{}' has different FDevID {} (TD) != {} (EDCD).",
                                itemTD.fullname, itemTD.fdevID, itemEDCD.fdevID
                            )
                    if len(updColumns):
                        tdenv.NOTE("Update Item '{}' {} {}",
                            itemTD.fullname, updColumns, updValues
                        )
                        updValues.append(itemTD.ID)
                        sqlStmt = (
                            "UPDATE Item SET {} = ?"
                            " WHERE Item.item_id = ?".format(
                            " = ?,".join(updColumns))
                        )
                        tdenv.DEBUG0("SQL-Statement: {}", sqlStmt)
                        tdenv.DEBUG0("SQL-Values: {}", updValues)
                        
                        db.execute(sqlStmt, updValues)
                        updItem += 1
                        commit = True
        
        if addItem:
            self.update_item_order(db)
        
        if commit:
            db.commit()
            if addCategory:
                tdenv.NOTE("Added {} categorie(s)", addCategory)
                _, csvPath = csvexport.exportTableToFile(tdb, tdenv, 'Category')
                tdenv.NOTE("{} updated.", csvPath)
            if addItem or updItem:
                for textAdd, intAdd in [('Added', addItem), ('Updated', updItem)]:
                    if intAdd:
                        tdenv.NOTE("{} {} item(s)", textAdd, intAdd)
                _, csvPath = csvexport.exportTableToFile(tdb, tdenv, 'Item')
                tdenv.NOTE("{} updated.", csvPath)
        
        if not commit:
            tdenv.NOTE("Nothing had to be done")


    def process_fdevids_items(self, localPath, tableName):
        """
            More to do for commodities
        """
        tdenv = self.tdenv
        tdenv.NOTE("Processing {}", tableName)
        
        itmCount = 0
        catCount = 0
        edcdItems = {}
        edcdCategories = {}
        with localPath.open('r', encoding='utf-8') as importFile:
            csvIn = csv.reader(
                importFile, delimiter=',', quotechar="'", doublequote=True
            )
            # first line must be the column names
            columnDefs = next(csvIn)
            
            tdenv.DEBUG0("columnDefs: {}", columnDefs)
            
            idxMap = {}
            for cIndex, cName in enumerate(columnDefs):
                idxMap[cName] = cIndex
            tdenv.DEBUG0("idxMap: {}", idxMap)
            
            notGood = False
            for checkMe in ('id', 'category', 'name'):
                if checkMe not in idxMap:
                    tdenv.WARN("'{}' column not in {}.", checkMe, localPath)
                    notGood = True
            hasAverage = True if 'average' in idxMap else False
            
            def castToInteger(val):
                try:
                    val = int(val)
                except:
                    val = None
                    pass
                return val
            
            if notGood:
                tdenv.NOTE("Import stopped.", checkMe, localPath)
            else:
                for lineIn in csvIn:
                    if not lineIn:
                        continue
                    lineNo = csvIn.line_num
                    tdenv.DEBUG0("LINE {}: {}", lineNo, lineIn)
                    
                    # strip() it do be save
                    edcdId       = lineIn[idxMap['id']].strip()
                    edcdCategory = lineIn[idxMap['category']].strip()
                    edcdName     = lineIn[idxMap['name']].strip()
                    if hasAverage:
                        edcdAverage = lineIn[idxMap['average']].strip()
                    else:
                        edcdAverage = None
                    
                    if edcdCategory.lower() == "nonmarketable":
                        # we are, after all, a trading tool
                        tdenv.DEBUG0("Ignoring {}/{}", edcdCategory, edcdName)
                        continue
                    
                    edcdId      = castToInteger(edcdId)
                    edcdAverage = castToInteger(edcdAverage)
                    
                    itemCategory = edcdCategories.get(edcdCategory, None)
                    if not itemCategory:
                        itemCategory = Category(0, edcdCategory, [])
                        edcdCategories[edcdCategory] = itemCategory
                        catCount += 1
                        tdenv.DEBUG1("NEW CATEGORY: {}", edcdCategory)
                    
                    if edcdName not in edcdItems:
                        newItem = Item(
                            edcdId, edcdName, itemCategory,
                            '{}/{}'.format(itemCategory.dbname, edcdName),
                            edcdAverage, edcdId
                        )
                        edcdItems[edcdName] = newItem
                        itemCategory.items.append(newItem)
                        itmCount += 1
                        tdenv.DEBUG1("NEW ITEM: {}", edcdName)
        
        self.edcdItems = edcdItems
        self.edcdCategories = edcdCategories
        
        tdenv.NOTE("Found {} categorie(s)", catCount)
        tdenv.NOTE("Found {} item(s)", itmCount)
        
        if catCount or itmCount:
            self.check_local_edcd()
            self.check_edcd_local()
    
    def process_fdevids_table(self, localPath, tableName):
        """
            Shipyard and outfitting files can be directly imported.
        """
        tdb, tdenv = self.tdb, self.tdenv
        tdenv.NOTE("Processing {}", tableName)
        
        db = tdb.getDB()
        db.execute("DELETE FROM {}".format(tableName))
        cache.processImportFile(
            tdenv,
            db,
            localPath,
            tableName
        )
        db.commit()
        lines, csvPath = csvexport.exportTableToFile(
            tdb,
            tdenv,
            tableName,
        )
        tdenv.NOTE("Imported {} {}(s).", lines, tableName)
        tdenv.NOTE("{} updated.", csvPath)
    
    def download_fdevids(self):
        """
            Download the current data from EDCD,
            see https://github.com/EDCD/FDevIDs
        """
        tdb, tdenv = self.tdb, self.tdenv
        
        BASE_URL = "https://raw.githubusercontent.com/EDCD/FDevIDs/master/"
        downloadList = []
        if self.getOption("shipyard"):
            downloadList.append(
                ('FDevShipyard', 'shipyard.csv', self.process_fdevids_table)
            )
        if self.getOption("outfitting"):
            downloadList.append(
                ('FDevOutfitting', 'outfitting.csv', self.process_fdevids_table)
            )
        if self.getOption("commodity"):
            downloadList.append(
                ('FDevCommodity', 'commodity.csv', self.process_fdevids_items)
            )
        
        if len(downloadList) == 0:
            tdenv.NOTE("I don't know what do to, give me some options!")
            return
        
        optLocal = self.getOption("local")
        for tableName, fileEDCD, callMeBack in downloadList:
            localPath = tdb.dataPath / pathlib.Path(tableName).with_suffix(".csv")
            if optLocal:
                if not localPath.exists():
                    raise PluginException(
                        "CSV-file '{}' not found.".format(str(localPath))
                    )
            else:
                transfers.download(
                    tdenv,
                    BASE_URL + fileEDCD,
                    str(localPath),
                )
            if callMeBack:
                callMeBack(localPath, tableName)
    
    def run(self):
        tdb, tdenv = self.tdb, self.tdenv
        
        tdenv.DEBUG0("csvs: {}", self.getOption("csvs"))
        tdenv.DEBUG0("shipyard: {}", self.getOption("shipyard"))
        tdenv.DEBUG0("commodity: {}", self.getOption("commodity"))
        tdenv.DEBUG0("outfitting: {}", self.getOption("outfitting"))
        
        if self.getOption("csvs"):
            self.options["shipyard"] = True
            self.options["commodity"] = True
            self.options["outfitting"] = True
        
        # Ensure the cache is built and reloaded.
        tdb.reloadCache()
        tdb.load(maxSystemLinkLy=tdenv.maxSystemLinkLy)
        
        self.download_fdevids()
        
        # We did all the work
        return False
