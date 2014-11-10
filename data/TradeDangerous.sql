--
-- This file contains definitions for all of the tables with
-- the exception of the price data.
--
-- Price data is stored in a non-SQL format in the top level
-- in a file called "TradeDangerous.prices"
--
-- If either file is changed, TradeDangerous will rebuild it's
-- sqlite3 database the next time it's run.
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
   ls_from_star DOUBLE NOT NULL,

   UNIQUE (name),

   FOREIGN KEY (system_id) REFERENCES System(system_id)
   	ON UPDATE CASCADE
   	ON DELETE CASCADE
 );


CREATE TABLE Ship
 (
   ship_id INTEGER PRIMARY KEY AUTOINCREMENT,
   name VARCHAR(40) COLLATE nocase,
   capacity INTEGER NOT NULL,
   mass INTEGER NOT NULL,
   drive_rating DOUBLE NOT NULL,
   max_ly_empty DOUBLE NOT NULL,
   max_ly_full DOUBLE NOT NULL,
   max_speed INTEGER NOT NULL,
   boost_speed INTEGER NOT NULL,

   UNIQUE (name)
 );


CREATE TABLE ShipVendor
 (
   ship_id INTEGER NOT NULL,
   station_id INTEGER NOT NULL,
   cost INTEGER,

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

   UNIQUE (category_id, name),

   FOREIGN KEY (category_id) REFERENCES Category(category_id)
   	ON UPDATE CASCADE
   	ON DELETE CASCADE
 );


-- Some items have two versions of their name.
CREATE TABLE AltItemNames
 (
   alt_name VARCHAR(40) NOT NULL COLLATE nocase,
   item_id INTEGER NOT NULL,

   PRIMARY KEY (alt_name, item_id)
 )
;


CREATE TABLE Price
 (
   station_id INTEGER NOT NULL,
   item_id INTEGER NOT NULL,
   ui_order INTEGER NOT NULL DEFAULT 0,
   -- how many credits will the station pay for this item?
   sell_to INTEGER NOT NULL,
   -- how many credits must you pay to buy at this station?
   buy_from INTEGER NOT NULL DEFAULT 0,
   modified DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
   demand INTEGER DEFAULT -1,
   demand_level INTEGER DEFAULT -1,
   stock INTEGER DEFAULT -1,
   stock_level INTEGER DEFAULT -1,

   PRIMARY KEY (station_id, item_id),

   FOREIGN KEY (item_id) REFERENCES Item(item_id)
   	ON UPDATE CASCADE
      ON DELETE CASCADE,
   FOREIGN KEY (station_id) REFERENCES Station(station_id)
   	ON UPDATE CASCADE
      ON DELETE CASCADE
 ) WITHOUT ROWID
;

-- Some views I use now and again.

CREATE VIEW vPriceDataAge AS
    SELECT System.name, MIN(Price.modified)
      FROM ((System INNER JOIN Station ON System.system_id = Station.system_id)
            INNER JOIN Price on Station.station_id = Price.station_id)
     GROUP BY 1
     ORDER BY 2 DESC
;

CREATE VIEW vOlderData AS
    SELECT System.name, MIN(Price.modified)
      FROM ((System INNER JOIN Station ON System.system_id = Station.system_id)
            INNER JOIN Price on Station.station_id = Price.station_id)
     WHERE Price.modified <= DATETIME(CURRENT_TIMESTAMP, '-2 day')
     GROUP BY 1
     ORDER BY 2 DESC
;

CREATE VIEW vForSale AS
   SELECT sy.name AS system
        , st.name AS station
        , c.name  AS category
        , i.name  AS item
        , p.buy_from AS asking
        , p.stock
        , p.stock_level
        , p.sell_to AS paying
        , p.demand
        , p.demand_level
        , STRFTIME('%s', 'now') - STRFTIME('%s', p.modified) AS age
     FROM System AS sy
          INNER JOIN Station as st ON (sy.system_id = st.system_id)
          INNER JOIN Price AS p ON (st.station_id = p.station_id)
          INNER JOIN Item AS I ON (p.item_id = i.item_id)
          INNER JOIN Category AS C on (i.category_id = c.category_id)
;

CREATE VIEW vForSaleOrdered AS
   SELECT * FROM vForSale ORDER BY system, station, category, item
;

COMMIT;
