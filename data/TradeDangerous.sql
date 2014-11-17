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
CREATE INDEX idx_station_by_system ON Station (system_id, station_id);


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

/*
 * The table formerly known as "Price" is now broken
 * up into 3 tables: StationItem keeps track of what
 * items we think a station carries for presentation
 * purposes.
 *
 * StationBuying is the items that a station is willing
 * to pay for, but only carries entries that have a
 * non-zero price, demand and demand-level.
 *
 * StationCarrying is the items that a station has in
 * stock for players to buy, but only carries entries
 * that have a non-zero price, stock and stock-level.
 */

CREATE TABLE StationItem
 (
  station_id INTEGER NOT NULL,
  item_id INTEGER NOT NULL,
  modified DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
  ui_order INTEGER NOT NULL DEFAULT 0,

  PRIMARY KEY (station_id, item_id),

  FOREIGN KEY (item_id) REFERENCES Item(item_id)
   ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (station_id) REFERENCES Station(station_id)
   ON UPDATE CASCADE ON DELETE CASCADE
 )
;

/*
 * The most common query is going to be:
 * onSale = stock(station_id)
 * profitable = [
 *  item for item in onSale
 *    if someonePayingMoreFor(seller.item_id, seller.price)
 * ]
 * So we want selling indexed by station,item
 * and we want buying indexed by item,station
*/
CREATE TABLE StationSelling
 (
  station_id INTEGER NOT NULL,
  item_id INTEGER NOT NULL,
  price INTEGER CHECK (price > 0),
  units INTEGER CHECK (units == -1 OR units > 0),
  level INTEGER CHECK (level == -1 OR level > 0),
  modified DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
  PRIMARY KEY (station_id, item_id),
  FOREIGN KEY (item_id) REFERENCES Item(item_id)
   ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (station_id) REFERENCES Station(station_id)
   ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (station_id, item_id) REFERENCES StationItem (station_id, item_id)
   ON UPDATE CASCADE ON DELETE CASCADE
 )
;

CREATE TABLE StationBuying
 (
  item_id INTEGER NOT NULL,
  station_id INTEGER NOT NULL,
  price INTEGER CHECK (price > 0),
  units INTEGER CHECK (units == -1 OR units > 0),
  level INTEGER CHECK (level == -1 or level > 0),
  modified DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
  PRIMARY KEY (item_id, station_id),
  FOREIGN KEY (item_id) REFERENCES Item(item_id)
   ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (station_id) REFERENCES Station(station_id)
   ON UPDATE CASCADE ON DELETE CASCADE,
  FOREIGN KEY (station_id, item_id) REFERENCES StationItem (station_id, item_id)
   ON UPDATE CASCADE ON DELETE CASCADE
 )
;
/* We're often going to be asking "using (item_id) where buying.price > selling.cost" */
CREATE INDEX idx_buying_price ON StationBuying (item_id, price);

CREATE TABLE StationLink
 (
   lhs_system_id INTEGER NOT NULL,
   lhs_station_id INTEGER NOT NULL,
   rhs_system_id INTEGER NOT NULL,
   rhs_station_id INTEGER NOT NULL,
   dist DOUBLE NOT NULL CHECK (dist > 0.0),
   PRIMARY KEY (lhs_station_id, rhs_station_id)
 ) WITHOUT ROWID
;
CREATE INDEX idx_stn_dist ON StationLink (lhs_station_id, dist);
CREATE INDEX idx_sys_dist ON StationLink (lhs_system_id, dist, rhs_system_id);

CREATE VIEW vPrice AS
	SELECT	si.station_id AS station_id,
			si.item_id AS item_id,
			si.ui_order AS ui_order,
			IFNULL(sb.price, 0) AS sell_to,
			IFNULL(ss.price, 0) AS buy_from,
			si.modified AS modified,
            IFNULL(sb.units, 0) AS demand,
            IFNULL(sb.level, 0) AS demand_level,
            IFNULL(ss.units, 0) AS stock,
            IFNULL(ss.level, 0) AS stock_level
      FROM  StationItem AS si
            LEFT OUTER JOIN StationBuying AS sb
                USING (item_id, station_id)
            LEFT OUTER JOIN StationSelling AS ss
                USING (station_id, item_id)
;


CREATE VIEW vProfits AS
  SELECT  ss.item_id          AS item_id
       ,  ss.station_id       AS src_station_id
       ,  sb.station_id       AS dst_station_id
       ,  ss.price            AS cost
       ,  sb.price - ss.price AS gain
       ,  ss.units            AS stock_units
       ,  ss.level            AS stock_level
       ,  sb.units            AS demand_units
       ,  sb.level            AS demand_level
       ,  strftime('%s', 'now') -
            strftime('%s', ss.modified)
            AS src_age
       ,  strftime('%s', 'now') -
            strftime('%s', sb.modified)
            AS dst_age
    FROM  StationSelling AS ss
          INNER JOIN StationBuying AS sb
              ON (ss.item_id = sb.item_id
                  AND ss.station_id != sb.station_id)
   WHERE  ss.price < sb.price
;


CREATE VIEW vProfitableTrades AS
	SELECT	src.station_id AS src_station_id,
			src.item_id AS item_id,
			dst.station_id AS dst_station_id,
			src.price AS cost,
			dst.price - src.price AS profit,
			link.dist AS dist
	  FROM	StationSelling AS src
			INNER JOIN StationBuying AS dst
				ON (src.item_id = dst.item_id AND dst.price > src.price)
			INNER JOIN StationLink AS link
				ON (src.station_id = link.lhs_station_id
					AND dst.station_id = link.rhs_station_id)
;


COMMIT;

