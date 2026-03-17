# ----------------------------------------------------------------
# Import plugin that downloads market and ship vendor data from the
# Elite Dangerous mobile API.
# ----------------------------------------------------------------

import hashlib
import json
import pathlib
import random
import requests
import time
import base64
import webbrowser
import configparser

from datetime import datetime, timezone
from collections import namedtuple
from http import HTTPStatus
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit, parse_qs

from .. import cache, csvexport, plugins, mapping, fs

import secrets

__version_info__ = (5, 0, 2)
__version__ = '.'.join(map(str, __version_info__))

# ----------------------------------------------------------------
# Deal with some differences in names between TD, ED and the API.
# ----------------------------------------------------------------

bracket_levels = ('?', 'L', 'M', 'H')

# Categories to ignore. Drones end up here. No idea what they are.
cat_ignore = [
    'NonMarketable',
]


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        split_url = urlsplit(self.path)
        if split_url.path == "/callback":
            parsed_url = parse_qs(split_url.query)
            self.server.callback_code = parsed_url.get("code", [None])[0]
            self.server.callback_state = parsed_url.get("state", [None])[0]
            self.send_response(HTTPStatus.OK)
            body_text = b"<p>You can close me now.</p>"
        else:
            self.send_response(HTTPStatus.NOT_IMPLEMENTED)
            body_text = b"<p>Something went wrong.</p>"
        self.end_headers()
        self.wfile.write(b"<html><head><title>EDAPI Frontier Login</title></head>")
        self.wfile.write(b"<body><h1>AUTHENTICATION</h1>")
        self.wfile.write(body_text)
        self.wfile.write(b"</body></html>")
    
    def log_message(self, format, *args):
        pass


class OAuthCallbackServer:
    def __init__(self, hostname, port, handler):
        myServer = HTTPServer
        myServer.callback_code = None
        myServer.callback_state = None
        self.httpd = myServer((hostname, port), handler)
        self.httpd.handle_request()
        self.httpd.server_close()


class EDAPI:
    '''
    A class that handles the Frontier ED API.
    '''
    
    _agent = "EDCD-TradeDangerousPluginEDAPI-%s" % __version__
    _basename = 'edapi'
    _configfile = _basename + '.config'
    
    def __init__(
        self,
        basename = 'edapi',
        debug = False,
        configfile = None,
        json_file = None,
        login = False
    ):
        '''
        Initialize
        '''
        
        # Build common file names from basename.
        self._basename = basename
        if configfile:
            self._configfile = configfile
        
        self.debug = debug
        self.login = login
        
        # If json_file was given, just load that instead.
        if json_file:
            with open(json_file) as file:
                self.profile = json.load(file)
                return
        
        # Setup the session.
        self.opener = requests.Session()
        
        # Setup config
        self.config = configparser.ConfigParser()
        self.config.read_dict({
            "frontier": {
                "AUTH_URL": "https://auth.frontierstore.net",
                "AUTH_URL_AUTH": "https://auth.frontierstore.net/auth",
                "AUTH_URL_TOKEN": "https://auth.frontierstore.net/token",
            },
            "companion": {
                "CAPI_LIVE_URL": "https://companion.orerve.net",
                "CAPI_BETA_URL": "https://pts-companion.orerve.net",
                "CLIENT_ID": "0d60c9fe-1ae3-4849-91e9-250db5de9d79",
                "REDIRECT_URI": "http://127.0.0.1:2989/callback",
            },
            "authorization": {}
        })
        self._authorization_set_config({})
        self.config.read(self._configfile)
        
        # If force login, kill the authorization
        if self.login:
            self._authorization_set_config({})
        
        # Grab the commander profile
        self.text = []
        self.profile = self.query_capi("/profile")
        
        # kfsone: not sure if there was a reason to query these even tho we didn't
        # use the resulting data.
        # market = self.query_capi("/market")
        # shipyard = self.query_capi("/shipyard")
        
        # Grab the market, outfitting and shipyard data if needed
        portServices = self.profile['lastStarport'].get('services')
        if self.profile['commander']['docked'] and portServices:
            if portServices.get('commodities'):
                res = self.query_capi("/market")
                if int(res["id"]) == int(self.profile["lastStarport"]["id"]):
                    self.profile["lastStarport"].update(res)
            hasShipyard = portServices.get('shipyard')
            if hasShipyard or portServices.get('outfitting'):
                # the ships for the shipyard are not always returned the first time
                for attempt in range(3):
                    # try up to 3 times
                    res = self.query_capi("/shipyard")
                    if not hasShipyard or res.get('ships'):
                        break
                    if self.debug:
                        print("No shipyard in response, I'll try again in 5s")
                    time.sleep(5)
                if int(res["id"]) == int(self.profile["lastStarport"]["id"]):
                    self.profile["lastStarport"].update(res)
    
    def query_capi(self, capi_endpoint):
        self._authorization_check()
        response = self.opener.get(self.config["companion"]["CAPI_LIVE_URL"] + capi_endpoint)
        try:
            print(response.text)
            data = response.json()
            self.text.append(response.text)
        except:
            if self.debug:
                print('   URL:', response.url)
                print('status:', response.status_code)
                print('  text:', response.text)
                txtDebug = ""
            else:
                txtDebug = "\nTry with --debug and report this."
            raise plugins.PluginException(
                "Unable to parse JSON response for {}!"
                "\nTry to relogin with the 'login' option."
                "{}".format(capi_endpoint, txtDebug)
            )
        return data
    
    def _authorization_check(self):
        status_ok = True
        expires_at = self.config.getint("authorization", "expires_at")
        if self.debug:
            print("auth expires_at", time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expires_at)))
        if (expires_at - time.time()) < 60:
            if self.debug:
                print("authorization expired")
            status_ok = False
            if self.config["authorization"]["refresh_token"]:
                status_ok = self._authorization_refresh()
            if not status_ok:
                status_ok = self._authorization_login()
            with open(self._configfile, "w") as c:
                self.config.write(c)
        
        if not status_ok:
            # Something terrible happend
            raise plugins.PluginException("Couldn't get frontier authorization.")
        
        # Setup session authorization
        self.opener.headers = {
            'User-Agent': self._agent,
            'Authorization': "%s %s" % (
                self.config['authorization']['token_type'],
                self.config['authorization']['access_token'],
            ),
        }
    
    def _authorization_set_config(self, auth_data):
        self.config.set("authorization", "access_token", auth_data.get("access_token", ""))
        self.config.set("authorization", "token_type", auth_data.get("token_type", ""))
        self.config.set("authorization", "expires_at", str(auth_data.get("expires_at", 0)))
        self.config.set("authorization", "refresh_token", auth_data.get("refresh_token", ""))
    
    def _authorization_token(self, data):
        expires_at = int(time.time())
        res = requests.post(self.config["frontier"]["AUTH_URL_TOKEN"], data = data)
        if self.debug:
            print(res, res.url)
            print(res.text)
        if res.status_code == requests.codes.ok:  # pylint: disable=no-member
            auth_data = res.json()
            auth_data['expires_at'] = expires_at + int(auth_data.get('expires_in', 0))
            self._authorization_set_config(auth_data)
            return True
        self._authorization_set_config({})
        return False
    
    def _authorization_refresh(self):
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.config["authorization"]["refresh_token"],
            "client_id": self.config["companion"]["CLIENT_ID"],
        }
        return self._authorization_token(data)
    
    def _authorization_login(self):
        session_state = secrets.token_urlsafe(36)
        code_verifier = secrets.token_urlsafe(36)
        code_digest = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(code_digest).decode().rstrip("=")
        data = {
            'response_type': 'code',
            'redirect_uri': self.config["companion"]["REDIRECT_URI"],
            'client_id': self.config["companion"]["CLIENT_ID"],
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            'state': session_state,
        }
        req = requests.Request("GET", self.config["frontier"]["AUTH_URL_AUTH"], params = data)
        pre = req.prepare()
        webbrowser.open_new_tab(pre.url)
        
        redirect_uri = urlsplit(self.config["companion"]["REDIRECT_URI"])
        oauth = OAuthCallbackServer(redirect_uri.hostname, redirect_uri.port, OAuthCallbackHandler)
        if oauth.httpd.callback_code and oauth.httpd.callback_state == session_state:
            data = {
                "grant_type": "authorization_code",
                "code": oauth.httpd.callback_code,
                "code_verifier": code_verifier,
                "client_id": self.config["companion"]["CLIENT_ID"],
                "redirect_uri": self.config["companion"]["REDIRECT_URI"],
            }
            return self._authorization_token(data)
        return False


class EDDN:
    _gateways = (
        'https://eddn.edcd.io:4430/upload/',
        # 'http://eddn-gateway.ed-td.space:8080/upload/',
    )
    
    _commodity_schemas = {
        'production': 'https://eddn.edcd.io/schemas/commodity/3',
        'test': 'https://eddn.edcd.io/schemas/commodity/3/test',
    }
    
    _shipyard_schemas = {
        'production': 'https://eddn.edcd.io/schemas/shipyard/2',
        'test': 'https://eddn.edcd.io/schemas/shipyard/2/test',
    }
    
    _outfitting_schemas = {
        'production': 'https://eddn.edcd.io/schemas/outfitting/2',
        'test': 'https://eddn.edcd.io/schemas/outfitting/2/test',
    }
    
    _debug = True
    
    # As of 1.3, ED reports four levels.
    _levels = (
        'Low',
        'Low',
        'Med',
        'High',
    )
    
    def __init__(
        self,
        uploaderID,
        noHash,
        softwareName,
        softwareVersion
    ):
        # Obfuscate uploaderID
        if noHash:
            self.uploaderID = uploaderID
        else:
            self.uploaderID = hashlib.sha1(uploaderID.encode('utf-8')).hexdigest()
        self.softwareName = softwareName
        self.softwareVersion = softwareVersion
    
    def postMessage(
        self,
        message,
        timestamp = 0
    ):
        if timestamp:
            timestamp = datetime.fromtimestamp(timestamp).isoformat()
        else:
            timestamp = datetime.now(timezone.utc).astimezone().isoformat()
        
        message['message']['timestamp'] = timestamp
        
        url = random.choice(self._gateways)
        
        headers = {
            'content-type': 'application/json; charset=utf8'
        }
        
        if self._debug:
            print(
                json.dumps(
                    message,
                    sort_keys = True,
                    indent = 4
                )
            )
        
        r = requests.post(
            url,
            headers = headers,
            data = json.dumps(
                message,
                ensure_ascii = False
            ).encode('utf8'),
            verify = True
        )
        
        r.raise_for_status()
    
    def publishCommodities(
        self,
        systemName,
        stationName,
        marketId,
        commodities,
        additional = None,
        timestamp = 0
    ):
        message = {}
        
        message['$schemaRef'] = self._commodity_schemas[('test' if self._debug else 'production')]  # NOQA
        
        message['header'] = {
            'uploaderID': self.uploaderID,
            'softwareName': self.softwareName,
            'softwareVersion': self.softwareVersion
        }
        
        message['message'] = {
            'systemName': systemName,
            'stationName': stationName,
            'marketId': marketId,
            'commodities': commodities,
        }
        if additional:
            message['message'].update(additional)
        
        self.postMessage(message, timestamp)
    
    def publishShipyard(
        self,
        systemName,
        stationName,
        marketId,
        ships,
        timestamp = 0
    ):
        message = {}
        
        message['$schemaRef'] = self._shipyard_schemas[('test' if self._debug else 'production')]  # NOQA
        
        message['header'] = {
            'uploaderID': self.uploaderID,
            'softwareName': self.softwareName,
            'softwareVersion': self.softwareVersion
        }
        
        message['message'] = {
            'systemName': systemName,
            'stationName': stationName,
            'marketId': marketId,
            'ships': ships,
        }
        
        self.postMessage(message, timestamp)
    
    def publishOutfitting(
        self,
        systemName,
        stationName,
        marketId,
        modules,
        timestamp = 0
    ):
        message = {}
        
        message['$schemaRef'] = self._outfitting_schemas[('test' if self._debug else 'production')]  # NOQA
        
        message['header'] = {
            'uploaderID': self.uploaderID,
            'softwareName': self.softwareName,
            'softwareVersion': self.softwareVersion
        }
        
        message['message'] = {
            'systemName': systemName,
            'stationName': stationName,
            'marketId': marketId,
            'modules': modules,
        }
        
        self.postMessage(message, timestamp)


class ImportPlugin(plugins.ImportPluginBase):
    """
    Plugin that downloads market and ship vendor data from the Elite Dangerous
    mobile API.
    """
    
    pluginOptions = {
        'csvs': 'Merge shipyards into ShipVendor.csv.',
        'edcd': 'Call the EDCD plugin first.',
        'eddn': 'Post market, shipyard and outfitting to EDDN.',
        'name': 'Do not obfuscate commander name for EDDN submit.',
        'save': 'Save the API response (tmp/profile.YYYYMMDD_HHMMSS.json).',
        'tdh': 'Save the API response for TDH (tmp/tdh_profile.json).',
        'test': 'Test the plugin with a json file (test=[FILENAME]).',
        'warn': 'Ask for station update if a API<->DB diff is encountered.',
        'login': 'Ask for login credentials.',
    }
    
    configFile = "edapi.config"
    
    def __init__(self, tdb, tdenv):
        super().__init__(tdb, tdenv)
        
        self.filename = self.defaultImportFile
        self.configPath = tdb.dataPath / pathlib.Path(ImportPlugin.configFile)
    
    def askForStationData(self, system, stnName = None, station = None):
        """
        Ask for new or updated station data
        """
        tdb, tdenv = self.tdb, self.tdenv
        askForData = False
        
        stnDefault = namedtuple(
            'stnDefault', [
                'lsFromStar', 'market', 'blackMarket', 'shipyard', 'maxPadSize',
                'outfitting', 'rearm', 'refuel', 'repair', 'planetary',
            ]
        )
        
        def tellUserAPIResponse(defName, defValue):
            if defValue == "Y":
                tdenv.NOTE("{:>12} in API response", defName)
            else:
                tdenv.NOTE("{:>12} NOT in API response", defName)
        
        def getYNfromObject(obj, key, val = None):
            if val:
                return "Y" if obj.get(key) == val else "N"
            else:
                return "Y" if key in obj else "N"
        
        # defaults from API response are not reliable!
        checkStarport = self.edAPI.profile['lastStarport']
        defMarket = getYNfromObject(checkStarport, 'commodities')
        defShipyard = getYNfromObject(checkStarport, 'ships')
        defOutfitting = getYNfromObject(checkStarport, 'modules')
        tellUserAPIResponse("'Outfitting'", defOutfitting)
        tellUserAPIResponse("'ShipYard'", defShipyard)
        tellUserAPIResponse("'Market'", defMarket)
        
        def warnAPIResponse(checkName, checkYN):
            # no warning if unknown
            if checkYN == "?":
                return False
            warnText = (
                "The station should{s} have a {what}, "
                "but the API did{d} return one."
            )
            if checkYN == "Y":
                s, d = "", "n't"
            else:
                s, d = "n't", ""
            
            tdenv.WARN(warnText, what = checkName, s = s, d = d)
            return True if self.getOption('warn') else False
        
        # station services since ED update 2.4
        checkServices = checkStarport.get('services', None)
        if checkServices:
            if station:
                tdenv.NOTE('Station known.')
                stnlsFromStar = station.lsFromStar
                stnmaxPadSize = station.maxPadSize
                stnplanetary = station.planetary
            else:
                tdenv.NOTE('Station unknown.')
                stnlsFromStar = 0
                stnmaxPadSize = "?"
                stnplanetary = "?"
            tdenv.NOTE("Found station services.")
            if checkStarport.get('outpostType', None) == 'starport':
                # only the big one can be detected
                stnmaxPadSize = "L"
                stnplanetary = "N"
            defStation = stnDefault(
                lsFromStar = stnlsFromStar,
                market = getYNfromObject(checkServices, 'commodities', val = 'ok'),
                blackMarket = getYNfromObject(checkServices, 'blackmarket', val = 'ok'),
                shipyard = getYNfromObject(checkServices, 'shipyard', val = 'ok'),
                maxPadSize = stnmaxPadSize,
                outfitting = getYNfromObject(checkServices, 'outfitting', val = 'ok'),
                rearm = getYNfromObject(checkServices, 'rearm', val = 'ok'),
                refuel = getYNfromObject(checkServices, 'refuel', val = 'ok'),
                repair = getYNfromObject(checkServices, 'repair', val = 'ok'),
                planetary = stnplanetary,
            )
        elif station:
            tdenv.NOTE('Station known.')
            defStation = stnDefault(
                lsFromStar = station.lsFromStar,
                market = defMarket if station.market == "?" else station.market,
                blackMarket = station.blackMarket,
                shipyard = defShipyard if station.shipyard == "?" else station.shipyard,
                maxPadSize = station.maxPadSize,
                outfitting = defOutfitting if station.outfitting == "?" else station.outfitting,
                rearm = station.rearm,
                refuel = station.refuel,
                repair = station.repair,
                planetary = station.planetary,
            )
        else:
            tdenv.NOTE('Station unknown.')
            defStation = stnDefault(
                lsFromStar = 0, market = defMarket,
                blackMarket = "?", shipyard = defShipyard,
                maxPadSize = "?", outfitting = defOutfitting,
                rearm = "?", refuel = "?",
                repair = "?", planetary = "?",
            )
        
        warning = False
        if defStation.outfitting != defOutfitting:
            warning |= warnAPIResponse('outfitting', defStation.outfitting)
        if defStation.shipyard != defShipyard:
            warning |= warnAPIResponse('shipyard', defStation.shipyard)
        if defStation.market != defMarket:
            warning |= warnAPIResponse('market', defStation.market)
        if warning:
            tdenv.WARN("Please update station data with correct values.")
            tdenv.WARN("(Fields will be marked with an leading asterisk '*')")
            askForData = True
        if ((defStation.lsFromStar == 0) or ("?" in defStation)):
            askForData = True
        
        newStation = {}
        for key in defStation._fields:
            newStation[key] = getattr(defStation, key)
        
        if askForData:
            tdenv.NOTE("Values in brackets are the default.")
            lsFromStar = input(
                " Stn/Ls..............[{}]: ".format(defStation.lsFromStar)
            ) or defStation.lsFromStar
            try:
                lsFromStar = int(float(lsFromStar) + 0.5)
            except:
                print("That doesn't seem to be a number. Defaulting to zero.")
                lsFromStar = defStation.lsFromStar
            newStation['lsFromStar'] = lsFromStar
            
            for askText, askField, markValue in [
                ('Pad Size....(s,m,l) ', 'maxPadSize', defStation.maxPadSize),
                ('Planetary.....(y,n) ', 'planetary', defStation.planetary),
                ('B/Market......(y,n) ', 'blackMarket', defStation.blackMarket),
                ('Refuel........(y,n) ', 'refuel', defStation.refuel),
                ('Repair........(y,n) ', 'repair', defStation.repair),
                ('Restock.......(y,n) ', 'rearm', defStation.rearm),
                ('Outfitting....(y,n) ', 'outfitting', defOutfitting),
                ('Shipyard......(y,n) ', 'shipyard', defShipyard),
                ('Market........(y,n) ', 'market', defMarket),
            ]:
                defValue = getattr(defStation, askField)
                if defValue != markValue:
                    mark = "*"
                else:
                    mark = " "
                askValue = input(
                    "{}{}[{}]: ".format(mark, askText, defValue)
                ) or defValue
                newStation[askField] = askValue
        
        else:
            
            def _detail(value, source):
                detail = source[value]
                if detail == '?':
                    detail += ' [unknown]'
                return detail
            
            ls = newStation['lsFromStar']
            print(" Stn/Ls....:", ls, '[unknown]' if ls == 0 else '')
            print(" Pad Size..:", _detail(newStation['maxPadSize'], tdb.padSizes))
            print(" Planetary.:", _detail(newStation['planetary'], tdb.planetStates))
            print(" B/Market..:", _detail(newStation['blackMarket'], tdb.marketStates))
            print(" Refuel....:", _detail(newStation['refuel'], tdb.marketStates))
            print(" Repair....:", _detail(newStation['repair'], tdb.marketStates))
            print(" Restock...:", _detail(newStation['rearm'], tdb.marketStates))
            print(" Outfitting:", _detail(newStation['outfitting'], tdb.marketStates))
            print(" Shipyard..:", _detail(newStation['shipyard'], tdb.marketStates))
            print(" Market....:", _detail(newStation['market'], tdb.marketStates))
        
        exportCSV = False
        if not station:
            station = tdb.addLocalStation(
                system = system,
                name = stnName,
                lsFromStar = newStation['lsFromStar'],
                blackMarket = newStation['blackMarket'],
                maxPadSize = newStation['maxPadSize'],
                market = newStation['market'],
                shipyard = newStation['shipyard'],
                outfitting = newStation['outfitting'],
                rearm = newStation['rearm'],
                refuel = newStation['refuel'],
                repair = newStation['repair'],
                planetary = newStation['planetary'],
            )
            exportCSV = True
        else:
            # let the function check for changes
            if tdb.updateLocalStation(
                station = station,
                lsFromStar = newStation['lsFromStar'],
                blackMarket = newStation['blackMarket'],
                maxPadSize = newStation['maxPadSize'],
                market = newStation['market'],
                shipyard = newStation['shipyard'],
                outfitting = newStation['outfitting'],
                rearm = newStation['rearm'],
                refuel = newStation['refuel'],
                repair = newStation['repair'],
                planetary = newStation['planetary'],
            ):
                exportCSV = True
        
        if exportCSV:
            lines, csvPath = csvexport.exportTableToFile(
                tdb,
                tdenv,
                "Station",
            )
            tdenv.DEBUG0("{} updated.", csvPath)
        return station
    
    def run(self):
        tdb, tdenv = self.tdb, self.tdenv
        
        # first check for EDCD
        if self.getOption("edcd"):
            # Call the EDCD plugin
            try:
                import plugins.edcd_plug as EDCD  # @UnresolvedImport
            except:
                raise plugins.PluginException("EDCD plugin not found.")
            tdenv.NOTE("Calling the EDCD plugin.")
            edcdPlugin = EDCD.ImportPlugin(tdb, tdenv)
            edcdPlugin.options["csvs"] = True
            edcdPlugin.run()
            tdenv.NOTE("Going back to EDAPI.\n")
        
        # now load the mapping tables
        itemMap = mapping.FDEVMappingItems(tdb, tdenv)
        shipMap = mapping.FDEVMappingShips(tdb, tdenv)
        
        # Connect to the API, authenticate, and pull down the commander
        # /profile.
        if self.getOption("test"):
            tdenv.WARN("#############################")
            tdenv.WARN("###  EDAPI in test mode.  ###")
            tdenv.WARN("#############################")
            apiED = namedtuple('EDAPI', ['profile', 'text'])
            try:
                proPath = pathlib.Path(self.getOption("test"))
            except TypeError:
                raise plugins.PluginException(
                    "Option 'test' must be a file name"
                )
            if proPath.exists():
                with proPath.open() as proFile:
                    proData = json.load(proFile)
                    if isinstance(proData, list):
                        # since 4.3.0: list(profile, market, shipyard)
                        testProfile = proData[0]
                        for data in proData[1:]:
                            if int(data["id"]) == int(testProfile["lastStarport"]["id"]):
                                testProfile["lastStarport"].update(data)
                    else:
                        testProfile = proData
                    api = apiED(
                        profile = testProfile,
                        text = '{{"mode":"test","file":"{}"}}'.format(str(proPath))
                    )
            else:
                raise plugins.PluginException(
                    "JSON-file '{}' not found.".format(str(proPath))
                )
        else:
            api = EDAPI(
                configfile = str(self.configPath),
                login = self.getOption('login'),
                debug = tdenv.debug,
            )
        self.edAPI = api
        
        fs.ensurefolder(tdenv.tmpDir)
        
        if self.getOption("tdh"):
            self.options["save"] = True
        
        # save profile if requested
        if self.getOption("save"):
            saveName = 'tdh_profile.json' if self.getOption("tdh") else \
                       'profile.' + time.strftime('%Y%m%d_%H%M%S') + '.json'
            savePath = tdenv.tmpDir / pathlib.Path(saveName)
            if savePath.exists():
                savePath.unlink()
            with open(savePath, 'w', encoding = "utf-8") as saveFile:
                if isinstance(api.text, list):
                    # since 4.3.0: list(profile, market, shipyard)
                    tdenv.DEBUG0("{}", api.text)
                    saveFile.write('{{"profile":{}}}'.format(api.text[0]))
                else:
                    saveFile.write(api.text)
                print('API response saved to: {}'.format(savePath))
        
        # If TDH is calling the plugin, nothing else needs to be done
        # now that the file has been created.
        if self.getOption("tdh"):
            return False
        
        # Sanity check that the commander is docked. Otherwise we will get a
        # mismatch between the last system and last station.
        if not api.profile['commander']['docked']:
            print('Commander not docked. Aborting!')
            return False
        
        # Figure out where we are.
        sysName = api.profile['lastSystem']['name']
        stnName = api.profile['lastStarport']['name']
        marketId = int(api.profile['lastStarport']['id'])
        print('@{}/{} (ID: {})'.format(sysName.upper(), stnName, marketId))
        
        # Reload the cache.
        tdenv.DEBUG0("Checking the cache")
        tdb.close()
        tdb.reloadCache()
        tdb.load(
            maxSystemLinkLy = tdenv.maxSystemLinkLy,
        )
        tdb.close()
        
        # Check to see if this system is in the database
        try:
            system = tdb.lookupSystem(sysName)
        except LookupError:
            raise plugins.PluginException(
                "System '{}' unknown.".format(sysName)
            )
        
        # Check to see if this station is in the database
        try:
            station = tdb.lookupStation(stnName, system)
        except LookupError:
            station = None
        
        # New or update station data
        station = self.askForStationData(system, stnName = stnName, station = station)
        
        # If a shipyard exists, make the ship lists
        shipCost = {}
        shipList = []
        eddn_ships = []
        if ((station.shipyard == "Y") and ('ships' in api.profile['lastStarport'])):
            if 'shipyard_list' in api.profile['lastStarport']['ships']:
                if len(api.profile['lastStarport']['ships']['shipyard_list']):
                    for ship in api.profile['lastStarport']['ships']['shipyard_list'].values():
                        shipName = shipMap.mapID(ship['id'], ship['name'])
                        shipCost[shipName] = ship['basevalue']
                        shipList.append(shipName)
                        eddn_ships.append(ship['name'])
            
            if 'unavailable_list' in api.profile['lastStarport']['ships']:
                for ship in api.profile['lastStarport']['ships']['unavailable_list']:
                    shipName = shipMap.mapID(ship['id'], ship['name'])
                    shipCost[shipName] = ship['basevalue']
                    shipList.append(shipName)
                    eddn_ships.append(ship['name'])
        
        if self.getOption("csvs"):
            addShipList = set()
            delShipList = set()
            addRows = delRows = 0
            db = tdb.getDB()
            if station.shipyard == "N":
                # delete all ships if there is no shipyard
                delRows = db.execute(
                    """
                    DELETE FROM ShipVendor
                     WHERE station_id = ?
                    """,
                    [station.ID]
                ).rowcount
            
            if len(shipList):
                # and now update the shipyard list
                # we go through all ships to decide if a ship needs to be
                # added or deleted from the shipyard
                for shipID in tdb.shipByID:
                    shipName = tdb.shipByID[shipID].dbname
                    if shipName in shipList:
                        # check for ship discount, costTD = 100%
                        # python builtin round() uses "Round half to even"
                        # but we need commercial rounding, so we do it ourself
                        costTD = tdb.shipByID[shipID].cost
                        costED = int((shipCost[shipName] + 5) / 10) * 10
                        if costTD != costED:
                            prozED = int(shipCost[shipName] * 100 / costTD + 0.5) - 100
                            tdenv.NOTE(
                                "CostDiff {}: {} != {} ({}%)",
                                shipName, costTD, costED, prozED
                            )
                        # add the ship to the shipyard
                        shipSQL = (
                            "INSERT OR IGNORE"
                             " INTO ShipVendor(station_id, ship_id)"
                           " VALUES(?, ?)"
                        )
                        tdenv.DEBUG0(shipSQL.replace("?", "{}"), station.ID, shipID)
                        rc = db.execute(shipSQL, [station.ID, shipID]).rowcount
                        if rc:
                            addRows += rc
                            addShipList.add(shipName)
                        # remove ship from the list
                        shipList.remove(shipName)
                    else:
                        # delete the ship from the shipyard
                        shipSQL = (
                            "DELETE FROM ShipVendor"
                            " WHERE station_id = ?"
                              " AND ship_id = ?"
                        )
                        tdenv.DEBUG0(shipSQL.replace("?", "{}"), station.ID, shipID)
                        rc = db.execute(shipSQL, [station.ID, shipID]).rowcount
                        if rc:
                            delRows += rc
                            delShipList.add(shipName)
                
                if len(shipList):
                    tdenv.WARN("unknown Ship(s): {}", ",".join(shipList))
            
            db.commit()
            if (addRows + delRows) > 0:
                if addRows > 0:
                    tdenv.NOTE(
                        "Added {} ({}) ships in '{}' shipyard.",
                        addRows, ", ".join(sorted(addShipList)), station.name()
                    )
                if delRows > 0:
                    tdenv.NOTE(
                        "Deleted {} ({}) ships in '{}' shipyard.",
                        delRows, ", ".join(sorted(delShipList)), station.name()
                    )
                lines, csvPath = csvexport.exportTableToFile(
                    tdb,
                    tdenv,
                    "ShipVendor",
                )
                tdenv.DEBUG0("{} updated.", csvPath)
        
        # If a market exists, make the item lists
        itemList = []
        eddn_market = []
        if ((station.market == "Y") and ('commodities' in api.profile['lastStarport'])):
            for commodity in api.profile['lastStarport']['commodities']:
                if commodity['categoryname'] in cat_ignore:
                    continue
                
                if commodity.get('legality', '') != '':
                    # ignore if present and not empty
                    continue
                
                locName = commodity.get('locName', commodity['name'])
                itmName = itemMap.mapID(commodity['id'], locName)
                
                def commodity_int(key):
                    try:
                        ret = int(float(commodity[key]) + 0.5)
                    except (ValueError, KeyError):
                        ret = 0
                    return ret
                
                itmSupply = commodity_int('stock')
                itmDemand = commodity_int('demand')
                itmSupplyLevel = commodity_int('stockBracket')
                itmDemandLevel = commodity_int('demandBracket')
                itmBuyPrice = commodity_int('buyPrice')
                itmSellPrice = commodity_int('sellPrice')
                
                if itmSupplyLevel == 0 or itmBuyPrice == 0:
                    # If there is not stockBracket or buyPrice, ignore stock
                    itmBuyPrice = 0
                    itmSupply = 0
                    itmSupplyLevel = 0
                    tdSupply = "-"
                    tdDemand = "{}{}".format(
                        itmDemand,
                        bracket_levels[itmDemandLevel]
                    )
                else:
                    # otherwise don't care about demand
                    itmDemand = 0
                    itmDemandLevel = 0
                    tdDemand = "?"
                    tdSupply = "{}{}".format(
                        itmSupply,
                        bracket_levels[itmSupplyLevel]
                    )
                
                # ignore items without supply or demand bracket (TD only)
                if itmSupplyLevel > 0 or itmDemandLevel > 0:
                    itemTD = (
                        itmName,
                        itmSellPrice, itmBuyPrice,
                        tdDemand, tdSupply,
                    )
                    itemList.append(itemTD)
                
                # Populate EDDN
                if self.getOption("eddn"):
                    itemEDDN = {
                        "name":          commodity['name'],
                        "meanPrice":     commodity_int('meanPrice'),
                        "buyPrice":      commodity_int('buyPrice'),
                        "stock":         commodity_int('stock'),
                        "stockBracket":  commodity['stockBracket'],
                        "sellPrice":     commodity_int('sellPrice'),
                        "demand":        commodity_int('demand'),
                        "demandBracket": commodity['demandBracket'],
                    }
                    if len(commodity['statusFlags']) > 0:
                        itemEDDN["statusFlags"] = commodity['statusFlags']
                    eddn_market.append(itemEDDN)
        
        if itemList:
            # Create the import file.
            with open(self.filename, 'w', encoding = "utf-8") as f:
                # write System/Station line
                f.write("@ {}/{}\n".format(sysName, stnName))
                
                # write Item lines (category lines are not needed)
                for itemTD in itemList:
                    f.write("\t\t%s %s %s %s %s\n" % itemTD)
            
            tdenv.ignoreUnknown = True
            cache.importDataFromFile(
                tdb,
                tdenv,
                pathlib.Path(self.filename),
            )
        
        # Import EDDN
        if self.getOption("eddn"):
            con = EDDN(
                api.profile['commander']['name'],
                self.getOption("name"),
                'EDAPI Trade Dangerous Plugin',
                __version__
            )
            if self.getOption("test"):
                con._debug = True
            else:
                con._debug = False
            
            if eddn_market:
                print('Posting commodities to EDDN...')
                eddn_additional = {}
                if 'economies' in api.profile['lastStarport']:
                    eddn_additional['economies'] = []
                    for economy in api.profile['lastStarport']['economies'].values():
                        eddn_additional['economies'].append(economy)
                if 'prohibited' in api.profile['lastStarport']:
                    eddn_additional['prohibited'] = []
                    for item in api.profile['lastStarport']['prohibited'].values():
                        eddn_additional['prohibited'].append(item)
                
                con.publishCommodities(
                    sysName,
                    stnName,
                    marketId,
                    eddn_market,
                    additional = eddn_additional
                )
            
            if eddn_ships:
                print('Posting shipyard to EDDN...')
                con.publishShipyard(
                    sysName,
                    stnName,
                    marketId,
                    eddn_ships
                )
            
            if station.outfitting == "Y" and 'modules' in api.profile['lastStarport'] and len(api.profile['lastStarport']['modules']):
                eddn_modules = []
                for module in api.profile['lastStarport']['modules'].values():
                    # see: https://github.com/EDSM-NET/EDDN/wiki
                    addModule = False
                    if module['name'].startswith(('Hpt_', 'Int_')) or module['name'].find('_Armour_') > 0:
                        if module.get('sku', None) in (None, 'ELITE_HORIZONS_V_PLANETARY_LANDINGS'):
                            if module['name'] != 'Int_PlanetApproachSuite':
                                addModule = True
                    if addModule:
                        eddn_modules.append(module['name'])
                    elif self.getOption("test"):
                        tdenv.NOTE("Ignored module ID: {}, name: {}", module['id'], module['name'])
                if eddn_modules:
                    print('Posting outfitting to EDDN...')
                    con.publishOutfitting(
                        sysName,
                        stnName,
                        marketId,
                        sorted(eddn_modules)
                    )
        
        # We did all the work
        return False
