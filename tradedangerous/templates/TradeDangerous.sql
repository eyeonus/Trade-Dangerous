-- Definitions for all of the tables used in the SQLite
-- cache database.
--
-- Source data for TradeDangerous is stored in various
-- ".csv" files which provide relatively constant data
-- such as star names, the list of known tradeable items,
-- etc.
--
-- Per-station price data is sourced from ".prices" files
-- which are designed to be human readable text that
-- closely aproximates the in-game UI.
--
-- When the .SQL file or the .CSV files change, TD will
-- destroy and rebuild the cache next time it is run.
--
-- When the .prices file is changed, only the price data
-- is reset.
--
-- You can edit this file, if you really need to, if you know
-- what you are doing. Or you can use the 'sqlite3' command
-- to edit the .db database and then use the '.dump' command
-- to regenerate this file, except then you'll lose this nice
-- header and I might have to wag my finger at you.
--
-- -Oliver

PRAGMA foreign_keys=ON;
PRAGMA synchronous=OFF;
PRAGMA temp_store=MEMORY;
PRAGMA journal_mode=WAL;
PRAGMA auto_vacuum=INCREMENTAL;

BEGIN TRANSACTION;


CREATE TABLE Added
 (
   added_id INTEGER PRIMARY KEY AUTOINCREMENT,
   name VARCHAR(40) COLLATE nocase,

   UNIQUE(name)
 );


CREATE TABLE System
 (
   system_id INTEGER PRIMARY KEY,
   name VARCHAR(40) COLLATE nocase,
   pos_x DOUBLE NOT NULL,
   pos_y DOUBLE NOT NULL,
   pos_z DOUBLE NOT NULL,
   added_id INTEGER,
   modified DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,

   UNIQUE (system_id),

    FOREIGN KEY (added_id) REFERENCES Added(added_id)
    ON UPDATE CASCADE
    ON DELETE CASCADE
 );
CREATE INDEX idx_system_by_pos ON System (pos_x, pos_y, pos_z, system_id);


CREATE TABLE Station
 (
   station_id INTEGER PRIMARY KEY,
   name VARCHAR(40) COLLATE nocase,
   system_id INTEGER NOT NULL,
   ls_from_star INTEGER NOT NULL DEFAULT 0
       CHECK (ls_from_star >= 0),
   blackmarket TEXT(1) NOT NULL DEFAULT '?'
       CHECK (blackmarket IN ('?', 'Y', 'N')),
   max_pad_size TEXT(1) NOT NULL DEFAULT '?'
       CHECK (max_pad_size IN ('?', 'S', 'M', 'L')),
   market TEXT(1) NOT NULL DEFAULT '?'
       CHECK (market IN ('?', 'Y', 'N')),
   shipyard TEXT(1) NOT NULL DEFAULT '?'
       CHECK (shipyard IN ('?', 'Y', 'N')),
   modified DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
   outfitting TEXT(1) NOT NULL DEFAULT '?'
       CHECK (outfitting IN ('?', 'Y', 'N')),
   rearm      TEXT(1) NOT NULL DEFAULT '?'
       CHECK (rearm      IN ('?', 'Y', 'N')),
   refuel     TEXT(1) NOT NULL DEFAULT '?'
       CHECK (refuel     IN ('?', 'Y', 'N')),
   repair     TEXT(1) NOT NULL DEFAULT '?'
       CHECK (repair     IN ('?', 'Y', 'N')),
   planetary  TEXT(1) NOT NULL DEFAULT '?'
       CHECK (planetary  IN ('?', 'Y', 'N')),
   type_id INTEGER DEFAULT 0 NOT NULL,

   UNIQUE (station_id),

   FOREIGN KEY (system_id) REFERENCES System(system_id)
    ON DELETE CASCADE
 ) WITHOUT ROWID;
CREATE INDEX idx_station_by_system ON Station (system_id);
CREATE INDEX idx_station_by_name ON Station (name);


CREATE TABLE Ship
 (
   ship_id INTEGER PRIMARY KEY,
   name VARCHAR(40) COLLATE nocase,
   cost INTEGER,

   UNIQUE (ship_id)
 );


CREATE TABLE ShipVendor
 (
   ship_id INTEGER NOT NULL,
   station_id INTEGER NOT NULL,
   modified DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,

   PRIMARY KEY (ship_id, station_id),

   FOREIGN KEY (ship_id) REFERENCES Ship(ship_id)
    ON UPDATE CASCADE
    ON DELETE CASCADE,
   FOREIGN KEY (station_id) REFERENCES Station(station_id)
    ON UPDATE CASCADE
    ON DELETE CASCADE
 ) WITHOUT ROWID
;


CREATE TABLE Upgrade
 (
   upgrade_id INTEGER PRIMARY KEY,
   name VARCHAR(40) COLLATE nocase,
   class NUMBER NOT NULL,
   rating CHAR(1) NOT NULL,
   ship VARCHAR(40) COLLATE nocase,

   UNIQUE (upgrade_id)
 );


CREATE TABLE UpgradeVendor
 (
   upgrade_id INTEGER NOT NULL,
   station_id INTEGER NOT NULL,
   modified DATETIME NOT NULL,

   PRIMARY KEY (upgrade_id, station_id),

   FOREIGN KEY (upgrade_id) REFERENCES Upgrade(upgrade_id)
    ON UPDATE CASCADE
    ON DELETE CASCADE,
   FOREIGN KEY (station_id) REFERENCES Station(station_id)
    ON UPDATE CASCADE
    ON DELETE CASCADE
 ) WITHOUT ROWID
;
CREATE INDEX idx_vendor_by_station_id ON UpgradeVendor (station_id);

CREATE TABLE RareItem
 (
   rare_id INTEGER PRIMARY KEY,
   station_id INTEGER NOT NULL,
   category_id INTEGER NOT NULL,
   name VARCHAR(40) COLLATE nocase,
   cost INTEGER,
   max_allocation INTEGER,
   illegal TEXT(1) NOT NULL DEFAULT '?'
       CHECK (illegal IN ('?', 'Y', 'N')),
   suppressed TEXT(1) NOT NULL DEFAULT '?'
       CHECK (suppressed IN ('?', 'Y', 'N')),

   UNIQUE (name),

   FOREIGN KEY (station_id) REFERENCES Station(station_id)
    ON UPDATE CASCADE
    ON DELETE CASCADE,
   FOREIGN KEY (category_id) REFERENCES Category(category_id)
    ON UPDATE CASCADE
    ON DELETE CASCADE
 )
;

CREATE TABLE Category
 (
   category_id INTEGER PRIMARY KEY,
   name VARCHAR(40) COLLATE nocase,

   UNIQUE (category_id)
 );


CREATE TABLE Item
 (
   item_id INTEGER PRIMARY KEY,
   name VARCHAR(40) COLLATE nocase,
   category_id INTEGER NOT NULL,
   ui_order INTEGER NOT NULL DEFAULT 0,
   avg_price INTEGER,
   fdev_id INTEGER,

   UNIQUE (item_id),

   FOREIGN KEY (category_id) REFERENCES Category(category_id)
    ON UPDATE CASCADE
    ON DELETE CASCADE
 );
 CREATE INDEX idx_item_by_fdev_id ON Item (fdev_id);


CREATE TABLE StationItem
 (
  station_id INTEGER NOT NULL,
  item_id INTEGER NOT NULL,
  demand_price INT NOT NULL,
  demand_units INT NOT NULL,
  demand_level INT NOT NULL,
  supply_price INT NOT NULL,
  supply_units INT NOT NULL,
  supply_level INT NOT NULL,
  modified DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
  from_live INTEGER DEFAULT 0 NOT NULL,

  PRIMARY KEY (station_id, item_id),
  FOREIGN KEY (station_id) REFERENCES Station(station_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (item_id) REFERENCES Item(item_id)
    ON UPDATE CASCADE ON DELETE CASCADE
) WITHOUT ROWID;
CREATE INDEX si_mod_stn_itm ON StationItem(modified, station_id, item_id);
CREATE INDEX si_itm_dmdpr ON StationItem(item_id, demand_price) WHERE demand_price > 0;
CREATE INDEX si_itm_suppr ON StationItem(item_id, supply_price) WHERE supply_price > 0;

-- Not used yet
CREATE TABLE IF NOT EXISTS StationDemand
(
    station_id      INTEGER NOT NULL,
    item_id         INTEGER NOT NULL,
    price           INTEGER NOT NULL,
    units           INTEGER NOT NULL,
    level           INTEGER NOT NULL,
    modified        INTEGER NOT NULL,
    from_live       INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT pk_StationDemand PRIMARY KEY (station_id, item_id),
    CONSTRAINT fk_StationDemand_station_id_Station FOREIGN KEY (station_id) REFERENCES Station (station_id) ON DELETE CASCADE,
    CONSTRAINT fk_StationDemand_item_id_Item       FOREIGN KEY (item_id)    REFERENCES Item    (item_id)    ON DELETE CASCADE
) WITHOUT ROWID;
DELETE FROM StationDemand;
CREATE INDEX idx_StationDemand_item ON StationDemand (item_id);

-- Not used yet
CREATE TABLE IF NOT EXISTS StationSupply
(
    station_id      INTEGER NOT NULL,
    item_id         INTEGER NOT NULL,
    price           INTEGER NOT NULL,
    units           INTEGER NOT NULL,
    level           INTEGER NOT NULL,
    modified        INTEGER NOT NULL,
    from_live       INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT pk_StationSupply PRIMARY KEY (station_id, item_id),
    CONSTRAINT fk_StationSupply_station_id_Station FOREIGN KEY (station_id) REFERENCES Station (station_id) ON DELETE CASCADE,
    CONSTRAINT fk_StationSupply_item_id_Item       FOREIGN KEY (item_id)    REFERENCES Item    (item_id)    ON DELETE CASCADE
) WITHOUT ROWID;
DELETE FROM StationSupply;
CREATE INDEX idx_StationSupply_item ON StationSupply (item_id);

CREATE VIEW StationBuying AS
SELECT  station_id,
        item_id,
        demand_price AS price,
        demand_units AS units,
        demand_level AS level,
        modified
  FROM  StationItem
 WHERE  demand_price > 0
;

CREATE VIEW StationSelling AS
SELECT  station_id,
        item_id,
        supply_price AS price,
        supply_units AS units,
        supply_level AS level,
        modified
  FROM  StationItem
 WHERE  supply_price > 0
;


--
-- The next two tables (FDevShipyard, FDevOutfitting) are
-- used to map the FDev API IDs to data ready for EDDN.
--
-- The column names are the same as the header line from
-- the EDCD/FDevIDs csv files, so we can just download the
-- files (shipyard.csv, outfitting.csv) and save them
-- as (FDevShipyard.csv, FDevOutfitting.csv) into the
-- data directory.
--
-- see https://github.com/EDCD/FDevIDs
--
-- The commodity.csv is not needed because TD and EDDN
-- are using the same names.
--
-- -Bernd

CREATE TABLE FDevShipyard
 (
   id INTEGER NOT NULL,
   symbol VARCHAR(40),
   name VARCHAR(40) COLLATE nocase,
   entitlement VARCHAR(50),

   UNIQUE (id)
 );


CREATE TABLE FDevOutfitting
 (
   id INTEGER NOT NULL,
   symbol VARCHAR(40),
   category CHAR(10)
      CHECK (category IN ('hardpoint','internal','standard','utility')),
   name VARCHAR(40) COLLATE nocase,
   mount CHAR(10)
      CHECK (mount IN (NULL, 'Fixed','Gimballed','Turreted')),
   guidance CHAR(10)
      CHECK (guidance IN (NULL, 'Dumbfire','Seeker','Swarm')),
   ship VARCHAR(40) COLLATE nocase,
   class CHAR(1) NOT NULL,
   rating CHAR(1) NOT NULL,
   entitlement VARCHAR(50),

   UNIQUE (id)
 );


COMMIT;
