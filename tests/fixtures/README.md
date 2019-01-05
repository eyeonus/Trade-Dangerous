Trade-Dangerous Fixtures
========================

These fixtures are created by... 
* first doing a clean eddblink import.
* Pick out a list of systems `trade local --ly 25 sol > sol25ly.txt`
* Modify the generated __sol25ly.txt__ so be a CSV file
* Using the __sqlite3__ tool import the sol25ly data and delete 
  ALL systems not in that list.
* `VACUUM` the database.
* `trade export --all-tables --path=test/fixtures`
* `cp data/TradeDangerous.db test/fixtures`
