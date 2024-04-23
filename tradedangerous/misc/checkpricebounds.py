#! /usr/bin/env python

from collections import defaultdict
import argparse
import colorama
import tradedb
import tradeenv
import sys

colorama.init()

def check_price_bounds(
        tdb,
        table,
        margin=25,
        deletePrices="tmp/deletions.prices",
        deleteSql="tmp/deletions.sql",
        doDeletions=False,
        percentile=5,
        errorFilter=None,
        ):
    assert isinstance(percentile, (int,float))
    assert percentile >= 0.01 and percentile < 50
    
    lowP = percentile / 100
    highP = 1 - lowP
    
    mask = "{:>7}:{:<28}|{:>8}|{:>8}|{:>8}|{:>8}|{:>8}|{:>8}|{:>8}|{:>8}|{:>8} {}"
    header = "{}:\n".format(table)
    header += mask.format(
        "#prices", "name",
        "p0", "low", "p{}".format(percentile),
        "p50", "avg", "midavg",
        "p{}".format(100-percentile), "high", "p100",
        ""
    )
    header += "\n" + '-' * len(header)
    print(header)
    
    deletions = []
    stations = defaultdict(list)
    
    def remediation(item, compare, value):
        deletion = (
            "DELETE FROM {} "
            "WHERE item_id = {} "
            "AND price > 0 AND price {} {}".format(
                table, item.ID, compare, value
        ))
        deletions.append((deletion, "{}".format(item.dbname)))
        count = 0
        for (stnID,) in tdb.query("""
                    SELECT station_id FROM {}
                     WHERE item_id = {} AND price > 0 AND price {} {}
                """.format(
                    table, item.ID, compare, value,
                )):
            stations[stnID].append((item.ID, compare, value))
            count += 1
        return count
    
    # Distance between p50 and p5 or p95 is 45.
    # We use multiplier to expand projections so that our thresholds
    # behave as though they are pX to p50+M instead of pX to p50.
    multiplier = (50 + margin) / (50 - lowP)
    
    for item in tdb.itemByID.values():
        if item.dbname.upper() in tdb.tdenv.ignore:
            continue
        cur = tdb.query("""
            SELECT price
              FROM {}
             WHERE item_id = ?
               AND price > 0
        """.format(table), [item.ID])
        prices = [ row[0] for row in cur ]
        if not prices:
            if tdb.tdenv.detail:
                tdb.tdenv.NOTE("{}: Zero entries", item.dbname)
            continue
        prices.sort()
        numPrices = len(prices)
        if numPrices < 20:
            tdb.tdenv.NOTE("{}: only {} rows", item.dbname, numPrices)
            continue
        
        lowPos = int(numPrices * lowP)
        midPos = int(numPrices * 0.5)
        highPos = int(numPrices * highP)
        
        low = prices[lowPos]
        mid = prices[midPos]
        high = prices[highPos]
        
        avg = int(sum(prices) / numPrices)
        midlist = prices[lowPos:highPos]
        midavg = int(sum(midlist) / len(midlist))
        
        # project the line from p50->p5 to predict
        # what we would expect p0 to be.
        # prices under 11 are invalid anyway
        bestMid = max(mid, avg)
        leastMid = min(mid, avg)
        lowCutoff = max(int(leastMid - (bestMid - low) * multiplier), 0)
        highCutoff = int(bestMid + (high - leastMid) * multiplier)
        
        if prices[0] < 11:
            alert = colorama.Fore.RED
            comp, cutoff, error = '<', 11, 'DUMB'
        elif prices[0] < lowCutoff:
            alert = colorama.Fore.YELLOW
            comp, cutoff, error = '<', lowCutoff, 'LOW'
        elif prices[-1] > 100 and prices[-1] > highCutoff:
            alert = colorama.Fore.CYAN
            comp, cutoff, error = '>', highCutoff, 'HIGH'
        else:
            continue
        
        if errorFilter and error != errorFilter:
            continue
        
        count = remediation(item, comp, cutoff)
        print(
            alert,
            mask.format(
                numPrices,
                item.dbname,
                prices[0],
                lowCutoff,
                low, 
                mid,
                avg,
                midavg,
                high,
                highCutoff,
                prices[-1],
                '{:<4s} {:>4n}'.format(error, count),
            ),
            colorama.Fore.RESET,
            sep="",
        )
    
    if stations:
        print()
        print("Generating", deletePrices)
        now = tdb.query("SELECT CURRENT_TIMESTAMP").fetchone()[0]
        with open(deletePrices, "w", encoding="utf-8") as fh:
            print("# Deletions based on {} prices".format(
                table,
            ), file=fh)
            for stnID, items in stations.items():
                station = tdb.stationByID[stnID]
                print(file=fh)
                print("@ {}".format(station.name()), file=fh)
                for item in items:
                    itemID = item[0]
                    print("      {:<30} {:>7} {:>7} {:>9} {:>9} {}  # was {} {}"
                        .format(
                            tdb.itemByID[itemID].name(),
                            0, 0,
                            '-', '-',
                            now,
                            item[1], item[2],
                        ), file=fh
                    )
        if doDeletions:
            db = tdb.getDB()
        print("Generating", deleteSql)
        with open(deleteSql, "w", encoding="utf-8") as fh:
            for deletion in deletions:
                print(deletion[0], '; --', deletion[1], file=fh)
                if doDeletions:
                    db.execute(deletion[0])
            if doDeletions:
                db.commit()

def main():
    parser = argparse.ArgumentParser(
        description='Check for prices that are outside reasonable bounds.'
    )
    parser.add_argument(
        '--percentile',
        help='Set cutoff percentile',
        type=float,
        default=2,
    )
    parser.add_argument(
        '--selling',
        help='Check the StationSelling table instead of StationBuying',
        action='store_true',
    )
    parser.add_argument(
        '--delete',
        help='Remove bad elements from the local .db immediately',
        action='store_true',
        default=False,
    )
    parser.add_argument(
        '--db',
        help='Specify location of the SQLite database.',
        default=None,
        dest='dbFilename',
        type=str,
    )
    parser.add_argument(
        '--debug', '-w',
        help='Enable/raise level of diagnostic output.',
        default=0,
        required=False,
        action='count',
    )
    parser.add_argument(
        '--detail', '-v',
        help='Increase level  of detail in output.',
        default=0,
        required=False,
        action='count',
    )
    parser.add_argument(
        '--quiet', '-q',
        help='Reduce level of detail in output.',
        default=0,
        required=False,
        action='count',
    )
    parser.add_argument(
        '--margin',
        help='Adjust the error margin.',
        type=int,
        default=25,
    )
    parser.add_argument(
        '--ignore',
        help='Ignore items.',
        action='append',
        default=list(),
    )
    
    filters = parser.add_mutually_exclusive_group()
    filters.add_argument(
        '--dumb',
        help='Limit to "DUMB" items (<11cr).',
        dest='filters',
        action='store_const',
        const='DUMB',
    )
    filters.add_argument(
        '--high',
        help='Limit to "HIGH" items.',
        dest='filters',
        action='store_const',
        const='HIGH',
    )
    filters.add_argument(
        '--low',
        help='Limit to "LOW" items.',
        dest='filters',
        action='store_const',
        const='LOW',
    )
    
    argv = parser.parse_args(sys.argv[1:])
    argv.ignore = [
        ignore.upper() for ignore in argv.ignore
    ]
    
    table = "StationSelling" if argv.selling else "StationBuying"
    tdenv = tradeenv.TradeEnv(properties=argv)
    tdb = tradedb.TradeDB(tdenv)
    
    tdenv.NOTE(
        "Checking {}, margin={}", table, argv.margin,
    )
    
    errorFilter = getattr(argv, "filters", None)
    check_price_bounds(
        tdb,
        table,
        margin=argv.margin,
        doDeletions=argv.delete,
        percentile=argv.percentile,
        errorFilter=errorFilter,
    )


if __name__ == "__main__":
    main()
