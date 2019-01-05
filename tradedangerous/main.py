import os
import traceback
from tradedangerous.trade import main
from tradedangerous.plugins import PluginException

def main_func():
    import sys
    if sys.hexversion < 0x03040200:
        raise SystemExit(
            "Sorry: TradeDangerous requires Python 3.4.2 or higher.\n"
            "For assistance, see:\n"
            "\tFacebook Group: http://kfs.org/td/group\n"
            "\tBitbucket Page: http://kfs.org/td/source\n"
            "\tEDForum Thread: http://kfs.org/td/thread\n"
            )
    from . import tradeexcept

    try:
        try:
            if "CPROF" in os.environ:
                import cProfile
                cProfile.run("main(sys.argv)")
            else:
                main(sys.argv)
        except PluginException as e:
            print("PLUGIN ERROR: {}".format(e))
            if 'EXCEPTIONS' in os.environ:
                raise e
            sys.exit(1)
        except tradeexcept.TradeException as e:
            print("%s: %s" % (sys.argv[0], str(e)))
            if 'EXCEPTIONS' in os.environ:
                raise e
            sys.exit(1)
    except (UnicodeEncodeError, UnicodeDecodeError) as e:
        print("-----------------------------------------------------------")
        print("ERROR: Unexpected unicode error in the wild!")
        print()
        print(traceback.format_exc())
        print(
            "Please report this bug (http://kfs.org/td/issues). You may be "
            "able to work around it by using the '-q' parameter. Windows "
            "users may be able to use 'chcp.com 65001' to tell the console "
            "you want to support UTF-8 characters."
        )