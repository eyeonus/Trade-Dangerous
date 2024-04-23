"""
Utilities for reading from the Elite Dangerous Data Network.

Example usages:
    
    # Simple:
    import eddn
    listener = eddn.Listener()
    while True:
        batch = listener.get_batch()
        if batch:
            print("Got batch of %d" % len(batch))
    
    # Advanced:
    import eddn
    
    listener = eddn.Listener(
        minBatchTime=3,         # Allow at least 3-s for a batch,
        maxBatchTime=5,         # But allow upto 5s,
        reconnectTimeout=300,   # Reconnect after 5 minutes without data,
        burstLimit=500,         # Drain upto 500 prices between polls,
    )
    
    def handle_listener_error(e):
        print("Listener Error:", e)
    
    def process_batch(batch):
        stations = set()
        items = set()
        software = set()
        for price in batch:
            stations.add(price.station)
            items.add(price.item)
            software.add(price.software + ":" + price.version)
        print("Batch: %d entries" % len(batch))
        print("Stations: %s" % (','.join(stations)))
        print("Items: %s" % (','.join(items)))
    
    print("Listening for 100 batches")
    while listener.stats['batches'] < 100:
        batch = listener.get_batch(onerror=handle_listener_error)
        if batch:
            process_batch(batch)
        stats, errors = listener.stats, listener.errors
        if errors or (listener.stats['batches'] % 5) == 0:
            print("Stats:")
            for stat in sorted(stats.keys()):
                print("  {:<20s} {:>10n}".format(stat, stats[stat]))
        if errors:
            print("ERRORS:")
            for error in sorted(errors.keys()):
                print("  {:<20s} {:>10n}".format(error, errors[error]))
            listener.clear_errors()
    
    listener.reset_counters()
"""

# Copyright (C) Oliver 'kfsone' Smith <oliver@kfs.org> 2015
#
# Conditional permission to copy, modify, refactor or use this
# code is granted so long as attribution to the original author
# is included.

import json
import time
import zlib
import zmq

from collections import defaultdict
from collections import namedtuple


class MarketPrice(namedtuple('MarketPrice', [
        'system',
        'station',
        'item',
        'buy',
        'sell',
        'demand',
        'supply',
        'timestamp',
        'uploader',
        'software',
        'version',
        ])):
    pass


class Listener:
    """
    Provides an object that will listen to the Elite Dangerous Data Network
    firehose and capture messages for later consumption.
    
    Rather than individual updates, prices are captured across a window of
    between minBatchTime and maxBatchTime. When a new update is received,
    Rather than returning individual messages, messages are captured across
    a window of potentially several seconds and returned to the caller in
    batches.
    
    Attributes:
        zmqContext          Context this object is associated with,
        minBatchTime        Allow at least this long for a batch (ms),
        maxBatchTime        Don't allow a batch to run longer than this (ms),
        reconnectTimeout    Reconnect the socket after this long with no data,
        burstLimit          Read a maximum of this many messages between
                            timer checks
        
        subscriber          ZMQ socket we're using
        stats               Counters of nominal events
        errors              Counters of off-nominal events
        lastRecv            time of the last receive (or 0)
    """
    
    uri = 'tcp://eddn-relay.elite-markets.net:9500'
    supportedSchema = 'http://schemas.elite-markets.net/eddn/commodity/1'
    
    def __init__(
        self,
        zmqContext=None,
        minBatchTime=5.,    # seconds
        maxBatchTime=10.,   # seconds
        reconnectTimeout=180.,  # seconds
        burstLimit=200,
    ):
        assert burstLimit > 0
        if not zmqContext:
            zmqContext = zmq.Context()
        self.zmqContext = zmqContext
        self.subscriber = None
        
        self.minBatchTime = minBatchTime
        self.maxBatchTime = maxBatchTime
        self.reconnectTimeout = reconnectTimeout
        self.burstLimit = burstLimit
        
        self.reset_counters()
        self.connect()


    def connect(self):
        """
        Start a connection
        """
        # tear up the new connection first
        if self.subscriber:
            self.subscriber.close()
            del self.subscriber
        self.subscriber = newsub = self.zmqContext.socket(zmq.SUB)
        newsub.setsockopt(zmq.SUBSCRIBE, b"")
        newsub.connect(self.uri)
        self.lastRecv = time.time()
        self.lastJsData = None


    def disconnect(self):
        del self.subscriber


    def clear_errors(self):
        self.errors = defaultdict(int)


    def reset_counters(self):
        self.clear_errors()
        self.stats = defaultdict(int)


    def wait_for_data(self, softCutoff, hardCutoff):
        """
        Waits for data until maxBatchTime ms has elapsed
        or cutoff (absolute time) has been reached.
        """
        
        now = time.time()
        
        cutoff = min(softCutoff, hardCutoff)
        if self.lastRecv < now - self.reconnectTimeout:
            if self.lastRecv:
                self.errors['reconnects'] += 1
            self.connect()
            now = time.time()
        
        nextCutoff = min(now + self.minBatchTime, cutoff)
        if now > nextCutoff:
            return False
        
        timeout = (nextCutoff - now) * 1000     # milliseconds
        
        # Wait for an event
        events = self.subscriber.poll(timeout=timeout)
        if events == 0:
            return False
        return True


    def get_batch(self, onerror=None):
        """
        Greedily collect deduped prices from the firehose over a
        period of between minBatchTime and maxBatchTime, with
        built-in auto-reconnection if there is nothing from the
        firehose for a period of time.
        
        As json data is decoded, it is stored in self.lastJsData.
        
        Parameters:
            onerror
                None or a function/lambda that takes an error
                string and deals with it.
        
        Returns:
            A list of MarketPrice entries based on the data read.
            Prices are deduped per System+Station+Item, so that
            if two entries are received for the same combination,
            only the most recent with the newest timestamp is kept.
        
        Errors:
            Errors are acculumated in the .errors dictionary. If you
            supply an 'onerror' function they are also passed to it.
        """
        now = time.time()
        hardCutoff = now + self.maxBatchTime
        softCutoff = now + self.minBatchTime
        
        # hoists
        supportedSchema = self.supportedSchema
        sub = self.subscriber
        stats, errors = self.stats, self.errors
        
        # Prices are stored as a dictionary of
        # (sys,stn,item) => [MarketPrice]
        # The list thing is a trick to save us having to do
        # the dictionary lookup twice.
        batch = defaultdict(list)
        
        while self.wait_for_data(softCutoff, hardCutoff):
            # When wait_for_data returns True, there is some data waiting,
            # possibly multiple messages. At this point we can afford to
            # suck down whatever is waiting in "nonblocking" mode until
            # we reach the burst limit or we get EAGAIN.
            bursts = 0
            for _ in range(self.burstLimit):
                self.lastJsData = None
                try:
                    zdata = sub.recv(flags=zmq.NOBLOCK, copy=False)
                    stats['recvs'] += 1
                except zmq.error.Again:
                    break
                
                bursts += 1
                
                try:
                    jsdata = zlib.decompress(zdata)
                except Exception as e:
                    errors['deflate'] += 1
                    if onerror:
                        onerror("zlib.decompress: %s: %s"%(type(e), e))
                    continue
                
                bdata = jsdata.decode()
                
                try:
                    data = json.loads(bdata)
                except ValueError as e:
                    errors['loads'] += 1
                    if onerror:
                        onerror("json.loads: %s: %s"%(type(e), e))
                    continue
                
                self.lastJsData = jsdata
                
                try:
                    schema = data["$schemaRef"]
                except KeyError:
                    errors['schemaref'] += 1
                    if onerror:
                        onerror("missing schema ref")
                    continue
                if schema != supportedSchema:
                    errors['schema'] += 1
                    if onerror:
                        onerror("unsupported schema: "+schema)
                    continue
                try:
                    header = data["header"]
                    message = data["message"]
                    system = message["systemName"].upper()
                    station = message["stationName"].upper()
                    item = message["itemName"].upper()
                    buy = int(message["buyPrice"])
                    sell = int(message["sellPrice"])
                    demand = message["demand"]
                    supply = message["stationStock"]
                    timestamp = message["timestamp"]
                    uploader = header["uploaderID"]
                    software = header["softwareName"]
                    swVersion = header["softwareVersion"]
                except (KeyError, ValueError) as e:
                    errors['json'] += 1
                    if onerror:
                        onerror("invalid json: %s: %s"%(type(e), e))
                    continue
                
                # We've received real data.
                stats['prices'] += 1
                
                # Normalize timestamps
                timestamp = timestamp.replace("T"," ").replace("+00:00","")
                
                # We'll get either an empty list or a list containing
                # a MarketPrice. This saves us having to do the expensive
                # index operation twice.
                oldEntryList = batch[(system, station, item)]
                if oldEntryList:
                    if oldEntryList[0].timestamp > timestamp:
                        stats['timeseq'] += 1
                        continue
                    stats['timeseq']
                else:
                    # Add a blank entry to make the list size > 0
                    oldEntryList.append(None)
                
                # Here we're replacing the contents of the list.
                # This simple array lookup is several hundred times less
                # expensive than looking up a potentially large dictionary
                # by STATION/SYSTEM:ITEM...
                oldEntryList[0] = MarketPrice(
                    system, station, item,
                    buy, sell,
                    demand, supply,
                    timestamp,
                    uploader, software, swVersion,
                )
            
            # For the edge-case where we wait 4.999 seconds and then
            # get a burst of data: stick around a little longer.
            if bursts >= self.burstLimit:
                stats['numburst'] += 1
                stats['maxburst'] = max(stats['maxburst'], bursts)
                softCutoff = min(softCutoff, time.time() + 0.5)
        
        # to get average batch length, divide batchlen/batches.
        # you could do the same with prices/batches except that
        stats['batches'] += 1
        if not batch:
            stats['emptybatches'] += 1
        else:
            stats['batchlen'] += len(batch)
        
        return [ entry[0] for entry in batch.values() ]
