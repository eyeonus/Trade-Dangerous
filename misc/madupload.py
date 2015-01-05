#! /usr/bin/env python

import pathlib
import platform
import re
import sys

try:
    import requests
except ImportError:
    if platform.system() == "Windows":
        prompt = "C:\ThisDir\>"
    else:
        prompt = "$"
    raise Exception("""Missing 'requests' module:

----------------------------------------------------------------
You don't appear to have the Python module "requests" installed.

It can be installed with Python's package installer, e.g:
  {prompt} pip install requests

For additional help, see:
  Bitbucket Wiki    http://kfs.org/td/wiki
  Facebook Group    http://kfs.org/td/group
  ED Forum Thread   http://kfs.org/td/thread

----------------------------------------------------------------
""".format(
            prompt=prompt
))


############################################################################


upload_url = 'http://www.davek.com.au/td/uploaddata.asp'
upfile = "updated.prices"
if len(sys.argv) > 1:
    upfile = sys.argv[1]


############################################################################


if not pathlib.Path(upfile).is_file():
    raise SystemExit("ERROR: File not found: {}".format(upfile))

files = {
}
r = requests.post(
        upload_url,
        files={
            'Filename': (
                upfile,
                open(upfile, 'rb'),
                'text/plain',
                {
                    "Expires": '300',
                }
            ),
        }
)

response = r.text
m = re.search(r'UPLOAD RESULT:\s*(.*?)<br', response, re.IGNORECASE)
if not m:
    raise Exception("Unexpected result:\n" + r.text)

resultCode = m.group(1)
if resultCode.startswith("SUCCESS"):
    raise SystemExit("Upload complete")

print("Upload failed: {}".format(resultCode))

