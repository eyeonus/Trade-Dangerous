#!/bin/bash

find * -type f -name "*.py" -print0 | xargs -0 sed -i -e '/^ *$/{N;s/^ *\n\( *\)\(.*\)/\1\n\1\2/}'