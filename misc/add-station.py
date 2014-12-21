#! /usr/bin/env python

import sys
import re


argStr = ' '.join(sys.argv[1:])
m = re.match(r'^(.*)/(.*)(\:([\d]+))?', argStr)
sys, stn, dist = m.group(1, 2, 3)
sys = sys.title()
stn = stn.title()
dist = int(dist)

import sqlite3
conn = sqlite3.connect("data/TradeDangerous.db")
cur = conn.cursor()

system_id = cur.execute("""
    SELECT  system_id
      FROM  System
     WHERE  name like ?
""", [sys]).fetchone()[0]

matches = cur.execute("""
    SELECT  COUNT(*)
      FROM  Station
     WHERE  system_id = ?
       AND  name like ?
""", [system_id, stn]).fetchone()[0]
if matches > 0:
    raise Exception("Station already exists.")

cur.execute("""
    INSERT  INTO Station
            (system_id, name, ls_from_star)
    VALUES  (?, ?, ?)
""", [system_id, stn, dist])
conn.commit()

print("ADDED: {}/{}:{}ls".format(sys, stn, dist))
print("You'll need to regenerate your Station.csv or lose your data.")
print("  trade.py export --table Station")

