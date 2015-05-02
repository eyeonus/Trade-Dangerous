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

BEGIN TRANSACTION;


CREATE TABLE Added
 (
   added_id INTEGER PRIMARY KEY AUTOINCREMENT,
   name VARCHAR(40) COLLATE nocase,

   UNIQUE(name)
 );


CREATE TABLE System
 (
   system_id INTEGER PRIMARY KEY AUTOINCREMENT,
   name VARCHAR(40) COLLATE nocase,
   pos_x DOUBLE NOT NULL,
   pos_y DOUBLE NOT NULL,
   pos_z DOUBLE NOT NULL,
   added_id INTEGER,
   modified DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,

   UNIQUE (name),

    FOREIGN KEY (added_id) REFERENCES Added(added_id)
    ON UPDATE CASCADE
    ON DELETE CASCADE
 );
CREATE INDEX idx_system_by_pos ON System (pos_x, pos_y, pos_z, system_id);


CREATE TABLE Station
 (
   station_id INTEGER PRIMARY KEY AUTOINCREMENT,
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

   UNIQUE (system_id, name),

   FOREIGN KEY (system_id) REFERENCES System(system_id)
    ON UPDATE CASCADE
    ON DELETE CASCADE
 );
CREATE INDEX idx_station_by_system ON Station (system_id, station_id);
CREATE INDEX idx_station_by_name ON Station (name);


CREATE TABLE Ship
 (
   ship_id INTEGER PRIMARY KEY AUTOINCREMENT,
   name VARCHAR(40) COLLATE nocase,
   cost INTEGER NOT NULL,

   UNIQUE (name)
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
   upgrade_id INTEGER PRIMARY KEY AUTOINCREMENT,
   name VARCHAR(40) COLLATE nocase,
   weight NUMBER NOT NULL,

   UNIQUE (name)
 );


CREATE TABLE UpgradeVendor
 (
   upgrade_id INTEGER NOT NULL,
   station_id INTEGER NOT NULL,
   cost INTEGER,

   PRIMARY KEY (upgrade_id, station_id),

   FOREIGN KEY (upgrade_id) REFERENCES Upgrade(upgrade_id)
    ON UPDATE CASCADE
    ON DELETE CASCADE,
   FOREIGN KEY (station_id) REFERENCES Station(station_id)
    ON UPDATE CASCADE
    ON DELETE CASCADE
 ) WITHOUT ROWID
;


CREATE TABLE RareItem
 (
   rare_id INTEGER PRIMARY KEY AUTOINCREMENT,
   station_id INTEGER NOT NULL,
   name VARCHAR(40) COLLATE nocase,
   cost INTEGER,
   max_allocation INTEGER,
   illegal TEXT(1) NOT NULL DEFAULT '?'
       CHECK (illegal IN ('?', 'Y', 'N')),

   UNIQUE (name),

   FOREIGN KEY (station_id) REFERENCES Station(station_id)
    ON UPDATE CASCADE
    ON DELETE CASCADE
 )
;

CREATE TABLE Category
 (
   category_id INTEGER PRIMARY KEY AUTOINCREMENT,
   name VARCHAR(40) COLLATE nocase,

   UNIQUE (name)
 );


CREATE TABLE Item
 (
   item_id INTEGER PRIMARY KEY AUTOINCREMENT,
   name VARCHAR(40) COLLATE nocase,
   category_id INTEGER NOT NULL,
   ui_order INTEGER NOT NULL DEFAULT 0,

   UNIQUE (category_id, name),

   FOREIGN KEY (category_id) REFERENCES Category(category_id)
    ON UPDATE CASCADE
    ON DELETE CASCADE
 );

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

  PRIMARY KEY (station_id, item_id),
  FOREIGN KEY (station_id) REFERENCES Station(station_id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (item_id) REFERENCES Item(item_id)
    ON UPDATE CASCADE ON DELETE CASCADE
);
CREATE INDEX si_mod_stn_itm ON StationItem(modified, station_id, item_id);
CREATE INDEX si_itm_dmdpr ON StationItem(item_id, demand_price) WHERE demand_price > 0;
CREATE INDEX si_itm_suppr ON StationItem(item_id, supply_price) WHERE supply_price > 0;

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

COMMIT;

