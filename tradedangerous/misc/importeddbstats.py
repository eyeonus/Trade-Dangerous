import csvexport
import misc.eddb
import tradedb

# Build an ID=>Name mapping for EDDB systems
tdb = tradedb.TradeDB()
systems = {}
tdSysLookup = tdb.systemByName.get
for s in misc.eddb.SystemsQuery():
    tdSys = tdSysLookup(s['name'].upper(), None)
    if tdSys and tdSys.stations:
        systems[s['id']] = { stn.dbname.upper(): stn for stn in tdSys.stations }

def matching_stations():
    # generator that searches the eddb station set for entries that
    # match tdb entries and yields the tuple (tdStn, eddbStn)
    
    for eddbStn in misc.eddb.StationsQuery():
        stationList = systems.get(eddbStn['system_id'], None)
        if not stationList:
            continue
        name = eddbStn['name'].upper()
        tdStn = stationList.get(name, None)
        if tdStn:
            yield tdStn, eddbStn


updateStation = tdb.updateLocalStation

bool_trans = { None: '?', 0: 'N', 1: 'Y' }

updates = 0
for tdStn, eddbStn in matching_stations():
    mps = eddbStn['max_landing_pad_size'] or '?'
    if updateStation(
            station=tdStn,
            lsFromStar=eddbStn['distance_to_star'],
            maxPadSize=mps,
            market=bool_trans[eddbStn['has_commodities']],
            blackMarket=bool_trans[eddbStn['has_blackmarket']],
            shipyard=bool_trans[eddbStn['has_shipyard']],
            outfitting=bool_trans[eddbStn['has_outfitting']],
            rearm=bool_trans[eddbStn['has_rearm']],
            refuel=bool_trans[eddbStn['has_refuel']],
            repair=bool_trans[eddbStn['has_repair']],
            modified='now',
            commit=False,
            ):
        updates += 1

if updates:
    tdb.getDB().commit()
    csvexport.exportTableToFile(tdb, tdb.tdenv, "Station")
    print("Updated Station.csv: {} updates".format(updates))
