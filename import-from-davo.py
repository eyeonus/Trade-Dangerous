#! /usr/bin/env python

############################### CAUTION ############################### 
#
# Forget Draegons, here be aliens with nasty, sharp, pointy-teeth.
#
# This is a completely experimental module that downloads the
# latest .prices file from maddavos.
#
# By default it asks his site to generate a new one first, which
# is probably a bit expensive for him. Use -g to just download
# whatever was most recent.
#
# The downloaded file is called "davek.prices". Specify -d if you
# don't want it lying around after it imported.
#
# Specify -i if you want to ignore unknown stations rather than
# fail to import.
#
# Specify -T if you want to just download the file without importing.
#
# Specify -w to increase debug output.
#
############################### CAUTION ############################### 

from urllib.parse import urlencode
from urllib.request import Request, urlopen
import os, pathlib, re, sys
import tradedb
import cache


site = "http://www.davek.com.au/td/"


def generate():
    url = site + "default.asp"
    data = urlencode({"state":"download", "filetype":"tradedangerous"})
    headers = { "Content-Type": "application/x-www-form-urlencoded", }
    req = Request(url, data.encode('utf-8'), headers)

    f = urlopen(req)
    data = f.read().decode()

    if not re.search(r"File Created", data):
        raise SystemExit("No 'File Created' in result.")

    m = re.search(r"document\.location\.href\s*=\s*[\"'](.*?)[\"']", data)
    if not m:
        raise SystemExit("No filename in result.")

    print("got", m.group(1))

    return m.group(1)


def download(filename=None):
    filename = filename or "tmp/TradeDangerous.prices"
    url = site + filename
    req = Request(url)

    f = urlopen(req)
    data = f.read().decode()

    dstFile = "davek.prices"
    with open(dstFile, "w") as fh:
        print(data, file=fh)

    return dstFile


if __name__ == "__main__":
    opt_debug = 0
    opt_generate = False
    opt_unlink = False
    opt_test = False
    opt_ignoreUnk = False

    for i in range(1, len(sys.argv)):
        if sys.argv[i] == '-w':
            opt_debug += 1
        elif sys.argv[i] == '-g':
            opt_generate = True
        elif sys.argv[i] == '-d':
            opt_unlink = True
        elif sys.argv[i] == '-T':
            opt_test = True
        elif sys.argv[i] == '-i':
            opt_ignoreUnk = True
        else:
            raise SystemExit("Unknown argument: "+sys.argv[i])

    if opt_generate:
        print("generate")
        file = generate()
    else:
        file = "tmp/TradeDangerous.prices"

    print("download")
    priceFile = download(file)


    if not opt_test:
        print("import")
        tdb = tradedb.TradeDB(debug=opt_debug, buildLinks=False, includeTrades=False)
        if opt_ignoreUnk:
            tdb.tdenv.ignoreUnkown = True
        cache.importDataFromFile(tdb, tdb.tdenv, pathlib.Path(priceFile))

    if opt_debug:
        print("done")

