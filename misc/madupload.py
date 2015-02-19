#! /usr/bin/env python

import pathlib
import re
import sys

try:
    import requests
except ImportError as e:
    print("""ERROR: Unable to load the Python 'requests' package.

This script uses a Python module/package called 'requests' to allow
it to talk to maddavo's web service. This package is not installed
by default, but it can be installed with Python's package manager (pip).

You can either install/update it yourself, e.g.:

  pip install --upgrade requests

or if you like, I can try and install it for you now
""")
    approval = input(
        "Do you want me to try and install it with the package manager (y/n)? "
    )
    if approval.lower() != 'y':
        print("You didn't type 'y' so I'm giving up.")
        raise e
    import pip
    pip.main(["install", "--upgrade", "requests"])
    import requests


############################################################################


upload_url = 'http://www.davek.com.au/td/uploaddata.asp'
if len(sys.argv) != 2:
    raise SystemExit(
        "Usage: {} <filename>\n"
        "Uploads 'filename' to Maddavo's site, where filename should be "
        "a .prices or Station.csv file.\n"
        "\n"
        "NOTE to OCR USERS:\n"
        "Please upload the .prices file from your OCR DIRECTLY before "
        "importing it into TD, not after.".format(sys.argv[0])
    )

upfile = sys.argv[1]

############################################################################


if not pathlib.Path(upfile).is_file():
    raise SystemExit("ERROR: File not found: {}".format(upfile))

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

