---
name: Bug report
about: Create a report to help us improve
title: 'Error running `trade [commoand]` : [description]'
labels: bug
assignees: ''

---

**Important**
It is recommended to install TD using `pip install --upgrade tradedangerous`. The same command can be used to keep TD up to date when a new version releases, as well. If you have not already done so, make sure that the version you have is up to date with the current version.

**Describe the bug**
Please run `trade import -P eddblink -O clean,skipvend`, then run your original `trade` command and see if the problem still occurs. If so, please add `-vvv -www` to the original `trade` command and provide the output below.

**Console log**
For smaller logs you may paste the output directly, please put it within triple ` tags
```
example code surrounded by triple ` tags
```
For larger logs (20+ lines) please paste the upload to [gist](https://gist.github.com/) and provide a link to the gist here.

**Additional context**
Add any other context about the problem here.
