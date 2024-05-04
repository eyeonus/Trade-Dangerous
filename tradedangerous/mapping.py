#
# Mapping class for FDEV-IDs to TD names
#
# Deprecated
# FDEVMappingItems and FDEVMappingShips used by edapi plugin
class FDEVMappingBase:
    """
    Base class to map FDEV-IDs to TD names, do not use directly.
    
    Derived class must declare "tableName" and "colNames" which are used
    to select the ID->Name mapping from the database.
    
    "colNames" is a list() of columns. The first one must be the idColumn.
    
    If there are unknown IDs but name mappings override the mapUnknown()
    method and use addUnknown().
    """
    
    def __init__(self, tdb, tdenv):
        """
        Parameters:
            tdb    Instance of TradeDB
            tdenv  Instance of TradeEnv
        """
        self.tdb      = tdb
        self.tdenv    = tdenv
        self._colCount = len(self.colNames) - 1
        self.mapLoad()
        anz = len(self.entries)
        self.mapUnknown()
        self._mapCount = len(self.entries)
        anz = self._mapCount - anz
        if anz > 0:
            self.tdenv.DEBUG1("Added {:n} unkown {}-Mappings".format(anz, self.tableName))
    
    @property
    def colCount(self):
        return self._colCount
    
    @property
    def mapCount(self):
        return self._mapCount
    
    def mapLoad(self):
        """
        Loads the mapping
        """
        stmt = """
            SELECT {columns}
              FROM {table}
             WHERE LENGTH({idCol}) > 0
        """.format(columns=",".join(self.colNames),
                   table=self.tableName,
                   idCol=self.colNames[0]
                  )
        
        self.tdenv.DEBUG1("Loading mapping for {}".format(self.tableName))
        
        conn = self.tdb.getDB()
        curs = conn.cursor()
        
        entries = {}
        curs.execute(stmt)
        for line in curs:
            ID = line[0]
            if self._colCount == 1:
                entries[ID] = line[1]
            else:
                entries[ID] = {}
                for i, val in enumerate(line[1:], start=1):
                    if val:
                        entries[ID][self.colNames[i]] = val
            self.tdenv.DEBUG2("{}: {}".format(ID, str(entries[ID]).replace("{", "{{").replace("}", "}}")))
        self.entries = entries
        self.tdenv.DEBUG1("Loaded {:n} {}-Mappings".format(len(entries), self.tableName))
    
    def addUnknown(self, wrong, right):
        # add Entries by name with unknown IDs
        if isinstance(wrong, (str,int,tuple)):
            self.tdenv.DEBUG2("{}: {}".format(wrong, right))
            self.entries[wrong] = right
        else:
            self.tdenv.WARN("{}: {}".format(wrong, right))
        return
    
    def mapUnknown(self):
        # override this and add unknown IDs in the derived class
        return
    
    def mapID(self, ID, oldValue=None):
        res = self.entries.get(int(ID), None)
        if not res:
            if isinstance(oldValue, (str,int)):
                res = self.entries.get(oldValue, oldValue)
            elif isinstance(oldValue, tuple):
                res = self.entries.get(oldValue, None)
        return res

class FDEVMappingItems(FDEVMappingBase):
    """
        Maps ID to TD and EDDN items
    """
    tableName = "Item"
    colNames  = [ 'item_id', 'name' ]
    
    def mapUnknown(self):
        # no ID known yet for:
        self.addUnknown('Comercial Samples',      'Commercial Samples')
        self.addUnknown('Encripted Data Storage', 'Encrypted Data Storage')
        self.addUnknown('Wreckage Components',    'Salvageable Wreckage')

class FDEVMappingShips(FDEVMappingBase):
    """
        Maps ID to TD ships
    """
    tableName = "Ship"
    colNames  = [ 'ship_id', 'name' ]

class FDEVMappingShipyard(FDEVMappingBase):
    """
        Maps ID to EDDN shipyard
    """
    tableName = "FDevShipyard"
    colNames  = [ 'id', 'name' ]

class FDEVMappingOutfitting(FDEVMappingBase):
    """
        Maps ID to EDDN outfitting
    """
    tableName = "FDevOutfitting"
    colNames  = [ 'id', 'category', 'name', 'mount',
                  'guidance', 'ship', 'class', 'rating'
                ]
