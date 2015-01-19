#! /usr/bin/env python

import pathlib
import re
import sys

try:
    import requests
except ImportError as e:
    import pip
    print("ERROR: Unable to load the Python 'requests' package.")
    approval = input(
        "Do you want me to try and install it with the package manager (y/n)? "
    )
    if approval.lower() != 'y':
        raise e
    pip.main(["install", "--upgrade", "requests"])
    import requests


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

