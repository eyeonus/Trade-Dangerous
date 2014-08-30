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
CREATE TABLE System
 (
   system_id INTEGER PRIMARY KEY AUTOINCREMENT,
   name VARCHAR(40) COLLATE nocase,
   pos_x DOUBLE NOT NULL,
   pos_y DOUBLE NOT NULL,
   pos_z DOUBLE NOT NULL,
   modified DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,

   UNIQUE (name)
 );
INSERT INTO "System" VALUES(1,'26 Draconis',-39.0,24.90625,-0.65625,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(2,'Acihaut',-18.5,25.28125,-4.0,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(3,'Aganippe',-11.5625,43.8125,11.625,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(4,'Asellus Primus',-23.9375,40.875,-1.34375,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(5,'Aulin',-19.6875,32.6875,4.75,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(6,'Aulis',-16.46875,44.1875,-11.4375,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(7,'BD+47 2112',-14.78125,33.46875,-0.40625,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(8,'BD+55 1519',-16.9375,44.71875,-16.59375,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(9,'Bolg',-7.90625,34.71875,2.125,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(10,'Chi Herculis',-30.75,39.71875,12.78125,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(11,'CM Draco',-35.6875,30.9375,2.15625,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(12,'Dahan',-19.75,41.78125,-3.1875,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(13,'DN Draconis',-27.09375,21.625,0.78125,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(14,'DP Draconis',-17.5,25.96875,-11.375,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(15,'Eranin',-22.84375,36.53125,-1.1875,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(16,'G 239-25',-22.6875,25.8125,-6.6875,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(17,'GD 319',-19.375,43.625,-12.75,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(18,'h Draconis',-39.84375,29.5625,-3.90625,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(19,'Hermitage',-28.75,25.0,10.4375,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(20,'i Bootis',-22.375,34.84375,4.0,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(21,'Ithaca',-8.09375,44.9375,-9.28125,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(22,'Keries',-18.90625,27.21875,12.59375,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(23,'Lalande 29917',-26.53125,22.15625,-4.5625,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(24,'LFT 1361',-38.78125,24.71875,-0.5,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(25,'LFT 880',-22.8125,31.40625,-18.34375,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(26,'LFT 992',-7.5625,42.59375,0.6875,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(27,'LHS 2819',-30.5,38.5625,-13.4375,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(28,'LHS 2884',-22.0,48.40625,1.78125,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(29,'LHS 2887',-7.34375,26.78125,5.71875,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(30,'LHS 3006',-21.96875,29.09375,-1.71875,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(31,'LHS 3262',-24.125,18.84375,4.90625,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(32,'LHS 417',-18.3125,18.1875,4.90625,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(33,'LHS 5287',-36.40625,48.1875,-0.78125,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(34,'LHS 6309',-33.5625,33.125,13.46875,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(35,'LP 271-25',-10.46875,31.84375,7.3125,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(36,'LP 275-68',-23.34375,25.0625,15.1875,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(37,'LP 64-194',-21.65625,32.21875,-16.21875,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(38,'LP 98-132',-26.78125,37.03125,-4.59375,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(39,'Magec',-32.875,36.15625,15.5,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(40,'Meliae',-17.3125,49.53125,-1.6875,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(41,'Morgor',-15.25,39.53125,-2.25,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(42,'Nang Ta-khian',-18.21875,26.5625,-6.34375,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(43,'Naraka',-34.09375,26.21875,-5.53125,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(44,'Opala',-25.5,35.25,9.28125,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(45,'Ovid',-28.0625,35.15625,14.8125,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(46,'Pi-fang',-34.65625,22.84375,-4.59375,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(47,'Rakapila',-14.90625,33.625,9.125,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(48,'Ross 1015',-6.09375,29.46875,3.03125,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(49,'Ross 1051',-37.21875,44.5,-5.0625,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(50,'Ross 1057',-32.3125,26.1875,-12.4375,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(51,'Styx',-24.3125,37.75,6.03125,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(52,'Surya',-38.46875,39.25,5.40625,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(53,'Tilian',-21.53125,22.3125,10.125,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(54,'WISE 1647+5632',-21.59375,17.71875,1.75,'2014-08-26 15:22:38');
INSERT INTO "System" VALUES(55,'Wyrd',-11.625,31.53125,-3.9375,'2014-08-26 15:22:38');
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
INSERT INTO "Station" VALUES(1,'Beagle 2 Landing',4,0.0);
INSERT INTO "Station" VALUES(2,'Gateway',12,0.0);
INSERT INTO "Station" VALUES(3,'Freeport',38,0.0);
INSERT INTO "Station" VALUES(4,'Chango Dock',20,0.0);
INSERT INTO "Station" VALUES(5,'Azeban City',15,0.0);
INSERT INTO "Station" VALUES(6,'Aulin Enterprise',5,0.0);
INSERT INTO "Station" VALUES(7,'WCM Transfer Orbital',30,0.0);
INSERT INTO "Station" VALUES(8,'Romanenko',44,0.0);
INSERT INTO "Station" VALUES(9,'Romanek''s Folly',41,0.0);
INSERT INTO "Station" VALUES(10,'Bradfield',45,0.0);
INSERT INTO "Station" VALUES(11,'Gorbatko',10,0.0);
INSERT INTO "Station" VALUES(12,'Cuffey Plant',2,0.0);
INSERT INTO "Station" VALUES(13,'Hay Point',42,0.0);
INSERT INTO "Station" VALUES(14,'Bresnik Mine',16,0.0);
INSERT INTO "Station" VALUES(15,'Vonarburg Co-operative',55,0.0);
INSERT INTO "Station" VALUES(16,'Olivas Settlement',7,0.0);
INSERT INTO "Station" VALUES(17,'Moxon''s Mojo',9,0.0);
INSERT INTO "Station" VALUES(18,'Bowersox',48,0.0);
INSERT INTO "Station" VALUES(19,'Massimino Dock',29,0.0);
INSERT INTO "Station" VALUES(20,'Stone Enterprise',47,0.0);
INSERT INTO "Station" VALUES(21,'Derrickson''s Escape',22,0.0);
INSERT INTO "Station" VALUES(22,'Xiaoguan',39,0.0);
INSERT INTO "Station" VALUES(23,'Gernhardt Camp',32,0.0);
INSERT INTO "Station" VALUES(24,'Louis De Lacaille Prospect',31,0.0);
INSERT INTO "Station" VALUES(25,'Maunder',53,0.0);
INSERT INTO "Station" VALUES(26,'Novitski Oasis',43,0.0);
INSERT INTO "Station" VALUES(27,'Brooks',46,0.0);
INSERT INTO "Station" VALUES(28,'Julian Market',3,0.0);
INSERT INTO "Station" VALUES(29,'Abnett Platform',28,0.0);
INSERT INTO "Station" VALUES(30,'Mcarthur''s Reach',33,0.0);
INSERT INTO "Station" VALUES(31,'Dezhurov Gateway',6,0.0);
INSERT INTO "Station" VALUES(32,'Hume Depot',21,0.0);
INSERT INTO "Station" VALUES(33,'Szulkin Mines',26,0.0);
INSERT INTO "Station" VALUES(34,'Baker Platform',25,0.0);
INSERT INTO "Station" VALUES(35,'Longyear Survey',37,0.0);
INSERT INTO "Station" VALUES(36,'Tasaki Freeport',27,0.0);
INSERT INTO "Station" VALUES(37,'Abetti Platform',49,0.0);
INSERT INTO "Station" VALUES(38,'Anderson Escape',11,0.0);
INSERT INTO "Station" VALUES(39,'Brislington',18,0.0);
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
INSERT INTO "Ship" VALUES(1,'Eagle',6,52,348.0,6.59,6.0,240,350);
INSERT INTO "Ship" VALUES(2,'Sidewinder',4,47,348.0,8.13,7.25,220,293);
INSERT INTO "Ship" VALUES(3,'Hauler',16,39,348.0,8.74,6.1,200,246);
INSERT INTO "Ship" VALUES(4,'Viper',8,40,348.0,13.49,9.16,320,500);
INSERT INTO "Ship" VALUES(5,'Cobra',36,114,1155.0,9.94,7.3,280,400);
INSERT INTO "Ship" VALUES(6,'Lakon Type 6',100,113,3455.0,29.36,15.64,220,329);
INSERT INTO "Ship" VALUES(7,'Lakon Type 9',440,1275,23720.0,18.22,13.34,130,200);
INSERT INTO "Ship" VALUES(8,'Anaconda',228,2600,52345.0,19.7,17.6,180,235);
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
INSERT INTO "ShipVendor" VALUES(1,1,0);
INSERT INTO "ShipVendor" VALUES(1,6,0);
INSERT INTO "ShipVendor" VALUES(2,1,0);
INSERT INTO "ShipVendor" VALUES(2,6,0);
INSERT INTO "ShipVendor" VALUES(3,1,0);
INSERT INTO "ShipVendor" VALUES(3,6,0);
INSERT INTO "ShipVendor" VALUES(4,1,0);
INSERT INTO "ShipVendor" VALUES(4,4,0);
INSERT INTO "ShipVendor" VALUES(4,6,0);
INSERT INTO "ShipVendor" VALUES(5,4,0);
INSERT INTO "ShipVendor" VALUES(5,6,0);
INSERT INTO "ShipVendor" VALUES(6,4,0);
INSERT INTO "ShipVendor" VALUES(6,6,0);
INSERT INTO "ShipVendor" VALUES(6,15,0);
INSERT INTO "ShipVendor" VALUES(7,4,0);
INSERT INTO "ShipVendor" VALUES(8,24,0);
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
INSERT INTO "Category" VALUES(1,'Chemicals');
INSERT INTO "Category" VALUES(2,'Consumer Items');
INSERT INTO "Category" VALUES(3,'Foods');
INSERT INTO "Category" VALUES(4,'Industrial Materials');
INSERT INTO "Category" VALUES(5,'Medicines');
INSERT INTO "Category" VALUES(6,'Metals');
INSERT INTO "Category" VALUES(7,'Minerals');
INSERT INTO "Category" VALUES(8,'Technology');
INSERT INTO "Category" VALUES(9,'Waste');
INSERT INTO "Category" VALUES(10,'Weapons');
INSERT INTO "Category" VALUES(11,'Drugs');
INSERT INTO "Category" VALUES(12,'Machinery');
INSERT INTO "Category" VALUES(13,'Textiles');
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
INSERT INTO "Item" VALUES(1,'Explosives',1);
INSERT INTO "Item" VALUES(2,'Hydrogen Fuels',1);
INSERT INTO "Item" VALUES(3,'Mineral Oil',1);
INSERT INTO "Item" VALUES(4,'Pesticides',1);
INSERT INTO "Item" VALUES(5,'Clothing',2);
INSERT INTO "Item" VALUES(6,'Consumer Tech',2);
INSERT INTO "Item" VALUES(7,'Dom. Appliances',2);
INSERT INTO "Item" VALUES(8,'Algae',3);
INSERT INTO "Item" VALUES(9,'Animal Meat',3);
INSERT INTO "Item" VALUES(10,'Coffee',3);
INSERT INTO "Item" VALUES(11,'Fish',3);
INSERT INTO "Item" VALUES(12,'Food Cartridges',3);
INSERT INTO "Item" VALUES(13,'Grain',3);
INSERT INTO "Item" VALUES(14,'Tea',3);
INSERT INTO "Item" VALUES(15,'Alloys',4);
INSERT INTO "Item" VALUES(16,'Plastics',4);
INSERT INTO "Item" VALUES(17,'Basic Medicines',5);
INSERT INTO "Item" VALUES(18,'Aluminium',6);
INSERT INTO "Item" VALUES(19,'Copper',6);
INSERT INTO "Item" VALUES(20,'Gold',6);
INSERT INTO "Item" VALUES(21,'Tantalum',6);
INSERT INTO "Item" VALUES(22,'Titanium',6);
INSERT INTO "Item" VALUES(23,'Bauxite',7);
INSERT INTO "Item" VALUES(24,'Coltan',7);
INSERT INTO "Item" VALUES(25,'Rutile',7);
INSERT INTO "Item" VALUES(26,'Advanced Catalysers',8);
INSERT INTO "Item" VALUES(27,'Animal Monitors',8);
INSERT INTO "Item" VALUES(28,'Aquaponic Systems',8);
INSERT INTO "Item" VALUES(29,'Computer Components',8);
INSERT INTO "Item" VALUES(30,'Robotics',8);
INSERT INTO "Item" VALUES(31,'Terrain Enrich Sys',8);
INSERT INTO "Item" VALUES(32,'Biowaste',9);
INSERT INTO "Item" VALUES(33,'Scrap',9);
INSERT INTO "Item" VALUES(34,'Reactive Armor',10);
INSERT INTO "Item" VALUES(35,'Personal Weapons',10);
INSERT INTO "Item" VALUES(36,'Liquor',11);
INSERT INTO "Item" VALUES(37,'Crop Harvesters',12);
INSERT INTO "Item" VALUES(38,'Marine Supplies',12);
INSERT INTO "Item" VALUES(39,'Cotton',13);
INSERT INTO "Item" VALUES(40,'Leather',13);
INSERT INTO "Item" VALUES(41,'Hel-Static Furnaces',12);
INSERT INTO "Item" VALUES(42,'Mineral Extractors',12);
INSERT INTO "Item" VALUES(43,'Progenitor Cells',5);
INSERT INTO "Item" VALUES(44,'Performance Enhancers',5);
INSERT INTO "Item" VALUES(45,'Agri-Medicines',5);
INSERT INTO "Item" VALUES(46,'Combat Stabilisers',5);
INSERT INTO "Item" VALUES(47,'Auto-Fabricators',8);
INSERT INTO "Item" VALUES(48,'H.E. Suits',8);
INSERT INTO "Item" VALUES(49,'Non-Lethal Wpns',10);
INSERT INTO "Item" VALUES(50,'Narcotics',11);
INSERT INTO "Item" VALUES(51,'Resonating Separators',8);
INSERT INTO "Item" VALUES(52,'Bertrandite',7);
INSERT INTO "Item" VALUES(53,'Bioreducing Lichen',8);
INSERT INTO "Item" VALUES(54,'Indite',7);
INSERT INTO "Item" VALUES(55,'Gallite',7);
INSERT INTO "Item" VALUES(56,'Lepidolite',7);
INSERT INTO "Item" VALUES(57,'Beer',11);
INSERT INTO "Item" VALUES(58,'Wine',11);
INSERT INTO "Item" VALUES(59,'Fruit and Vegetables',3);
INSERT INTO "Item" VALUES(60,'Synthetic Meat',3);
INSERT INTO "Item" VALUES(61,'Superconductors',4);
INSERT INTO "Item" VALUES(62,'Silver',6);
INSERT INTO "Item" VALUES(63,'Lithium',6);
INSERT INTO "Item" VALUES(64,'Palladium',6);
INSERT INTO "Item" VALUES(65,'Cobalt',6);
INSERT INTO "Item" VALUES(66,'Indium',6);
INSERT INTO "Item" VALUES(67,'Uranium',6);
INSERT INTO "Item" VALUES(68,'Gallium',7);
INSERT INTO "Item" VALUES(69,'Beryllium',7);
INSERT INTO "Item" VALUES(70,'Semiconductors',4);
INSERT INTO "Item" VALUES(71,'Polymers',4);
INSERT INTO "Item" VALUES(72,'Natural Fabrics',13);
INSERT INTO "Item" VALUES(73,'Synthetic Fabrics',13);
INSERT INTO "Item" VALUES(74,'Uraninite',7);
INSERT INTO "Item" VALUES(75,'Tobacco',11);
CREATE TABLE Price
 (
   item_id INTEGER NOT NULL,
   station_id INTEGER NOT NULL,
   ui_order INTEGER NOT NULL DEFAULT 0,
   -- how many credits will the station pay for this item?
   sell_to INTEGER NOT NULL,
   -- how many credits must you pay to buy at this station?
   buy_from INTEGER NOT NULL DEFAULT 0,
   modified DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,

   PRIMARY KEY (item_id, station_id),

   FOREIGN KEY (item_id) REFERENCES Item(item_id)
   	ON UPDATE CASCADE
      ON DELETE CASCADE,
   FOREIGN KEY (station_id) REFERENCES Station(station_id)
   	ON UPDATE CASCADE
      ON DELETE CASCADE
 ) WITHOUT ROWID
;
DELETE FROM sqlite_sequence;
INSERT INTO "sqlite_sequence" VALUES('System',55);
INSERT INTO "sqlite_sequence" VALUES('Station',39);
INSERT INTO "sqlite_sequence" VALUES('Ship',8);
INSERT INTO "sqlite_sequence" VALUES('Category',13);
INSERT INTO "sqlite_sequence" VALUES('Item',75);
CREATE INDEX systems_position ON System (pos_x, pos_y, pos_z);
CREATE INDEX station_systems ON Station (system_id);
COMMIT;
