-- Source for the TradeDangerous database.

-- I'm using foreign keys for referential integrity.
PRAGMA foreign_keys = ON;

-- Star systems
CREATE TABLE
 Systems
 (
   id INTEGER PRIMARY KEY AUTOINCREMENT,
   name VARCHAR(40) COLLATE nocase,
   pos_x DOUBLE NOT NULL,
   pos_y DOUBLE NOT NULL,
   pos_z DOUBLE NOT NULL,
   modified DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,

   UNIQUE (name)
 )
;
CREATE INDEX systems_position ON Systems (pos_x, pos_y, pos_z);

-- Stations within systems
CREATE TABLE
 Stations
 (
   id INTEGER PRIMARY KEY AUTOINCREMENT,
   name VARCHAR(40) COLLATE nocase,
   system_id INTEGER NOT NULL,
   ls_from_star DOUBLE NOT NULL,

   UNIQUE (name),

   FOREIGN KEY (system_id) REFERENCES Systems(id)
   	ON UPDATE CASCADE
   	ON DELETE CASCADE
 )
;
CREATE INDEX station_systems ON Stations (system_id);

-- Ships
CREATE TABLE
 Ships
 (
   id INTEGER PRIMARY KEY AUTOINCREMENT,
   name VARCHAR(40) COLLATE nocase,
   capacity INTEGER NOT NULL,
   mass INTEGER NOT NULL,
   drive_rating DOUBLE NOT NULL,
   max_ly_empty DOUBLE NOT NULL,
   max_ly_full DOUBLE NOT NULL,
   max_speed INTEGER NOT NULL,
   boost_speed INTEGER NOT NULL,

   UNIQUE (name)
 )
;

-- Where ships can be bought
CREATE TABLE
 ShipVendors
 (
   ship_id INTEGER NOT NULL,
   station_id INTEGER NOT NULL,
   cost INTEGER,

   PRIMARY KEY (ship_id, station_id),

   FOREIGN KEY (ship_id) REFERENCES Ships(id)
   	ON UPDATE CASCADE
   	ON DELETE CASCADE,
   FOREIGN KEY (station_id) REFERENCES Stations(id)
   	ON UPDATE CASCADE
   	ON DELETE CASCADE
 ) WITHOUT ROWID
;

CREATE TABLE
 Upgrades
 (
   id INTEGER PRIMARY KEY AUTOINCREMENT,
   name VARCHAR(40) COLLATE nocase,
   weight NUMBER NOT NULL,

   UNIQUE (name)
 )
;

CREATE TABLE
 UpgradeVendors
 (
   upgrade_id INTEGER NOT NULL,
   station_id INTEGER NOT NULL,
   cost INTEGER,

   PRIMARY KEY (upgrade_id, station_id),

   FOREIGN KEY (upgrade_id) REFERENCES Upgrades(id)
   	ON UPDATE CASCADE
   	ON DELETE CASCADE,
   FOREIGN KEY (station_id) REFERENCES Stations(id)
   	ON UPDATE CASCADE
   	ON DELETE CASCADE
 ) WITHOUT ROWID
;

-- Trade items are divided up into categories
CREATE TABLE
 ItemCategories
 (
   id INTEGER PRIMARY KEY AUTOINCREMENT,
   name VARCHAR(40) COLLATE nocase,

   UNIQUE (name)
 )
;

-- Tradeable items
CREATE TABLE
 Items
 (
   name VARCHAR(40) COLLATE nocase,
   category_id INTEGER NOT NULL,

   UNIQUE (category_id, name),

   FOREIGN KEY (category_id) REFERENCES ItemCategories(id)
   	ON UPDATE CASCADE
   	ON DELETE CASCADE
 )
;

CREATE TABLE
 Prices
 (
   item_id INTEGER NOT NULL,
   station_id INTEGER NOT NULL,
   ui_order INTEGER NOT NULL DEFAULT 0,
   from_stn_cr INTEGER NOT NULL,
   to_stn_cr INTEGER NOT NULL DEFAULT 0,
   modified DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,

   PRIMARY KEY (item_id, station_id),

   FOREIGN KEY (item_id) REFERENCES Items(id)
   	ON UPDATE CASCADE
      ON DELETE CASCADE,
   FOREIGN KEY (station_id) REFERENCES Stations(id)
   	ON UPDATE CASCADE
      ON DELETE CASCADE
 ) WITHOUT ROWID
;
