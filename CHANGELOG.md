# CHANGELOG



## v11.0.5 (2024-04-27)

### Fix

* fix: update Station info when source timestamp newer ([`fa63e94`](https://github.com/eyeonus/Trade-Dangerous/commit/fa63e94a106088d28292a79829131cf938be34bc))

### Refactor

* refactor: move entry points to top level

fixes #137 ([`100e417`](https://github.com/eyeonus/Trade-Dangerous/commit/100e4179c77ceed40cab5b0f88b6f06c8b7e5846))


## v11.0.4 (2024-04-26)

### Documentation

* docs: Update comments, method annotations to be accurate ([`87c74ba`](https://github.com/eyeonus/Trade-Dangerous/commit/87c74bad86ad6a0d05ccaf9533d8ec9de0cf2b6b))

### Fix

* fix: from_live calculation

Need to include `self.dataPath` or it will always return False, which is
not what we want. ([`631758c`](https://github.com/eyeonus/Trade-Dangerous/commit/631758cc37f1b64711760ba341b937d535298e8e))

### Performance

* perf: improve eddb import performance.

small tweaks, but it redunce time to import the listings on my machine from 40 minutes to 23 ([`7716bf2`](https://github.com/eyeonus/Trade-Dangerous/commit/7716bf2e492111874dddfb1a3584c00daf5d5464))

### Refactor

* refactor: add `purge` to options prevent enabling default options ([`18782be`](https://github.com/eyeonus/Trade-Dangerous/commit/18782be674d6d5bf87a34ee38193b42248446695))

* refactor: clear progbar, do final commit, etc., after closing file ([`9b21109`](https://github.com/eyeonus/Trade-Dangerous/commit/9b211092a8e167f42c7e6f28c2795f18b6286960))

* refactor: remove unused methods, use db.* rather than self.*

Don&#39;t use self.execute() or self.commit() in some cases and db.execute()
or db.commit() in others, use db.* in all cases. ([`5e4a9de`](https://github.com/eyeonus/Trade-Dangerous/commit/5e4a9ded335a660402b38dbe170b0b1ccac85722))

* refactor: `request_url()` to `_request_url()`

Have all the methods external to the class have matching naming
convention ([`2b0d5dc`](https://github.com/eyeonus/Trade-Dangerous/commit/2b0d5dc33da5a4954d2f840ca049686528ccffc2))

* refactor: fix pylint warnings ([`61c159a`](https://github.com/eyeonus/Trade-Dangerous/commit/61c159a4b15fd74088ec743a908aa7af21c20aef))

### Test

* test: extend tox coverage with pylint and cleanup various pylint findings to make that useful ([`9b4e91c`](https://github.com/eyeonus/Trade-Dangerous/commit/9b4e91cf21e87f6f985e7cefdfae4b1708c2cf0a))


## v11.0.3 (2024-04-26)

### Fix

* fix: issue#130: lowercase cmd options ([`fd2370b`](https://github.com/eyeonus/Trade-Dangerous/commit/fd2370b3733d16ce9e3ec82c0b014c15cf0eb8e6))

### Refactor

* refactor: requests is installed by requirements, don&#39;t need code to faff with it ([`48c0382`](https://github.com/eyeonus/Trade-Dangerous/commit/48c0382ec0149febac279ac8dd75409677d487e5))


## v11.0.2 (2024-04-24)

### Fix

* fix: check for existence of the DB itself

The plugins don&#39;t export the prices cache anymore, so that&#39;s a bad thing
to check for to determine if the DB needs to be built.

Do the smart thing and check for the existence of the actual DB file
itself. ([`3dee4cb`](https://github.com/eyeonus/Trade-Dangerous/commit/3dee4cb3aeaf0810d6565f4aee00284f292a3c6e))


## v11.0.1 (2024-04-24)

### Fix

* fix: don&#39;t enable default options if `prices`

revert: use the `newItemPriceRe` that works ([`3302fa5`](https://github.com/eyeonus/Trade-Dangerous/commit/3302fa515a4238190a647b43e331b16b6cac1640))


## v11.0.0 (2024-04-24)

### Breaking

* feat: multiple improvements from ksfone

BREAKING CHANGE:
semantic release thinks we&#39;re on 10.16.7 rather than 10.17.0, and these
are a lot of improvements, so bump to 11.0.0 ([`31bcb4f`](https://github.com/eyeonus/Trade-Dangerous/commit/31bcb4f78e7e3d0daafb7eef2d69c84fd6762f87))

### Feature

* feat: multiple improvements from ksfone ([`c63e757`](https://github.com/eyeonus/Trade-Dangerous/commit/c63e7570f793849f151367e7e01f8a04c1baca5e))

* feat: multiple improvements from kfsone

* chore: increase the line limit in the .editorconfig

* chore: relax tox warnings by disabling spaces-after-:

* refactor: Cleanup pass on cache and spansh_plug

- introduce type annotations,
- Small performance considerations,

* refactor: flake and pylint rules

- ignore warnings that are overly opinionated for our needs,
- tell pylint to quit complaining about lines &gt; 100

* fix: ensure db gets closed before trying to rename it.

* perf: modernize small performance factors in spansh

- lookup systems and stations by id rather than name,
- move several &#39;is it registered&#39; tests out of ensure_ methods
  so we can avoid calling the method if there is no work to do
  (calling a function in python is expensive)
- fix ingest_stream looking up body ids rather than system ids

* chore: remove vestigial numpy stuff that annoyed linters

I couldn&#39;t see any evidence of this code still being useful.

* chore: move uprint into a mixin

tradeenv was already hard enough to read, but the utf8 wrapping of uprint made it worse, and less pythonic.

this change moves the io behavior into a base Mixin class, then provides the non-utf8 variant as an optional override mixin. finally, we do a simple if on which one to use as the favored implementation to mixin to TradeEnv.

This should be far more readable to both humans and linters etc. At least, on my machine, PyCharm no-longer catches fire.
(* it&#39;s possible that it never caught fire and that I just ate an overly hot chilli last night, but who are we to question the universe? not deflecting enough, well LOOK A SQUIRREL)

* chore: appease the gods of pylint

pylint gives deeper code warnings than flake8 can, but is slower and more spammy.

* chore: change terribly misnamed &#39;str&#39; to &#39;text&#39;

* chore: tox/pylint: now we&#39;ve appeased, lets ask for more

this will enable some more useful pylint warnings/messages, and also making it think a little harder about others so they&#39;re more useful.

* feat: introduce theming in tradeenv

two fold reasoning:
1- so people can opt out of any kind of decoration if it becomes inconvenient/problematic,
2- localization and style

In particular: the colors people want for light-vs-dark background terminals might vary, and this would make it easy to switch; second, this makes it possible to configure various strings to be localizable through the theme.

The demo-case included here is that when you use --color the word &#34;NOTE&#34; will be replaced with the &#34;information-source&#34; emoji and the word &#34;WARNING&#34; will be replaced with a warning-symbol emoji, the &#39;#&#39; for bugs will be replaced with a bug emoji.

* chore: cleanup/performance tradedb.py

this eliminates some dead methods, and switches some of the math operations to their favored modern-python/performant/64-bit versions

specifically:

%timeit 2 ** 2
94ns
%timeit 2 * 2
24ns

Also, when I originally feared math_sqrt vs ** it was probably because I didn&#39;t realize that &#34;math.sqrt&#34; was having to lookup math and sqrt each time it was called, duh.

* feat: spansh import presentation

- Adds Progresser to spansh_plugin as an experimental ui presentation layer using rich,
-- active progress bars with timers that run asynchronously (so they shouldn&#39;t have a significant performance overhead),
-- opt-out to plain-text mode incase it needs turning off quickly,
- present statistics with the view to give you a sense of progress,
- small perf tweaks

* style: blank lines have same indent as following non-blank line

* fix: Use same supply/demand levels as before

* fix: having the fdev_id listed as a unique column causes dump prices to break.

* refactor: tox was configured to give flake8 its own environment

The idea is that flake8 is really fast, so you give it it&#39;s own environment and it comes back and says &#34;YA MADE A TYPO OLIVER YA DID IT AGAIN WHY YOU ALWAYS...&#34; *cough*, sorry, anyway.

I usually run tox one of two ways:

```
tox -e flake8   # for a quick what-did-I-type-wrong check
tox --parallel  # run em all, but, like, in parallel so I don&#39;t retire before you finish
```

* test: flake8 appeasement

turning on flake8 made linters very shouty

* refactor: tox.ini

flake8 now runs its own environment that is JUST flake8 so it&#39;s fast, it doesn&#39;t install the package for itself;
added lots of flake8 ignores for formatting issues I&#39;m unclear on

* chore: flake8 warnings

* refactor: tox.ini

added a lot more ignores and some file-specific ignores, but generally got it to a point where flake8 becomes proper useful.

* chore: fix all the tox warnings

This fixes all of the tox warnings that I haven&#39;t disabled, and several that I did.

* chore: bump pylint score up to 9.63/10

fixed a few actual problems while I was at it.

* fix: formatting needs __str__ methods

When I first created the &#39;str&#39; methods, it was because I wanted a display name but repr and str both confused me at the time; I&#39;ve now renamed it text but apparently I forgot that in Py2.x def str() worked like __str__...

* refactor: use ijson instead of simdjson to reduce memory use in big imports

* refactor: logic reversal for plugin option handling

* fix: presentation was a bit wonky with doubled progress bars

---------

Co-authored-by: eyeonus &lt;eyeonus@panther&gt;
Co-authored-by: Jonathan Jones &lt;eyeonus@gmail.com&gt; ([`7c60def`](https://github.com/eyeonus/Trade-Dangerous/commit/7c60def3c9465a44b368d624d00f78f03d48a9c9))

* feat: &#39;prices&#39; option in spansh and eddblink

spansh and eddblink plugins no longer regenerate the
`TradeDangerous.prices` cache file by default

The cache file is used to rebuild the database in the event it is lost,
corrupted or otherwise damaged.

Users can manually perform a backup by running eddblink with the
&#39;prices&#39; option. If not other options are specified, eddblink will only
perform the backup

If any other options are specified, eg. `-O listings,prices`, eddblink
will perform the backup after the import process has completed. ([`257428a`](https://github.com/eyeonus/Trade-Dangerous/commit/257428aded8962b2a85920188e14525aa0d72863))

* feat: &#39;prices&#39; option in spansh and eddblink

spansh and eddblink plugins no longer regenerate the
`TradeDangerous.prices` cache file by default

The cache file is used to rebuild the database in the event it is lost,
corrupted or otherwise damaged.

Users can manually perform a backup by running eddblink with the
&#39;prices&#39; option. If not other options are specified, eddblink will only
perform the backup

If any other options are specified, eg. `-O listings,prices`, eddblink
will perform the backup after the import process has completed. ([`2e1fe85`](https://github.com/eyeonus/Trade-Dangerous/commit/2e1fe85449144c684810d815f835e73124d8ed77))

### Fix

* fix: improve compressed download progress bars

when downloading a large and extremely compressed file, user feedback would stop after we had received an uncompressed amount of data equal to the compressed size of the data.

Downloading the spansh galaxy data, for example, only transfers 1.5GB of data after compression, but the file itself expands to over 9GB, resulting in the progress bar sticking at 1.5GB and looking as though it has failed/hung. ([`1801216`](https://github.com/eyeonus/Trade-Dangerous/commit/180121632b386bf5994dbf82ab81b11e155154c9))

* fix: overridable timeout transfers w/sane default

5 minutes was a bit long, 90s seems more reasonable tho it could probably go as low as 30. ([`3687a6b`](https://github.com/eyeonus/Trade-Dangerous/commit/3687a6b689b0eead480213a20026e1e4225e8831))


## v10.16.17 (2024-04-24)

### Fix

* fix: No such file or directory error

listings_path, not listings_file ([`3bf1167`](https://github.com/eyeonus/Trade-Dangerous/commit/3bf1167e08ba0c68f89b2ad5a17a36ae1c34fade))


## v10.16.16 (2024-04-24)

### Performance

* perf: Reduce the time to load large listing files etc by a factor of 4:

https://gist.github.com/kfsone/dcb0d7811570e40e73136a14c23bf128 ([`ff7a57b`](https://github.com/eyeonus/Trade-Dangerous/commit/ff7a57b9eea46e1cec8fa24124d78f74581bb057))


## v10.16.15 (2024-04-24)

### Performance

* perf: (eddblink) get the timestamp for all station commodities at once

Do one SQL query before processing the listings file to get every
timestamp, rather than doing a SQL query for the timestamp on each
individual listing as we come to it.

This cuts the number of SQL statements being made during processing --
and thus the time taken to process -- roughly in half. ([`6c7b8d7`](https://github.com/eyeonus/Trade-Dangerous/commit/6c7b8d73bb382f07e4281b3ad5079c5a9e506157))


## v10.16.14 (2024-04-23)

### Fix

* fix: excessive RAM usage on eddblink listings import

fixes #125

Instead of building a list during processing of the listings file (which
uses a *lot* of RAM on large source files) and updating the DB after
processing, update the DB as each line is processed.

This keeps RAM usage very low, especially in comparison. ([`91a71c0`](https://github.com/eyeonus/Trade-Dangerous/commit/91a71c075d352cae91bc9cf6e5f9659cc88b2dcd))

### Refactor

* refactor: make skipping station message more clear ([`3434b53`](https://github.com/eyeonus/Trade-Dangerous/commit/3434b53b821f0f9d7791004066ebb2da89e46982))

* refactor: removed unneeded loading of DB ([`532342e`](https://github.com/eyeonus/Trade-Dangerous/commit/532342e68c7222cf9d431ed75e4f53098f0a310f))


## v10.16.13 (2024-04-22)

### Fix

* fix: remove fdev_id from Ships ([`8a67162`](https://github.com/eyeonus/Trade-Dangerous/commit/8a67162571e6dfd706b7be056d75529208f8f471))

### Refactor

* refactor: load DB after doing rebuild rather than before. ([`aaabdd1`](https://github.com/eyeonus/Trade-Dangerous/commit/aaabdd19eb395ce1f3b9f3a89789acccf23363ec))


## v10.16.12 (2024-04-22)

### Chore

* chore: add rich to install_requires in setup.py

Will automatically install rich module if needed when installing TD via
pip ([`5822a4c`](https://github.com/eyeonus/Trade-Dangerous/commit/5822a4c853602d94e7b7e621145276cc069f66ab))

### Fix

* fix: release lock on DB before rebuilding

fixes #123 ([`031eb51`](https://github.com/eyeonus/Trade-Dangerous/commit/031eb51515371ff9e42e37c226619059a9c48f03))

### Refactor

* refactor: account for FDevShipyard and FDevOutfitting changes

FDevShipyard now has entitlements, and FDevOutfitting has entitlements
that are more than 10 char long, .sql updated to reflect these changes.

Changes will automatically take effect when eddblink is run after
upgrading to this version.

correct eddblink plugin to download the source for both to the correct
location. ([`5eae43d`](https://github.com/eyeonus/Trade-Dangerous/commit/5eae43da8154b3e9d6a5aeb6e726c750b8418a1e))

### Unknown

* Merge branch &#39;release/v1&#39; of https://github.com/eyeonus/Trade-Dangerous.git into release/v1 ([`f91ff79`](https://github.com/eyeonus/Trade-Dangerous/commit/f91ff798293789a82650f38382c1d055fbbfc299))


## v10.16.11 (2024-04-22)

### Chore

* chore: tox test environments needs to require the packages that tradedangerous is going to be depending on (#122)

The tox testenv&#39;s need to import the same set of packages as dependencies that trade is going to want. using &#34;-r requirements/dev.txt&#34; tells it to do this.

I also added &#34;flake8&#34; as an env so that you can use tox to get flake results with tox -e flake8; the value there is that you get apples-to-apples. I hate running flake in my ide / vim and then tox has a slightly different config :) ([`1e15bbf`](https://github.com/eyeonus/Trade-Dangerous/commit/1e15bbf000c05bc57a57aea3a1e33192d038ae11))

* chore: additional IDE folders added to .gitignore (#120) ([`79db6f1`](https://github.com/eyeonus/Trade-Dangerous/commit/79db6f1e7f3acad3e37c3913ba1311364723a55a))

### Fix

* fix: don&#39;t generate StationItem table

It&#39;s just a bad idea, even if it didn&#39;t break things because csvexport
doesn&#39;t know what to do with two unique keys in the same table. ([`5d50c84`](https://github.com/eyeonus/Trade-Dangerous/commit/5d50c843e9dbfe44bbe8a09aeb5033b1a7ada043))

### Unknown

* qol: enable rich text (#121)

* chore: tox test environments needs to require the packages that tradedangerous is going to be depending on

* qol: enable rich text

Fix typo in markup for stack traces (dim vs out) ([`a7dba2f`](https://github.com/eyeonus/Trade-Dangerous/commit/a7dba2f6d8d25cbc600161d6039194ffb3788cc1))


## v10.16.10 (2024-04-22)

### Fix

* fix: &#34;database image malformed&#34; error in eddblink

caused by self.commit() method, which isn&#39;t actually needed ([`67b2410`](https://github.com/eyeonus/Trade-Dangerous/commit/67b24103fbff47cd24684e398ea5636cce946c8a))

* fix: make downloaded file have correct timestamp

force the modification time to be that of the timestamp from the server,
because the downloaded file will have a different timestamp based on the
time it was created ([`b34ba66`](https://github.com/eyeonus/Trade-Dangerous/commit/b34ba6663437b77b5c57199c043e485743bea74f))


## v10.16.9 (2024-04-21)

### Fix

* fix: the actual problem is there is self.updated anymore

Switched to checking if listings option is set instead. ([`8f0b3ba`](https://github.com/eyeonus/Trade-Dangerous/commit/8f0b3ba180bdf98d5861ac142521356bc0fcfc9b))


## v10.16.8 (2024-04-21)

### Fix

* fix: Mysteriously appeared &#34;Listings&#34; should be &#34;listings&#34; ([`0153410`](https://github.com/eyeonus/Trade-Dangerous/commit/0153410cce05e14e270d77b4e52ba5e5482fc21f))


## v10.16.7 (2024-04-21)

### Fix

* fix: getOption(...), not getOption[...] ([`bcbc05f`](https://github.com/eyeonus/Trade-Dangerous/commit/bcbc05f74e6ca76cc54016ba2d49893d7947040c))


## v10.16.6 (2024-04-21)

### Performance

* perf: skip station if commodity in DB is not older

Instead of checking all the commodities, skip the whole station if the
first doesn&#39;t pass, because all commodities are always updated at the
same time.

Also don&#39;t increment number of stations if commodities were skipped.

Also don&#39;t increment number of systems if all stations in it were
skipped. ([`9560dc7`](https://github.com/eyeonus/Trade-Dangerous/commit/9560dc7647c363652cfa7f390cf41f914623512a))

### Unknown

* Merge branch &#39;release/v1&#39; of https://github.com/eyeonus/Trade-Dangerous.git into release/v1 ([`4b3cd6b`](https://github.com/eyeonus/Trade-Dangerous/commit/4b3cd6b2608f13b8d79c915cfa0571387155360f))


## v10.16.5 (2024-04-21)

### Fix

* fix: Use corrections DB when adding commodities ([`d070a7c`](https://github.com/eyeonus/Trade-Dangerous/commit/d070a7c7c1a7fe18995d34ffbbb223e1d5e1fb03))


## v10.16.4 (2024-04-21)

### Fix

* fix: correct commodity count

fix: close DB when finished with import ([`b5d17b6`](https://github.com/eyeonus/Trade-Dangerous/commit/b5d17b6f2418da5244840a27c7732febf1064dd5))


## v10.16.3 (2024-04-21)

### Fix

* fix: don&#39;t crash when trying to perform unneeded commit ([`afce0e2`](https://github.com/eyeonus/Trade-Dangerous/commit/afce0e287acdace7d7bd24867ee10850f6f2beca))

### Refactor

* refactor: include FDevShipyard.csv and FDevOutfitting.csv ([`b2398cb`](https://github.com/eyeonus/Trade-Dangerous/commit/b2398cbedc992a4b9bffb10efc46bf4cf9a7d42d))


## v10.16.2 (2024-04-21)

### Fix

* fix: check for prices cache file, not db file ([`3be19bf`](https://github.com/eyeonus/Trade-Dangerous/commit/3be19bf7bf92e81578a0ce44df59af7e12243b75))

### Refactor

* refactor: Use WAL and VACUUM ([`0a329ee`](https://github.com/eyeonus/Trade-Dangerous/commit/0a329ee9e5abfe2a892c6ff4298084c8d0e346bf))


## v10.16.1 (2024-04-21)

### Fix

* fix: copy Category.csv into data on new build ([`51a1964`](https://github.com/eyeonus/Trade-Dangerous/commit/51a19641b2f701d226efa687d89179c3a5667093))


## v10.16.0 (2024-04-21)

### Chore

* chore: remove eddblink test ([`c0b14fd`](https://github.com/eyeonus/Trade-Dangerous/commit/c0b14fdeeef807634e95f080e14f86c2e130f9ad))

### Feature

* feat: spansh doesn&#39;t crash when run on new install

feat: spansh imports directly to database, rather than creating a
.prices file and then importing that

fix: strip trailing whitespace from system and station names, if any,
when pulling from the source

refactor: include station type for *all* stations, not just fleet
carriers and odyssey settlements

refactor: determine if station is planetary based on station type,
rather than assuming based on format of source file

refactor: use id provided by source for systems and stations when
inserting new into DB, search for same by id instead of by name

refactor: eddblink now uses csv files from server instead of the old
EDDB files that no longer exist

chore: include `Categories.csv` in templates ([`bad945c`](https://github.com/eyeonus/Trade-Dangerous/commit/bad945c86fea3ccc74787f5fd5f972c9dc99f1fd))


## v10.15.2 (2024-04-19)

### Fix

* fix: maxage errors if not set

`float(null)` doesn&#39;t work, obviously, make sure to only cast to float
is maxage has been set. Also make sure maxage is set before doing the
math to see if a station should be skipped.

fix: Make sure the cache is updated if a system, station, or commodity
was added to the DB.

fix: Use fdev_id as item_id when adding new commodity to the DB.

fix: Update the ui_order for commodities when a new one is added to the
DB.

refactor: Use a better method for removing spaces from a prices file. ([`3d7e330`](https://github.com/eyeonus/Trade-Dangerous/commit/3d7e33033b274a49bec63c61ab317c8fcfb2d011))

### Unknown

* Merge branch &#39;release/v1&#39; of https://github.com/eyeonus/Trade-Dangerous.git into release/v1 ([`eddbbe0`](https://github.com/eyeonus/Trade-Dangerous/commit/eddbbe02f630877c25297a804cc37e543838d5ac))


## v10.15.1 (2024-04-19)

### Fix

* fix: fix formatting of station skip message ([`906227d`](https://github.com/eyeonus/Trade-Dangerous/commit/906227d74dda67fc4a51296372ea75eade95a8c8))


## v10.15.0 (2024-04-17)

### Feature

* feat: add maxage option to spansh plugin

By specifying maxage, any station from the source that is older than the
age will be skipped.
So if a full update was done using galaxy_stations.json on 13th May
(which is updated every ~24 hours), doing a new update on 20th of May
with a max_age of 7 will skip anything in the source that wasn&#39;t updated
later than 13th May ([`0063e12`](https://github.com/eyeonus/Trade-Dangerous/commit/0063e12d24fc72b5e2673a28956d5262371e8e8c))


## v10.14.4 (2024-04-15)

### Fix

* fix: download file when using spansh url option

If there is a connection error whilst streaming from the url, it results
in a crash. Downloading the file first and then streaming from the local
file instead results in a much more stable import process. ([`f6e1a9a`](https://github.com/eyeonus/Trade-Dangerous/commit/f6e1a9aa59373cdbc200b008dddbd7f4bce07fb9))

### Unknown

* Merge branch &#39;release/v1&#39; of https://github.com/eyeonus/Trade-Dangerous.git into release/v1 ([`40f8f7c`](https://github.com/eyeonus/Trade-Dangerous/commit/40f8f7c027441ff8eb6a450f915473bb9ca39201))


## v10.14.3 (2024-04-15)

### Fix

* fix: Don&#39;t overwrite TradeDangerous.prices

spansh import plugin now writes to `&lt;TD_path&gt;/tmp/spansh.prices` rather
than overwriting the cache file, and automatically imports the resulting
spansh.prices file when processing has completed, rather than asking the
user to import it via the import dialog box.

Also added the `listener` option to the spansh plugin to forego the
import when run from TD-listener. ([`2c5080b`](https://github.com/eyeonus/Trade-Dangerous/commit/2c5080b76d5e5c497a56fbb0de60f3e4ae204f93))

### Unknown

* Merge branch &#39;release/v1&#39; of https://github.com/eyeonus/Trade-Dangerous.git into release/v1 ([`f8db4af`](https://github.com/eyeonus/Trade-Dangerous/commit/f8db4af74af8187225b057f23f178f47b67d8b45))


## v10.14.2 (2024-03-23)

### Fix

* fix: Update pyproject.toml ([`c25e778`](https://github.com/eyeonus/Trade-Dangerous/commit/c25e778df27540420d40909831f3baf4e6012794))

* fix: Update python-app.yml ([`0320312`](https://github.com/eyeonus/Trade-Dangerous/commit/0320312d1d1ae1c9023e690e7603e41d72b85997))

* fix: Update python-app.yml ([`d523382`](https://github.com/eyeonus/Trade-Dangerous/commit/d5233828b405148acd8f3a28762e93c0896d0231))

* fix: Update python-app.yml ([`15fa4ca`](https://github.com/eyeonus/Trade-Dangerous/commit/15fa4ca952754ce148e35ae02b69396b5b2608d6))

* fix: Update python-app.yml ([`7e118a8`](https://github.com/eyeonus/Trade-Dangerous/commit/7e118a865fa2dd23ec7a6b1e8b79ce4c5e2d4aee))

* fix: Update publish.txt ([`1dc4031`](https://github.com/eyeonus/Trade-Dangerous/commit/1dc4031a4c9d3b31bdc06cb51f188387b1d4ea8f))

* fix: Update python-app.yml ([`39b2fbc`](https://github.com/eyeonus/Trade-Dangerous/commit/39b2fbcf242cb4d8a1d9d476ba9c8fbd2ef481c3))

* fix: Update python-app.yml ([`890bba8`](https://github.com/eyeonus/Trade-Dangerous/commit/890bba87796cb636554b21a81f327f3ce118e527))

* fix: Update python-app.yml ([`229db1f`](https://github.com/eyeonus/Trade-Dangerous/commit/229db1fec29dbc9196f0fb341596d67dd9977a9f))

* fix: Update python-app.yml ([`b79a47b`](https://github.com/eyeonus/Trade-Dangerous/commit/b79a47b535d62863be7d2157aad1e8ee54b5fd73))

* fix: Update python-app.yml ([`41962ef`](https://github.com/eyeonus/Trade-Dangerous/commit/41962efb685822f5c3dcf2e9a336dbcdc024e315))

* fix: Update python-app.yml ([`c7141ca`](https://github.com/eyeonus/Trade-Dangerous/commit/c7141cab3cbc92fe995a27582f4e5dfd7c690c0f))

* fix: Update python-app.yml ([`432631e`](https://github.com/eyeonus/Trade-Dangerous/commit/432631e1c1ec6acce4bdc2754ee0bcf869bdb1c3))

* fix: Update python-app.yml ([`96c29bd`](https://github.com/eyeonus/Trade-Dangerous/commit/96c29bdbb884036ce96e0e67abc8d490f3ac83b2))

* fix: Update python-app.yml ([`7a4ce3b`](https://github.com/eyeonus/Trade-Dangerous/commit/7a4ce3b19ada8dc1c2f76048d9d54428063e3f95))

* fix: Update python-app.yml ([`46288d9`](https://github.com/eyeonus/Trade-Dangerous/commit/46288d9c535234259ee5f1501343972ad1d6678e))

* fix: Update python-app.yml ([`d6b956c`](https://github.com/eyeonus/Trade-Dangerous/commit/d6b956c2b56ac7fc128c6725d9194a47ecb322dd))

* fix: Create pyproject.toml ([`bd54be8`](https://github.com/eyeonus/Trade-Dangerous/commit/bd54be86cbe0a967f8fee06a0e9b16b4d77f4ee8))

* fix: Update python-app.yml ([`85491b9`](https://github.com/eyeonus/Trade-Dangerous/commit/85491b923db25c8ca0f2914252b022c1efed9568))

* fix: Update python-app.yml ([`45a420a`](https://github.com/eyeonus/Trade-Dangerous/commit/45a420ad817bc1566bb86146bef53f9b68771db7))

* fix: Update python-app.yml ([`70a80a1`](https://github.com/eyeonus/Trade-Dangerous/commit/70a80a17b56de3cb989225c8a256525599d83d01))

* fix: Update python-app.yml ([`69d3806`](https://github.com/eyeonus/Trade-Dangerous/commit/69d3806a6f0617316e723a136c454edbf8ee0dc4))

* fix: Update python-app.yml ([`482462d`](https://github.com/eyeonus/Trade-Dangerous/commit/482462d55ccfb673a8ea765684d9fd693a1631d0))

* fix: Update python-app.yml ([`563d447`](https://github.com/eyeonus/Trade-Dangerous/commit/563d447252c53e738f62afacfe65b1d7dea4b816))

* fix: Update python-app.yml ([`94f5e3d`](https://github.com/eyeonus/Trade-Dangerous/commit/94f5e3d14fd365482a0a48eed43a1dbac434734e))

* fix: bump again ([`3cc5254`](https://github.com/eyeonus/Trade-Dangerous/commit/3cc5254a2bd5ed0ea354c394df0edeef9929af91))

* fix: Update python-app.yml ([`5d098fb`](https://github.com/eyeonus/Trade-Dangerous/commit/5d098fbcd0a5de9f0162fe6d9f4a3b60dc27217c))

* fix: bump version for pypi publication ([`e05853f`](https://github.com/eyeonus/Trade-Dangerous/commit/e05853ff0d12f5117bb4e94813cba4c779c285d9))

### Refactor

* refactor: Update publish.txt ([`d8ae0b7`](https://github.com/eyeonus/Trade-Dangerous/commit/d8ae0b76409d77bec68069080bba90bcc798e337))

### Unknown

* Merge branch &#39;release/v1&#39; of https://github.com/eyeonus/Trade-Dangerous.git into release/v1 ([`8480ee6`](https://github.com/eyeonus/Trade-Dangerous/commit/8480ee6d75183405e7575d15d811a3c21d9ea901))

* Merge branch &#39;release/v1&#39; of https://github.com/eyeonus/Trade-Dangerous.git ([`d4eb96a`](https://github.com/eyeonus/Trade-Dangerous/commit/d4eb96a31353222b3ee1d86c98b47001db51959c))


## v10.14.1 (2024-03-18)

### Fix

* fix: remove incorrect cast to boolean for the modified timestamp values (#118)

also include distance from star from stations ([`6f2027a`](https://github.com/eyeonus/Trade-Dangerous/commit/6f2027aefbf2210821358cfcb4eae8a2f8375452))


## v10.14.0 (2024-03-17)

### Feature

* feat: plugin to ingest pricing data from https://downloads.spansh.co.uk/galaxy_stations.json

* fix station name matching

sqlite&#39;s `upper()` function doesn&#39;t support non-ascii characters, so letters like &#34;ñ&#34; do not get capitalised correctly.
move that transform to the python side, which has full unicode support

* feat: plugin to ingest pricing data from https://downloads.spansh.co.uk/galaxy_stations.json ([`7dd32b5`](https://github.com/eyeonus/Trade-Dangerous/commit/7dd32b514d6aa88368e2648565410998005a02f1))

### Unknown

* test ([`88c1fd7`](https://github.com/eyeonus/Trade-Dangerous/commit/88c1fd7d914dd779b4a267843f7b8f831341294d))


## v10.13.10 (2023-02-13)

### Fix

* fix: make gui work again ([`f0a95c3`](https://github.com/eyeonus/Trade-Dangerous/commit/f0a95c3950783c6377df0c0ef3fce0f24769c4c9))

### Refactor

* refactor: use raw strings for regex

Fixes #107 ([`74a4c31`](https://github.com/eyeonus/Trade-Dangerous/commit/74a4c3190eb300981d5c578fe3105c7edaf8f122))

### Unknown

* 10.13.10

python-semantic-release automatic version update. ([`6f266ac`](https://github.com/eyeonus/Trade-Dangerous/commit/6f266ac98b7370f7d7e4322ad65fe55ea2c7fc50))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous ([`db62e14`](https://github.com/eyeonus/Trade-Dangerous/commit/db62e148faa8885db9615fa5c66fac4ac3c049af))


## v10.13.9 (2022-12-27)

### Fix

* fix: Make tox work on windows again (#106)

* fix: fix funky ssl for urllib on windows

* chore: re enable test for windows

* tests: run tox differently

* chore: coverage is great to have when developing

* style: cleanup and typing

* fix: close tdb and/or cursors

* style: remove debug print infor

* tests: add update_gui to bootstrap test ([`5309181`](https://github.com/eyeonus/Trade-Dangerous/commit/53091817c5274589b54ed41fe099ba68531fa1d1))

### Unknown

* 10.13.9

python-semantic-release automatic version update. ([`aee966c`](https://github.com/eyeonus/Trade-Dangerous/commit/aee966cde41033246c15bf9ac340abacd517c7d8))


## v10.13.8 (2022-12-27)

### Fix

* fix: New Sementic release ([`1b2a46c`](https://github.com/eyeonus/Trade-Dangerous/commit/1b2a46c29eef708e439abea86d863409edc350ef))

### Refactor

* refactor: Update ship index message.

Minor comment changes as well. ([`6f63d4d`](https://github.com/eyeonus/Trade-Dangerous/commit/6f63d4dde6de10aeca9b80aee3dcfcf0a95ef2ed))

### Unknown

* 10.13.8

python-semantic-release automatic version update. ([`df01f9c`](https://github.com/eyeonus/Trade-Dangerous/commit/df01f9c8246e74a6a882a013095f61d6d61fb577))

* Remove Windows testing until it stops being broken

For whatever reason, tox fails on Windows currently when running &#39;coverage report --show-missing&#39;, most likely due to the following:

```
   tests\test_bootstrap_commands.py ..............               [ 22%]
  tests\test_bootstrap_plugins.py ...s....                       [ 35%]
  tests\test_cache.py ...                                        [ 40%]
  tests\test_commands.py .......                                 [ 51%]
  tests\test_fs.py ...                                           [ 56%]
  tests\test_peek.py ....                                        [ 62%]
  tests\test_tools.py .                                          [ 64%]
  tests\test_trade.py .........s                                 [ 80%]
  tests\test_trade_import_eddblink.py ..ss                       [ 87%]
  D:\a\Trade-Dangerous\Trade-Dangerous\.tox\py37\lib\site-packages\coverage\control.py:825: CoverageWarning: No data was collected. (no-data-collected)
  tests\test_trade_run.py .ss.                                   [ 93%]
  tests\test_utils.py ....                                       [100%]
    self._warn(&#34;No data was collected.&#34;, slug=&#34;no-data-collected&#34;)
```

Linux testing proceeds without error, so until this is figured out, no Windows testing in the publishing action.

Hopefully @kmpm will know what is going on, if not GitHub support will hopefully eventually get back to me. ([`431a258`](https://github.com/eyeonus/Trade-Dangerous/commit/431a25870461d09be61926b44e06142e2e2e31a2))

* Update python-app.yml ([`188a592`](https://github.com/eyeonus/Trade-Dangerous/commit/188a592c6c265de6c1d2c693d1b136ad52507dd2))

* Fix tox-travis breaking publish testing ([`3c00ea0`](https://github.com/eyeonus/Trade-Dangerous/commit/3c00ea0fed76ac7e0ea5db4b35d9ee27dd8c7391))

* Fix #104 ([`4b90222`](https://github.com/eyeonus/Trade-Dangerous/commit/4b90222a7f7f38cd7061bf879dc1c9751dc8e387))


## v10.13.7 (2022-06-15)

### Fix

* fix: Forgot to remove some debug code. ([`8b1b889`](https://github.com/eyeonus/Trade-Dangerous/commit/8b1b889823365b337ac9657cfbf034c0373ee76c))

### Unknown

* 10.13.7

python-semantic-release automatic version update. ([`df8a28f`](https://github.com/eyeonus/Trade-Dangerous/commit/df8a28fea05f29c747997892c6f11893ab9495f2))

* Fix: nav errors when no route found

Still errors, but now it&#39;s the TD-specific error that&#39;s intended to be
thrown rather than the Python error. ([`5f8e95a`](https://github.com/eyeonus/Trade-Dangerous/commit/5f8e95abd5b49a53bb2015dadf35dd6cc372655d))


## v10.13.6 (2022-06-09)

### Fix

* fix: strip microseconds off timestamps which have them ([`17b603d`](https://github.com/eyeonus/Trade-Dangerous/commit/17b603d52517d1bfdf9956993bec656a3e8b6673))

### Unknown

* 10.13.6

python-semantic-release automatic version update. ([`339b1ce`](https://github.com/eyeonus/Trade-Dangerous/commit/339b1cebe04bc9cc17baba5fa98821b0a84c9995))


## v10.13.5 (2022-06-01)

### Fix

* fix: set default argv to None ([`4b44458`](https://github.com/eyeonus/Trade-Dangerous/commit/4b444581844a356c7cf65c1d4301bac83cf93436))

### Unknown

* 10.13.5

python-semantic-release automatic version update. ([`4e28941`](https://github.com/eyeonus/Trade-Dangerous/commit/4e289414b0cfef371744e1a8ff0eab06d152e5f6))


## v10.13.4 (2022-06-01)

### Fix

* fix: Pypi authentication error

Added PYPI_TOKEN to Actions workflow ([`87e2c82`](https://github.com/eyeonus/Trade-Dangerous/commit/87e2c82a3deee9f0679f76723f420c24b79ff8b9))

### Unknown

* 10.13.4

python-semantic-release automatic version update. ([`5e55346`](https://github.com/eyeonus/Trade-Dangerous/commit/5e553463468f16057299635553c12fed0ca248b2))


## v10.13.3 (2022-06-01)

### Fix

* fix: don&#39;t run version, publish does that

running `semantic-release version` before running `semantic-release publish` causes publish to think it doesn&#39;t need to publish when it does:
```
Run semantic-release version
Creating new version
Current version: 10.13.2, Current release version: 10.13.2
Bumping with a patch version to 10.13.3
Run semantic-release publish -v debug
. . .
Current version: 10.13.3, Current release version: 10.13.3
. . .
No release will be made.
```

As per the semantic-release doc, publish will run version, so doing it ourselves, it turns out, is a BAD thing ([`f873a82`](https://github.com/eyeonus/Trade-Dangerous/commit/f873a8224d1df938bd9bb94904ee3c17ab4e47fd))

* fix: remove Travis, separate GUI ([`4557d7b`](https://github.com/eyeonus/Trade-Dangerous/commit/4557d7bb7dd65b2aab1c3e2e34494e305ebd73bb))

### Refactor

* refactor: remove Travis ([`0b28406`](https://github.com/eyeonus/Trade-Dangerous/commit/0b2840633e8e30e95a1d0f0efc4aa8481cbcce6c))

### Unknown

* 10.13.3

python-semantic-release automatic version update. ([`f9ef6cd`](https://github.com/eyeonus/Trade-Dangerous/commit/f9ef6cdb8f657721c6644f48a74aaab5dcedbf50))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous ([`316deb8`](https://github.com/eyeonus/Trade-Dangerous/commit/316deb8e43334bdf18a49dd5e4514b08a35a6115))

* refactor - split gui into own console command &#39;tradegui&#39;

Can no longer launch TD GUI by passing the &#39;gui&#39; argument to trade as in
&#39;&gt;python trade.py gui&#39;

Good news is this means users not using the GUI won&#39;t get any tk related
errors when running the CLI.

docs - updated gui.py with development roadmap ([`5e4d272`](https://github.com/eyeonus/Trade-Dangerous/commit/5e4d2725d3086a9868733397a4dbdf778a29f9bc))


## v10.13.2 (2022-02-07)

### Chore

* chore: add support for gh-action ([`25869f3`](https://github.com/eyeonus/Trade-Dangerous/commit/25869f3adb7df80b92542007a3aaa71b9c37598c))

* chore: editorconfig with trim trailing ws disabled ([`eebe677`](https://github.com/eyeonus/Trade-Dangerous/commit/eebe677cdaa0d7fadb94337c858f0a42c0a6d7d4))

* chore: add supported version classifiers ([`0bebda5`](https://github.com/eyeonus/Trade-Dangerous/commit/0bebda5a7b977d98fe29f90a0f3d28991b928d6c))

### Fix

* fix: minor fixes

fixes #98

fix potential fail when using TD_DATA but not TD_CSV ([`154db36`](https://github.com/eyeonus/Trade-Dangerous/commit/154db361ce739ff22db63f84c2bc5cd2691046b0))

### Test

* test: fix locking files during tests ([`deb7317`](https://github.com/eyeonus/Trade-Dangerous/commit/deb7317c437184284976dbef2dadf481d4da7e44))

### Unknown

* 10.13.2

python-semantic-release automatic version update. ([`9016b3c`](https://github.com/eyeonus/Trade-Dangerous/commit/9016b3c7e2589a44f75bb6f6fb542bb2ccf0b95c))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous ([`01d5375`](https://github.com/eyeonus/Trade-Dangerous/commit/01d537546d61f9ea27700ecdd2507a5b2479ded3))

* minor fixes

fixes #98

fix potential fail when using TD_DATA but not TD_CSV ([`f7d0090`](https://github.com/eyeonus/Trade-Dangerous/commit/f7d009081c971c314de461bc972d7ea1fe316240))


## v10.13.1 (2022-01-31)

### Fix

* fix: make semantic tell me what&#39;s broke ([`0c328ca`](https://github.com/eyeonus/Trade-Dangerous/commit/0c328ca49556958438621f5ff84aba7cde39dbdd))

### Unknown

* 10.13.1

python-semantic-release automatic version update. ([`ffa51ae`](https://github.com/eyeonus/Trade-Dangerous/commit/ffa51ae183a45c8f90cf716b30759324dad4f5a4))

* 10.13.1

python-semantic-release automatic version update. ([`2df3f0f`](https://github.com/eyeonus/Trade-Dangerous/commit/2df3f0f68ad643434f2f9911b6f0c5068e8b65fb))


## v10.13.0 (2022-01-31)

### Feature

* feat: add TD_CSV environment variable detection to csv export

Allows saving the the TD cache in a location other than TD_DATA ([`9537082`](https://github.com/eyeonus/Trade-Dangerous/commit/95370829da9b25e3d6aba0e9161c92716be82633))

### Fix

* fix: (maybe) remove test that travis keeps failing on

Possibly revert later once I figure out how this works ([`9e23361`](https://github.com/eyeonus/Trade-Dangerous/commit/9e23361b43d5068c0ef2c5ce13489a74275d653a))

### Unknown

* 10.13.0

python-semantic-release automatic version update. ([`3400f5d`](https://github.com/eyeonus/Trade-Dangerous/commit/3400f5dfb72b8fcdf2e84f81fe8120a341d1e5ea))


## v10.12.0 (2021-11-20)

### Feature

* feat: Added --max-ls parameter to the buy command. (#96)

Here&#39;s hoping TravisCL doesn&#39;t break. Again. ([`ff371eb`](https://github.com/eyeonus/Trade-Dangerous/commit/ff371eb25b91f745e872dce953001c3644a4db2c))

### Fix

* fix: buy command var &#34;maxLS&#34; not named consistently (&#34;maxLS&#34;, &#34;maxLs&#34;)

All instances have been changed to &#34;mls&#34; to match other commands. ([`1f4989a`](https://github.com/eyeonus/Trade-Dangerous/commit/1f4989a8280702110b68f8b52c08b60a27c41e33))

### Unknown

* 10.12.0

python-semantic-release automatic version update. ([`98a8710`](https://github.com/eyeonus/Trade-Dangerous/commit/98a8710ab1241cd9fb18a765b70598a3f968f50c))


## v10.11.3 (2021-10-04)

### Chore

* chore: hopefully fix semantic-release not publishing ([`d3b4485`](https://github.com/eyeonus/Trade-Dangerous/commit/d3b44856600b8974d0fb9e77a8470268f4cc21ee))

### Fix

* fix: publish the new version! ([`d8f0dd7`](https://github.com/eyeonus/Trade-Dangerous/commit/d8f0dd700f46c73ba9505ce0dbb6fa726ebd931b))

### Refactor

* refactor: Add TODO, hopefully make Travis publish again. ([`2946b9c`](https://github.com/eyeonus/Trade-Dangerous/commit/2946b9c559a84a604d46aac8c8395c78af0b5d42))

### Unknown

* 10.11.3

python-semantic-release automatic version update. ([`146cc1b`](https://github.com/eyeonus/Trade-Dangerous/commit/146cc1bc63e1c134dd3797f9a9e18e4a7e7f150e))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous ([`88b6ac9`](https://github.com/eyeonus/Trade-Dangerous/commit/88b6ac943beef88f8573332f66b78d6fc2369269))


## v10.11.2 (2021-10-03)

### Documentation

* docs: Update README.md

Update copyright dates. ([`d38a096`](https://github.com/eyeonus/Trade-Dangerous/commit/d38a09641eac6ab5f25fa59e9b8187c686267b47))

### Fix

* fix: Correct typo in olddata.

Fixes #94. ([`8cd12c5`](https://github.com/eyeonus/Trade-Dangerous/commit/8cd12c5875566728c0ff79299004b6f19406ebfe))

### Unknown

* 10.11.2

python-semantic-release automatic version update. ([`52fe5a3`](https://github.com/eyeonus/Trade-Dangerous/commit/52fe5a324d850566dfb6b6d68215a8060f6e7cfc))


## v10.11.1 (2021-06-28)

### Performance

* perf: Avoid excessive loops (#93)

Evaluate all filter conditions instead of looping over all stations separately for condition provided.
This leads to a quite substantial speedup if multiple filter conditions are provided. ([`f457db5`](https://github.com/eyeonus/Trade-Dangerous/commit/f457db5c9a6b46ce3610d993ff629d2a579e7ce8))

### Unknown

* 10.11.1

python-semantic-release automatic version update. ([`62a097b`](https://github.com/eyeonus/Trade-Dangerous/commit/62a097b844c848e5d3b2f4c7ddbe210c0212406a))


## v10.11.0 (2021-06-22)

### Feature

* feat: Add switch to filter Odyssey Settlements [&#39;--odyssey&#39;|&#39;--od&#39;].

Fixes #91 ([`396d9f0`](https://github.com/eyeonus/Trade-Dangerous/commit/396d9f0876bcb2c1c4cf7ecb7e164c5139df5c8c))

### Refactor

* refactor: missing comma ([`87d53ff`](https://github.com/eyeonus/Trade-Dangerous/commit/87d53ffbec3c32ba6613b406d55e360cc32bdb47))

* refactor: broke a test case ([`f7a4a32`](https://github.com/eyeonus/Trade-Dangerous/commit/f7a4a32ded2c75e06d9eefaa01f121a523db0a61))

### Unknown

* 10.11.0

python-semantic-release automatic version update. ([`002436c`](https://github.com/eyeonus/Trade-Dangerous/commit/002436c81ac52f65a1f743b6249ae50c8c625bf3))

* Fix: mfd module not found.

Fixes #92 ([`e5b01b7`](https://github.com/eyeonus/Trade-Dangerous/commit/e5b01b728bcce6eb784a2c8a720d1a1311ccac9d))


## v10.10.0 (2021-03-26)

### Feature

* feat: Allow for capacities above 1500

See #89

There is no longer an upper limit, capacities &gt;1500 will trigger a
warning, not an error.

This also forces jumps per hop to 1 and adds &#39;--supply&#39; and &#39;--demand&#39;,
if not already provided, to ignore stations that do not have
supply/demand of at least 10*capacity. This has the effect of filtering
out many stations, with the effect of making it more likely it will find
a route that not only will fill the hold and also more likely the route
can be repeated multiple times.

1 hop with the above settings is about long enough to shop for, prepare,
and eat dinner.

2 hops is multiple days without &#39;--loop&#39;. With &#39;--loop&#39;, it took ~150%
of the time as 1 hop to finish, reporting failure to find a route.

It is extremely unlikely that any station not only has a large quantity
of something another station needs a large quantity of, but also needs
needs a large quantity of something that same other station has a large
quantity of, so not finding a 2-hop loop route isn&#39;t surprising.

It might be possible to find a loop route of 3+ hops, this has not been
tested and is not recommended. A 3-hop loop route might be possible to
find reliably, user discretion is advised.

Doing an unsupported &gt;1500 capacity trade with &gt;3 hops will trigger a
special warning with instructions on how to SIGTERM using a keyboard. ([`76537b9`](https://github.com/eyeonus/Trade-Dangerous/commit/76537b9d84fc55994970f55f3cf39649c9c6bc5f))

### Unknown

* 10.10.0

python-semantic-release automatic version update. ([`28b9ac5`](https://github.com/eyeonus/Trade-Dangerous/commit/28b9ac5aa1346c79cbfa281c21cdd043ce3cca01))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous ([`e44eb40`](https://github.com/eyeonus/Trade-Dangerous/commit/e44eb403aae990e1e73b6abd0c2a9e613394b944))

* Fix: update MFD (PR#88)

Updates to device_handle to define the type as HANDLE, seems to resolve issue with &#34;ctypes.ArgumentError: argument 1: &lt;class &#39;OverflowError&#39;&gt;: int too long to convert&#34;, at least  on my x52pro.
Also change dll install location as it&#39;s now Logitech, maybe a check can be put in to pull install location from registry?

I know nothing about programming but I&#39;ve been able to fudge this, hope it helps. ([`6e3de0c`](https://github.com/eyeonus/Trade-Dangerous/commit/6e3de0ca6f3fdf13a7ad83b82735b07e4f08a061))


## v10.9.8 (2021-02-05)

### Fix

* fix: update the build semantic, you jerk ([`8ca4e39`](https://github.com/eyeonus/Trade-Dangerous/commit/8ca4e392f7949e106636a1fee90a0d381b8a03e0))

### Refactor

* refactor: small change to trigger the build again.

Last fix commit didn&#39;t build because it was pushed before the previous
one was finished building. ([`b9ebcb5`](https://github.com/eyeonus/Trade-Dangerous/commit/b9ebcb54fca6d9c003013fde50811fa42132b84b))

### Unknown

* 10.9.8

python-semantic-release automatic version update. ([`7b8fc7e`](https://github.com/eyeonus/Trade-Dangerous/commit/7b8fc7ebb92f70b0e18b7b163785e0ef17addc7b))


## v10.9.7 (2021-02-05)

### Fix

* fix: add &#39;VOID OPAL&#39; to corrections

fixes #84 ([`f208023`](https://github.com/eyeonus/Trade-Dangerous/commit/f20802319a503f569d836c8d46ca7231779f5024))

### Unknown

* 10.9.7

python-semantic-release automatic version update. ([`568ff62`](https://github.com/eyeonus/Trade-Dangerous/commit/568ff62e23c57d202962e7e77471a8f8cc417d37))

* Fix: supposed to be Name Case, not lower case. ([`3da326e`](https://github.com/eyeonus/Trade-Dangerous/commit/3da326e1f5556623e7a3b6b6b4fa78a373e035ce))


## v10.9.6 (2021-01-18)

### Fix

* fix: edmc_batch_plug Path issues (#83)

This fixed two bugs in the EDMC Batch set_environment method.
The method used `pathlib.Path` while `pathlib` was not imported as a
module which threw a NameError. Secondly, the method set the
environments filename to a Path object when it should be a string. ([`ef06684`](https://github.com/eyeonus/Trade-Dangerous/commit/ef06684e0534d1d969658e9b55f3a752c502475e))

### Unknown

* 10.9.6

python-semantic-release automatic version update. ([`8a0c3c1`](https://github.com/eyeonus/Trade-Dangerous/commit/8a0c3c1ad93784c1c11425ab16f890baba6e017f))


## v10.9.5 (2021-01-09)

### Fix

* fix: MaxGainPerTon shouldn&#39;t be set by default. ([`00c558c`](https://github.com/eyeonus/Trade-Dangerous/commit/00c558cf7f31fb82deb4ca176b43ca16db130559))

### Unknown

* 10.9.5

python-semantic-release automatic version update. ([`7c3fa8e`](https://github.com/eyeonus/Trade-Dangerous/commit/7c3fa8e883929e744bb8bf0645099dcde02516ba))


## v10.9.4 (2020-12-19)

### Fix

* fix: Galactic Travel Guides are not deleted, just rare. ([`b20b9d0`](https://github.com/eyeonus/Trade-Dangerous/commit/b20b9d0abbcf4fb1d371715bc47da2e625a2cb23))

### Unknown

* 10.9.4

python-semantic-release automatic version update. ([`006b58b`](https://github.com/eyeonus/Trade-Dangerous/commit/006b58b448ff915af2e33f73a8665de608d22144))


## v10.9.3 (2020-12-16)

### Fix

* fix: Hopefully actually fix Travis this time. ([`970d721`](https://github.com/eyeonus/Trade-Dangerous/commit/970d721c2b512fff096f4bc76c15716f35a03633))

* fix: Make Travis work again.

Also add new 3.8 and remove soon to be unsupported 3.4 python versions ([`13addad`](https://github.com/eyeonus/Trade-Dangerous/commit/13addad48d2bb5f58b7e5c09c0ebdd5eedd74bd0))

* fix: ensure folder exists before attempting to write file

fixes #78 ([`2de883f`](https://github.com/eyeonus/Trade-Dangerous/commit/2de883f62b1460c28da006d972da6225a9bd882f))

### Unknown

* 10.9.3

python-semantic-release automatic version update. ([`73dbcb8`](https://github.com/eyeonus/Trade-Dangerous/commit/73dbcb862769b541f1706bd9144a19cda12d3f4f))

* Update dev.txt ([`3fe11f7`](https://github.com/eyeonus/Trade-Dangerous/commit/3fe11f756a40328b44cac912264342db30e35a9b))

* 10.9.2

python-semantic-release automatic version update. ([`1ed15f6`](https://github.com/eyeonus/Trade-Dangerous/commit/1ed15f6805213495dd7dd0c73e6dd803b66a25c2))

* Update .travis.yml ([`8348b0a`](https://github.com/eyeonus/Trade-Dangerous/commit/8348b0aa19d1f383e517f7b7df18df49c8e1befe))

* Update .travis.yml ([`d150824`](https://github.com/eyeonus/Trade-Dangerous/commit/d1508245ee5b17c52f32dbac5f4714002f18ad5c))

* Update .travis.yml ([`619b1e9`](https://github.com/eyeonus/Trade-Dangerous/commit/619b1e9eab64b59e9b2b92462d88126d5806665c))

* Update dev.txt ([`8a3abae`](https://github.com/eyeonus/Trade-Dangerous/commit/8a3abae7c6721f95a664e21166e470db8820b2c7))

* Update dev.txt ([`1695a1e`](https://github.com/eyeonus/Trade-Dangerous/commit/1695a1e652550636b0ca513d8c2792b1bc3ddd92))

* 10.9.1

python-semantic-release automatic version update. ([`b084ad7`](https://github.com/eyeonus/Trade-Dangerous/commit/b084ad7d449913123948fc29c38cf730934f2c1a))

* Update .travis.yml ([`de7ba27`](https://github.com/eyeonus/Trade-Dangerous/commit/de7ba27ff345dbe22cadb7109a180537de74ea2b))

* Update .travis.yml ([`e1db93a`](https://github.com/eyeonus/Trade-Dangerous/commit/e1db93af4314bec963a2e3a4c363c40bca3804f6))

* Update .travis.yml ([`363ebf7`](https://github.com/eyeonus/Trade-Dangerous/commit/363ebf7d453d9eb4480d0d105d4169baddbaea14))

* Update .travis.yml ([`0e1eaff`](https://github.com/eyeonus/Trade-Dangerous/commit/0e1eaff171dff7e36c365f7ac8396342135e19e5))


## v10.9.0 (2020-07-17)

### Fix

* fix: one more go at properly fixing required arguments. ([`79ba4f3`](https://github.com/eyeonus/Trade-Dangerous/commit/79ba4f3b65925098f5160e6042dd4e7336a15e69))

### Refactor

* refactor: remove redundant code. ([`bf27c3e`](https://github.com/eyeonus/Trade-Dangerous/commit/bf27c3e43f0644dbb572de3cd467766595d79790))

### Unknown

* 10.9.0

python-semantic-release automatic version update. ([`106bd74`](https://github.com/eyeonus/Trade-Dangerous/commit/106bd7465f1e2d3a2d431cc7986ac37ac84b0360))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous.git into fc_beta ([`40e2fdb`](https://github.com/eyeonus/Trade-Dangerous/commit/40e2fdb8793e4695dd7f205f51f33e7aa18ffddc))


## v10.8.2 (2020-07-17)

### Fix

* fix: make certain hopRoute is a list. ([`27eba0d`](https://github.com/eyeonus/Trade-Dangerous/commit/27eba0d61895380058628fd0eeb6cdebe304fce6))

### Unknown

* 10.8.2

python-semantic-release automatic version update. ([`a3d39b7`](https://github.com/eyeonus/Trade-Dangerous/commit/a3d39b70cd4d3996c82563e5b15659f387e224e4))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous.git into fc_beta ([`657cf9f`](https://github.com/eyeonus/Trade-Dangerous/commit/657cf9f4f4dfb830ec19cf9ff04572db616846a5))


## v10.8.1 (2020-07-17)

### Feature

* feat: add &#39;--fleet-carrier&#39; (&#39;--fc&#39;) option

Functions exactly like &#39;--planetary&#39;, but for fleet carriers.

Allowed values are &#39;YN?&#39;

Fixes 74. ([`339b2af`](https://github.com/eyeonus/Trade-Dangerous/commit/339b2af4e58ef9296a84548605359517511425be))

### Fix

* fix: required args now pass correctly in gui ([`b21aba8`](https://github.com/eyeonus/Trade-Dangerous/commit/b21aba84766e9a7377875e89227eccd418f8814a))

### Unknown

* 10.8.1

python-semantic-release automatic version update. ([`9fccad6`](https://github.com/eyeonus/Trade-Dangerous/commit/9fccad6c2a94bb8bb513334d0520bc2ce57cc8de))


## v10.8.0 (2020-07-01)

### Feature

* feat: Add purge option to eddblink plugin.

The &#39;purge&#39; option will remove all system listings which do not have any
stations in them, such as uninhabited systems that used to have a Fleet
Carrier in them but no longer do.

It is also run whenever using the &#39;systemrec&#39; option. ([`9689ed7`](https://github.com/eyeonus/Trade-Dangerous/commit/9689ed7fc3762084661ebded7e198e335f543403))

### Fix

* fix: Make recent systems also separate, optional update.

Use &#39;systemrec&#39; option in eddblink import plugin. ([`20fb696`](https://github.com/eyeonus/Trade-Dangerous/commit/20fb696335d65773df216f5283fef896951aa496))

### Refactor

* refactor: Better gui entry method. ([`9b5b175`](https://github.com/eyeonus/Trade-Dangerous/commit/9b5b1750f104c10209bd8adc414cf68723f8c684))

### Unknown

* 10.8.0

python-semantic-release automatic version update. ([`858fc60`](https://github.com/eyeonus/Trade-Dangerous/commit/858fc60124484c519f4c651058755ee1b0a28049))


## v10.7.1 (2020-06-30)

### Fix

* fix: always check for new populated systems dump. ([`cce11af`](https://github.com/eyeonus/Trade-Dangerous/commit/cce11afd8f7c398767efa9a29d4bd093ac3e95ac))

### Refactor

* refactor: don&#39;t turn off &#39;system&#39; when &#39;systemfull&#39; is on. ([`a2b9153`](https://github.com/eyeonus/Trade-Dangerous/commit/a2b9153d6e41cba97950fdd9187d22b0d64eef03))

### Unknown

* 10.7.1

python-semantic-release automatic version update. ([`21773a4`](https://github.com/eyeonus/Trade-Dangerous/commit/21773a469339d2b780cc839a7125c38d8cff7949))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous.git ([`a16a7c6`](https://github.com/eyeonus/Trade-Dangerous/commit/a16a7c6b9150d7946b3a3d36d6fc65e823a177ff))


## v10.7.0 (2020-06-30)

### Feature

* feat: &#39;systemfull&#39; option added to eddblink import plugin

Added &#39;systemfull&#39; option, which uses systems.csv, the list all
currently recorded systems, to build the Systems table, which should
mean no FC shows up as being in Unknown Space.

&#39;systemfull&#39; is purely optional and not recommended.

Added systems_recently.csv to processing of Systems.
systems_recently contains all systems- populated or not- that have been
update within the previous 7 days. This will make it less likely a FC
will be marked as being in Unknown Space. ([`9b27a99`](https://github.com/eyeonus/Trade-Dangerous/commit/9b27a9985ff2360c2da5ec65dccea1308a475b63))

### Unknown

* 10.7.0

python-semantic-release automatic version update. ([`4c7ac02`](https://github.com/eyeonus/Trade-Dangerous/commit/4c7ac028d7fc344313695b6756b594590d207a42))


## v10.6.3 (2020-06-30)

### Fix

* fix: Fleet Carriers can be in an unpopulated system.

Added &#34;Unknown Space&#34; system for FCs in a system not in the DB.
&#34;Unknown Space&#34; systems are added with x,y, and z pos of 0. ([`27ab8b3`](https://github.com/eyeonus/Trade-Dangerous/commit/27ab8b397b1276732f1b915cc956792b03bd47ea))

### Refactor

* refactor: Updated server address to use https. ([`9a77295`](https://github.com/eyeonus/Trade-Dangerous/commit/9a77295b39d9368f2ff824a814c701020a3d3ca9))

### Unknown

* 10.6.3

python-semantic-release automatic version update. ([`62a0fb5`](https://github.com/eyeonus/Trade-Dangerous/commit/62a0fb5daba3e2048f5bb06ffda542deee9727ef))


## v10.6.2 (2020-06-30)

### Documentation

* docs: Update README.md (#71)

http://elite.tromador.com/ ([`192502d`](https://github.com/eyeonus/Trade-Dangerous/commit/192502d6d9a443b6e6cee90faf24f24f3d61404e))

* docs: pyenv/pyenv#1375 with Mojave (#67)

Document fix for Mac users who use pyenv Python installation, to get the latest
tcl/tk version working on Mac OS 10.14.6 (Mojave). ([`2edbdf4`](https://github.com/eyeonus/Trade-Dangerous/commit/2edbdf4eec37e605d71a7e88fd4afd818c25e7d8))

### Performance

* perf: Raise warning rather than exiting. ([`3f0b6ff`](https://github.com/eyeonus/Trade-Dangerous/commit/3f0b6ff24982560fb8ccaf5e74d0dad1b2b28fdf))

### Unknown

* 10.6.2

python-semantic-release automatic version update. ([`9d53849`](https://github.com/eyeonus/Trade-Dangerous/commit/9d538493fcd8c6bfa330ad4cc104ea324c944468))

* Document fix for Tkinter error on Mac with pyenv installed python (#66)

Reference: pyenv/pyenv#94 ([`ced02f1`](https://github.com/eyeonus/Trade-Dangerous/commit/ced02f154cd8e0a5c95e66ca459eacc1db3e7d5a))


## v10.6.1 (2019-09-01)

### Fix

* fix: Only run the color command on Windows machines.

It&#39;s not needed on *nix or OSX and throws shell errors when int&#39;s run on
OSX. ([`7538e98`](https://github.com/eyeonus/Trade-Dangerous/commit/7538e9869a225f0e94857900eea77fbe9cc0731a))

### Unknown

* 10.6.1

python-semantic-release automatic version update. ([`3f1357b`](https://github.com/eyeonus/Trade-Dangerous/commit/3f1357b721335c899fc5c6d1a9f42254a014dce8))


## v10.6.0 (2019-08-31)

### Feature

* feat: Color output (only implemented in &#39;run&#39; command thus far.)

When running TD in terminal (command prompt/ powershell for windows users), adding the &#39;--color&#39;  argument to the run command will output the text in color. Color output will be enabled for the other commands as time permits.

(Thanks go to skorn for idea and initial coding.) ([`3cf1dc8`](https://github.com/eyeonus/Trade-Dangerous/commit/3cf1dc8eb623f3a9776243ce38b6fc5405f5e9ea))

### Fix

* fix: missing argument in method call ([`004a6d8`](https://github.com/eyeonus/Trade-Dangerous/commit/004a6d853f89b1b605bd34e78fe2431e65d6f555))

### Unknown

* 10.6.0

python-semantic-release automatic version update. ([`46cc8d7`](https://github.com/eyeonus/Trade-Dangerous/commit/46cc8d7a451e92b26e026d250b2c46eeed477746))


## v10.5.7 (2019-08-31)

### Fix

* fix: Properly implement options with multiple choices.

Was comparing against the wrong var. ([`ba9a940`](https://github.com/eyeonus/Trade-Dangerous/commit/ba9a940dc102de7c0a0438106a83a967f972583b))

### Refactor

* refactor: Formatting fixes. (Indentation) ([`9da641b`](https://github.com/eyeonus/Trade-Dangerous/commit/9da641b38203ad44ba5d87a58d84b9372bc536cd))

### Unknown

* 10.5.7

python-semantic-release automatic version update. ([`0be1517`](https://github.com/eyeonus/Trade-Dangerous/commit/0be15171766c4a9699f2b2b054d3976856f91648))


## v10.5.6 (2019-08-31)

### Fix

* fix: append the argnames for required arguments

Don&#39;t know why I did that, but it was the wrong thing to do. ([`0617187`](https://github.com/eyeonus/Trade-Dangerous/commit/0617187874670630d32791ed7dce930362890f7d))

### Unknown

* 10.5.6

python-semantic-release automatic version update. ([`a970e8d`](https://github.com/eyeonus/Trade-Dangerous/commit/a970e8d36cff9b7c7c1a11bff078687e765adc0b))


## v10.5.5 (2019-06-21)

### Fix

* fix: Remove unused imports ([`4049f57`](https://github.com/eyeonus/Trade-Dangerous/commit/4049f573e1d7c6e9f311582badf177ef7e60742c))

### Unknown

* 10.5.5

python-semantic-release automatic version update. ([`59cca16`](https://github.com/eyeonus/Trade-Dangerous/commit/59cca16ba4d94c75dff0504470ec85588f14c3bb))


## v10.5.4 (2019-06-21)

### Fix

* fix: Use 127.0.0.1, not 127.2.0.1, Because Apple computers are evil.

Fixes #63 ([`1dacb3b`](https://github.com/eyeonus/Trade-Dangerous/commit/1dacb3b6816b6480c3360f8abea7bbb4bf2511c4))

### Unknown

* 10.5.4

python-semantic-release automatic version update. ([`c9c7f87`](https://github.com/eyeonus/Trade-Dangerous/commit/c9c7f872c8ffac0cd81a20b3fbe348c0caee45e2))


## v10.5.3 (2019-06-20)

### Fix

* fix: Implement plugin options subwindow

Now you don&#39;t need to type in every option. Push the button, and a
window will pop up allowing you to simply select which options you&#39;d
like.

Plugin options which require a value, such as the filename to test json
importing with in the case of the edapi plugin&#39;s &#39;test&#39; option, will
show as a text field for typing that parameter in. ([`a471b7a`](https://github.com/eyeonus/Trade-Dangerous/commit/a471b7a107880c915f1ff14f8db63c829ab1217d))

### Unknown

* 10.5.3

python-semantic-release automatic version update. ([`f131801`](https://github.com/eyeonus/Trade-Dangerous/commit/f13180178120a512c0adf8e6a41e8c418c22362e))


## v10.5.2 (2019-06-17)

### Fix

* fix: Set width of tab fields, no more output weirdness.

Hooray. Figured it out. ([`dfca779`](https://github.com/eyeonus/Trade-Dangerous/commit/dfca7791a40c4e70b21a4a6cfc8aa4225c960b3e))

### Unknown

* 10.5.2

python-semantic-release automatic version update. ([`57d0e99`](https://github.com/eyeonus/Trade-Dangerous/commit/57d0e99c7c39855c31f01c706390d404f14499ff))


## v10.5.1 (2019-06-17)

### Fix

* fix: Make the gui actually work when TD is pip installed. ([`5c36944`](https://github.com/eyeonus/Trade-Dangerous/commit/5c3694442e5cbf977e5235dcb4b9345c320ef98b))

### Unknown

* 10.5.1

python-semantic-release automatic version update. ([`56923e0`](https://github.com/eyeonus/Trade-Dangerous/commit/56923e0e3ab9f4ccbff29378c17f6b2b7d4a790a))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous.git ([`b9036e2`](https://github.com/eyeonus/Trade-Dangerous/commit/b9036e2521f55295acc6c0ef4cd3486fe7827ce9))


## v10.5.0 (2019-06-17)

### Documentation

* docs: Update copyright notices with current year.

Man there are a lot. I&#39;m considering removing all but the one on
trade.py and README.md ([`1cf29ad`](https://github.com/eyeonus/Trade-Dangerous/commit/1cf29ad183eaab61f4d417f09b2f26bc6c7e5237))

### Feature

* feat: Beta release of GUI

Just run &#34;trade gui&#34; and tell me what you think. ([`4d56509`](https://github.com/eyeonus/Trade-Dangerous/commit/4d565091aa081eebca1bcc5ccab941cdd0b75b3c))

### Unknown

* 10.5.0

python-semantic-release automatic version update. ([`cbf8493`](https://github.com/eyeonus/Trade-Dangerous/commit/cbf8493b5c764b271311f7ad01865ddd4df8f635))

* beta: Redirect output of command to output tab in GUI.

It&#39;s kind of funky, for why I don&#39;t know, but it works, which at this
point is good enough. Working towards a beta, after all, not a finished
product.

With this bit done, it is now officially time to release this thing as a
beta. W00t and stuff. ([`d890e22`](https://github.com/eyeonus/Trade-Dangerous/commit/d890e22ce97f0044052bc74379950740419388a1))

* beta: Added Tabbed frame with &#34;Help&#34; and &#34;Output&#34; frames

general bug fixing, clean up, and refactoring.

The &#34;Help&#34; pane has been moved to a tab, and there is an &#34;OutPut&#34; tab as
well, although it doesn&#39;t work yet. Getting there. ([`d881b8e`](https://github.com/eyeonus/Trade-Dangerous/commit/d881b8eea5179c78452176a5582ed4422bd2e1fd))

* beta: Implement runTD

&#39;--options&#39; is currently a text entry, will be changed in future to be
procedural generated like the TD arguments currently are.

&#39;--credits&#39; is also currently a text entry. TD allows a number followed
by K,M,G. Numeric entries don&#39;t allow any letters, text entries allow
all, so for now it&#39;s text.

The output still goes straight to the terminal, that&#39;s next on the list. ([`6f133d9`](https://github.com/eyeonus/Trade-Dangerous/commit/6f133d9406fe28bdefb14cd588b839e8ad134c55))

* beta: Finish implementing makeWidget. (Excepting &#39;--option&#39;)

All that remains is implementing the &#39;--option&#39; widget-making code,
possibly dealing with a complication involving arguments in the
&#39;station&#39; command having the same name but different type as in other
commands, and implementing the whole running of the commands.

Implementing the running of commands is next on the list, the other two
can be worked on post-release of the beta. ([`451b712`](https://github.com/eyeonus/Trade-Dangerous/commit/451b712cd7c1e28b3c8552326c93b593eea73195))

* beta: Major reformat to argument dictionary, now includes widget type

The former reqArg and optArg dicts have been merged along with the
common arguments into the single allArgs dict.

The dict formerly known as allArgs is now known as argVals to accomodate
the above as well as more accurately reflect its purpose.

During the creation of the dict, each argument will have the appropriate
widget information for the to-be-completed makeWidget method.

During population of the arguments panels, makeWidget will be used to
perform the actual population. Currently only arguments that take a
string are implemented as a proof-of-concept.

When makeWidget is completed, the common arguments will added to the
window using makeWidget as well.

Current TODO list:

1) Finish implementing makeWidget and use it for populating /all/
arguments, including top-level. The &#39;--option&#39; argument will be treated
as a string for now.

2) Implement runTD, which includes grabbing the output and redirecting
it to the GUI. At this point the help panel will be adjusted to be a
tabbed display, so that the command output can be on a separate tab.
(Create new tabs as needed, close button for user?)

---- Initial beta release ----

3) Fully implement the &#39;--option&#39; argument, possibly by having an entry
containing the current option list, and a button that will open a sub
window containing all the options for the chosen plugin.

4) Fix discovered bugs.

5) Implement beta tester feedback until no longer in beta.

---- Initial feature release ----

6) Fix discovered bugs.

7) Implement worthwhile user feedback if I feel like it and have time. ([`3f73856`](https://github.com/eyeonus/Trade-Dangerous/commit/3f73856189c86efd412f6641d9560198210d5f34))

* beta: Prep work for determining widget types and storing values. ([`7782746`](https://github.com/eyeonus/Trade-Dangerous/commit/77827466a5d870ff8290103a1c968347dd90302f))

* beta: Add appJar to the install requirements.

Hopefully, this will make it automagically install when upgrading via
pip. ([`ed18bbd`](https://github.com/eyeonus/Trade-Dangerous/commit/ed18bbd6cadac535e1341d9f2a7b8117b5ec4284))

* beta: Store MutuallyExclusiveGroup data to optArg dict.

Members of a MutuallyExclusiveGroup now have the names of the other
members of the group stored as a list under &#39;excludes&#39;.

This will be used to reset arguments to default/off when a different
arguments excludes it.

Worked out the function design of the various kinds of arguments, to be
implemented in the future.

Fixed &#39;--credit&#39; and &#39;--capacity&#39; required arguments for the &#39;run&#39;
command to show they are numbers. Probably need to make a verification
method for them as well as the ints and &#39;credits&#39;s floating in the
optional arguments. ([`06562d7`](https://github.com/eyeonus/Trade-Dangerous/commit/06562d7e8b30652dd28d79e6dbf21efdf0006ea6))

* beta: Add remaining common arguments to window.

This is not the final design, this will probably change eventually.
Right now I&#39;m focusing purely on functionality and space. When
functionality is complete, visuals will get a look.

Regarding functionality, all that remains of the basics is populating
the optional arguments, enabling the running of user-chosen TD commands,
and redirecting TD&#39;s output to the window.
Upon finishing those bits, TD GUI will be precisely as functional as TD
CLI, and possibly a bit easier to use, though not nearly as user
friendly as TDHelper.
This point will mark the first public release of the GUI to the main
branch, although it will still be considered in Beta status.

There&#39;s more planned after that point. ([`d458a19`](https://github.com/eyeonus/Trade-Dangerous/commit/d458a19c22d7da21d2c7cd439b8c435973724d58))

* beta: include plugin list and options for plugins in dict ([`b9ca6f8`](https://github.com/eyeonus/Trade-Dangerous/commit/b9ca6f856d596b630ba17aed621f31ec76c4d1c7))

* beta: reflect mutual exclusivity of --quiet and --detail in gui ([`a9fd051`](https://github.com/eyeonus/Trade-Dangerous/commit/a9fd05197f2b71dabee5252105d90f75791e6332))

* beta: Minor look changes. ([`03faa4f`](https://github.com/eyeonus/Trade-Dangerous/commit/03faa4f55f08146ceb6ef3d8f7e3afd1c1eab49a))

* beta: Remove a completed TODO. ([`b036441`](https://github.com/eyeonus/Trade-Dangerous/commit/b036441d41471fe66303faf2da1b354fbdf7a834))

* beta: Some work populating required and common args.

The required arguments section is finished, in terms of existing and
functioning correctly.

Whilst working on the debug and detail common options, I noticed that
the selectors were acting backwards, so I had to do a bit of a library
overwrite to fix that weirdness.

If you test this, let me know if the number increases when pressing the
up arrow and decreases when pressing the down arrow. This is the
intended behaviour that is caused by the overwrite.

The normal behaviour is that increase is down arrow, and decrease is up
arrow, at least for me on my machine.

You can check out the difference by (un)commenting the following two
lines:
```
80: gui._populateSpinBox = _populateSpinBox
81: gui.setSpinBoxPos = setSpinBoxPos
``` ([`a521eae`](https://github.com/eyeonus/Trade-Dangerous/commit/a521eae59c85df4ac67feb1ded393703324815c7))

* beta: Flatten command dicts, store by argument name.

Results in:
        buy:{
            &#39;name&#39;:{[[values]]},
            &#39;--supply&#39;:{[[values]]},
            &#39;--near&#39;:{[[values]]},
            &#39;--ly&#39;:{[[values]]},
            &#39;--limit&#39;:{[[values]]},
            &#39;--avoid&#39;:{[[values]]},
            &#39;--pad-size&#39;:{[[values]]},
            &#39;--no-planet&#39;:{[[values]]},
            &#39;--planetary&#39;:{[[values]]},
            &#39;--black-market&#39;:{[[values]]},
            &#39;--one-stop&#39;:{[[values]]},
            &#39;--price-sort&#39;:{[[values]]},
            &#39;--units-sort&#39;:{[[values]]},
            &#39;--gt&#39;:{[[values]]},
            &#39;--lt&#39;:{[[values]]}
        }

rather than the former:
    buy:[
        { &#39;name&#39;:{[[values]]} },
        { &#39;--supply&#39;:{[[values]]} },
        { &#39;--near&#39;:{[[values]]} },
        { &#39;--ly&#39;:{[[values]]} },
        { &#39;--limit&#39;:{[[values]]} },
        { &#39;--avoid&#39;:{[[values]]} },
        { &#39;--pad-size&#39;:{[[values]]} },
        [
            { &#39;--no-planet&#39;:{[[values]]} },
            { &#39;--planetary&#39;:{[[values]]} }
        ],
        { &#39;--black-market&#39;:{[[values]]} },
        [
            { &#39;--one-stop&#39;:{[[values]]} },
            { &#39;--price-sort&#39;:{[[values]]} },
            { &#39;--units-sort&#39;:{[[values]]} }
        ],
        { &#39;--gt&#39;:{[[values]]} },
        { &#39;--lt&#39;:{[[values]]} }
    ], ([`2abb3a2`](https://github.com/eyeonus/Trade-Dangerous/commit/2abb3a2cfbef0f430ecf01f64dc73d79406dcd4c))

* beta: Common Arguments dict added. ([`036f909`](https://github.com/eyeonus/Trade-Dangerous/commit/036f9095277cd87f287cb163eb815679ce2deb9e))

* beta: Use option as key, instead.

{&#39;name&#39;: {&#39;help&#39;: &#39;Items or Ships to look for.&#39;, &#39;nargs&#39;: &#39;+&#39;}}

rather than

{&#39;help&#39;: &#39;Items or Ships to look for.&#39;, &#39;nargs&#39;: &#39;+&#39;, &#39;arg&#39;: &#39;name&#39;}

Among other things, this makes it easier to access the name of the
option. ([`897d323`](https://github.com/eyeonus/Trade-Dangerous/commit/897d3235a8308404cf40757246f5625b982f762b))

* beta: Re-implement everything done before API switch.

update command had a mutually exclusive group consisting of one argument
and another mutually existing group consisting of four other arguments.
All five arguments are all mutually exclusive, so I removed the group of
groups and put them all in the same mutually exclusive group.

buildcache had the only instance of the shortcut being listed before the
command ( &#34;&#39;-f&#39;, &#39;--force&#39;&#34; rather than &#34;&#39;--force&#39;, &#39;-f&#39;&#34;), so that&#39;s
been fixed to conform with the normal.

We now have a dict of each option, for each command, which is about
where we were before the switch to appJar. ([`e3c16f7`](https://github.com/eyeonus/Trade-Dangerous/commit/e3c16f7d62b9a3515fd59a5f439be4a50efd20ba))

* beta: switch to more well-featured GUI API

Now using appJar instead of pySimpleGUI.

The look is slightly different, but that&#39;s not super important right
now. ([`7229e92`](https://github.com/eyeonus/Trade-Dangerous/commit/7229e9243f29d5e4fad34028112d09f61b7c6422))

* beta: Well, I got this far, now I&#39;m stuck.

I might be trying to do something that API can&#39;t do.

In which case I may need to try a different API, because that&#39;s
unacceptable.

In the meantime, this is what I&#39;ve managed today. ([`80cb16f`](https://github.com/eyeonus/Trade-Dangerous/commit/80cb16fa882c5b16c19219e64d7d41afec173856))


## v10.4.8 (2019-05-29)

### Fix

* fix: Don&#39;t set fallback on failure of ship or live listings dl...

Completely ignore fallback option wrt ships index, now will always try
to download, only uses template on failure to open.

refactor: Switch back to beta for the ships index. Better suited so says
Trom.
:) ([`ab6e48e`](https://github.com/eyeonus/Trade-Dangerous/commit/ab6e48e5b3a1bca82a4b7a3d7c5962b9d3f77606))

### Unknown

* 10.4.8

python-semantic-release automatic version update. ([`02cffb9`](https://github.com/eyeonus/Trade-Dangerous/commit/02cffb934b534dba21492c1dec79cccda895c18e))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous.git ([`416136c`](https://github.com/eyeonus/Trade-Dangerous/commit/416136cbc8cd7733dfc0c8069814ee65404cd334))


## v10.4.7 (2019-05-28)

### Fix

* fix: Stop always using the template ship index when fallback enabled

Check to see if the attempt to download the ship index was successful,
and if so, do not use the template, even if the fallback option is
enabled. ([`54897cb`](https://github.com/eyeonus/Trade-Dangerous/commit/54897cb0e8ffb20c0fc6455f4bcdca482ff1f5ed))

### Refactor

* refactor: Update ship index to not use the beta site. ([`49ce095`](https://github.com/eyeonus/Trade-Dangerous/commit/49ce095416be1e505307f3bac14b4b5867c38c13))

### Unknown

* 10.4.7

python-semantic-release automatic version update. ([`19454ea`](https://github.com/eyeonus/Trade-Dangerous/commit/19454eaca835fb484dd8c95c71b0b50616ecbf71))


## v10.4.6 (2019-05-23)

### Fix

* fix: Give TD web requests a User-Agent header.

Fixes #61 ([`0a10cec`](https://github.com/eyeonus/Trade-Dangerous/commit/0a10ceceebc4228b39494310d88b6997f8a36028))

### Unknown

* 10.4.6

python-semantic-release automatic version update. ([`0fd2d68`](https://github.com/eyeonus/Trade-Dangerous/commit/0fd2d683b9b8ecb4d8825529ab88bf4e40e1196e))


## v10.4.5 (2019-05-23)

### Fix

* fix: Update ship index URL. ([`c455594`](https://github.com/eyeonus/Trade-Dangerous/commit/c4555942c2cca0da8a49a470f2165402f50e5457))

### Unknown

* 10.4.5

python-semantic-release automatic version update. ([`7cb764d`](https://github.com/eyeonus/Trade-Dangerous/commit/7cb764d8b245e955efe1283cccd90c6e1aa86dec))


## v10.4.4 (2019-05-23)

### Chore

* chore: include fix-indent.sh bash script

May not have figured out how to get pylint to correctly detect missing
indentation on blank lines, or how to get any of the auto-formatters to
correctly indent them, but at least there&#39;s now a bash script that will
take care of the indentation for all the .py files when it&#39;s run. ([`f088f25`](https://github.com/eyeonus/Trade-Dangerous/commit/f088f256c28da2e0767c12b6009b0a86fe46587b))

### Fix

* fix: Don&#39;t crash when attempting to download non-existent file.

Fixes #21.

Specifically, it fixes the crash that happens because of the ship&#39;s
index file no longer existing of the EDCD coriolois data github.

So the Ships database won&#39;t be getting updated until a new source is
found to download from.

For now the latest version available before the removal is stored as a
template.

TD will get another update once we have a new site from which to get the
index again. ([`97c254d`](https://github.com/eyeonus/Trade-Dangerous/commit/97c254de2f18cc45cb341ba3e7f34127baef5136))

### Style

* style: found a few more missing indents ([`2aa12d0`](https://github.com/eyeonus/Trade-Dangerous/commit/2aa12d01840fffd5b3657609a38a020a7ae5f6d1))

### Test

* test: Remove test_transfers.py from tests

It fails when Tromador&#39;s server isn&#39;t up, even though there&#39;s nothing
wrong with the code.

Since the code it supposedly checks is never touched anyway, and it can
easily put out a false positive, it&#39;s gone now. ([`4867f3b`](https://github.com/eyeonus/Trade-Dangerous/commit/4867f3bb50ba8dab3099c9c5d476e2d8bbe82c27))

### Unknown

* 10.4.4

python-semantic-release automatic version update. ([`d5a9b86`](https://github.com/eyeonus/Trade-Dangerous/commit/d5a9b860890d8cca16c983f35819df3cd67b8680))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous.git ([`4a06159`](https://github.com/eyeonus/Trade-Dangerous/commit/4a0615990c510cd047cb276143cbd3c7dc54a78a))


## v10.4.3 (2019-02-26)

### Fix

* fix: properly set profile save path

Need to make sure it works correctly with non-TDH profile saving too,
Jon.

Fixes #57 ([`55274fe`](https://github.com/eyeonus/Trade-Dangerous/commit/55274fefda798124714015f89d6dc803ce24544d))

### Unknown

* 10.4.3

python-semantic-release automatic version update. ([`159cdb1`](https://github.com/eyeonus/Trade-Dangerous/commit/159cdb13d7ecf1b9504624abd1cd74102f4b9336))


## v10.4.2 (2019-02-26)

### Fix

* fix: unable to save tdh profile

Reverts change introduced unintentionally by
fca7f2698a5ac83dd4011c4dcd3379d9cbed0274 ([`248a4fb`](https://github.com/eyeonus/Trade-Dangerous/commit/248a4fba804e7ac99e279a678d622ce5acbc4577))

### Unknown

* 10.4.2

python-semantic-release automatic version update. ([`47d3ace`](https://github.com/eyeonus/Trade-Dangerous/commit/47d3aceaa6a3b3c37ea321f32190fbd5c48fcda8))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous.git ([`d77b728`](https://github.com/eyeonus/Trade-Dangerous/commit/d77b7284736bf944f032b8f7829fe6fabe59c3de))


## v10.4.1 (2019-02-26)

### Fix

* fix: error when trying to insert rare items that already exist in table

In this case, I don&#39;t think &#34;INSERT OR REPLACE&#34; is a horrible idea. ([`20d64c6`](https://github.com/eyeonus/Trade-Dangerous/commit/20d64c6f999e0108f4f1e4e56f6ac92facc08a52))

### Unknown

* 10.4.1

python-semantic-release automatic version update. ([`ec24509`](https://github.com/eyeonus/Trade-Dangerous/commit/ec245096355c27b9670a9ca89b0e54a707587e1a))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous.git ([`97779a3`](https://github.com/eyeonus/Trade-Dangerous/commit/97779a34819066a84742933313a70f545e8318b1))


## v10.4.0 (2019-02-26)

### Feature

* feat: Allow rare items to be in the normal item table.

This change will enable rare items to be included in the market
listings. ([`6a8ddef`](https://github.com/eyeonus/Trade-Dangerous/commit/6a8ddefb6d68e219bd95f615a18e5f20a774b27c))

### Fix

* fix: generate RareItem table after import

The RareItem table never got filled in, now it is. Oops. ([`6425188`](https://github.com/eyeonus/Trade-Dangerous/commit/6425188d46ab1b8f11e85f3d616b1b1540ee1e6a))

### Refactor

* refactor: &#39;option == x or option == y ...&#39; =&gt; &#39;option in (x,y,z)&#39; ([`601355d`](https://github.com/eyeonus/Trade-Dangerous/commit/601355d0eae03617e39edfd7e747b9198537f3d7))

* refactor: update journal plugin wrt station types

Correctly identify CraterPort and CraterOutpost station types as
planetary.

Future planetary station types can be included by simply adding them to
planetTypeList. ([`070fb84`](https://github.com/eyeonus/Trade-Dangerous/commit/070fb843d948c1c8175c23c6329185432e656346))

* refactor: correct Fdev warning in edcd plugin ([`e80a3ad`](https://github.com/eyeonus/Trade-Dangerous/commit/e80a3adbd1e855d4032a81b93f3409438b20f85b))

### Style

* style: whitespace normalizing ([`32c75d2`](https://github.com/eyeonus/Trade-Dangerous/commit/32c75d28317b5ea7f63f1956d1915901a478f96b))

* style: Apply preferred indenting to all files.

Blank lines should be indented to the same level as the line immediately
after.

Ex:
```
........return
....
....def newFunc()
```

Performed automatically on all files using the following Linux bash
command:
```
find * -type f -name &#34;*.py&#34; -print0 | xargs -0 sed -i -e &#39;/^ *$/{N;s/^
*\n\( *\)\(.*\)/\1\n\1\2/}&#39;
``` ([`14c84c6`](https://github.com/eyeonus/Trade-Dangerous/commit/14c84c66554167ba8edf8109f81b76027ea0af79))

### Unknown

* 10.4.0

python-semantic-release automatic version update. ([`befa982`](https://github.com/eyeonus/Trade-Dangerous/commit/befa9827ba3fd7d0eb774eb16fc4dc3841be7060))


## v10.3.1 (2019-02-25)

### Fix

* fix: skip stations that are not in the DB when importing listings

Thanks go to Bernd for the code work.

Fixes #56 ([`34220dc`](https://github.com/eyeonus/Trade-Dangerous/commit/34220dc3b201c4471f117a091944c0884f670c22))

### Unknown

* 10.3.1

python-semantic-release automatic version update. ([`3723336`](https://github.com/eyeonus/Trade-Dangerous/commit/3723336d358ec490a65b1eefdfaedd32d5327039))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous.git ([`f496279`](https://github.com/eyeonus/Trade-Dangerous/commit/f49627946f979fd664e254fd81d341e4f99fdd36))


## v10.3.0 (2019-02-20)

### Feature

* feat: add &#39;TD_SERVER&#39;, &#39;TD_FALLBACK&#39;, and &#39;TD_SHIPS&#39; env_vars

TD_SERVER = Location of the TD server.
(Currently &#39;http://elite.tromador.com/files/&#39;.)

TD_FALLBACK = Location of the EDDB.io server.
(Currently &#39;https://eddb.io/archive/v6/&#39;.)

TD_SHIPS = Location of EDCD ship info file.
(Currently &#39;https://raw.githubusercontent.com/EDCD/
            coriolis-data/master/dist/index.json    &#39;.)

Setting the environment variable allows updating these web addresses by
the user without needing to wait for TD to update.


refactor: set BASE_URL default to &#39;http://elite.tromador.com/files/&#39;
fixes #55


revert: 1c4d186
Apparently caused by developer error and wasn&#39;t a necessary change. ([`5e92257`](https://github.com/eyeonus/Trade-Dangerous/commit/5e92257dd6f45bb653bfb128572f78b838c5241d))

### Unknown

* 10.3.0

python-semantic-release automatic version update. ([`48ee104`](https://github.com/eyeonus/Trade-Dangerous/commit/48ee104715b2bdaca7cb9af8a3c21e0a3c6e4c41))


## v10.2.2 (2019-02-15)

### Fix

* fix: Correctly check for $TD_EDDB

In python&#39;s &#39;x if true else y&#39;, x is evaluated first, then the if
statement is evaluated, and only when the if statement is false does y
get evaluated.

Path(os.environ.get(&#39;TD_EDDB&#39;) = NoneType) will cause the program to
error before even getting to the if statement. ([`1c4d186`](https://github.com/eyeonus/Trade-Dangerous/commit/1c4d186be29379217eab1d27cf72915c5c74e5c0))

### Unknown

* 10.2.2

python-semantic-release automatic version update. ([`921b0bc`](https://github.com/eyeonus/Trade-Dangerous/commit/921b0bcbe32f2668520dffca8c3094b27e3b8264))


## v10.2.1 (2019-02-15)

### Fix

* fix: avoid TypeError if TD_EDDB is not set

Path(None) raises a TypeError.
Test for missing TD_EDDB as well as set.

fixes #51 ([`cd41144`](https://github.com/eyeonus/Trade-Dangerous/commit/cd41144a1f875dda2fea189dc97831c5edd762ad))

### Style

* style: Restore whitespace to eddblink_plug.py ([`6d0de5f`](https://github.com/eyeonus/Trade-Dangerous/commit/6d0de5faba85dbe51f47f8e888b16d2c39a844ac))

### Unknown

* 10.2.1

python-semantic-release automatic version update. ([`c70880f`](https://github.com/eyeonus/Trade-Dangerous/commit/c70880f11b07de158870fd7c98dfa53db93f6adf))


## v10.2.0 (2019-02-14)

### Chore

* chore: stop trying to deploy pull-request


Trying to deploy a pull request will fail the job. ([`d7a4fb3`](https://github.com/eyeonus/Trade-Dangerous/commit/d7a4fb3dbd74ecbea4c04a79216796820d69b966))

### Feature

* feat: Add environment variable for setting location of &#39;eddb&#39; folder.

If set, the &#34;dump files&#34; will be stored to the path set by TD_EDDB. It
will not be in an &#39;eddb&#39; sub-folder, but the specific path set by the
environment variable.

(listings.csv =&gt; $TD_EDDB\listings.csv)

If not, the &#34;dump files&#34; will be stored in the &#39;data&#39; folder (which
itself may be set via TD_DATA) in an &#39;eddb&#39; sub-folder.

(listings.csv =&gt; $TD_DATA\eddb\listings.csv) ([`930e2e5`](https://github.com/eyeonus/Trade-Dangerous/commit/930e2e5ba3571ff477b234800cc8598c046bcc4f))

### Fix

* fix: Make sure eddb path is path, not string, when set via env_var ([`6204486`](https://github.com/eyeonus/Trade-Dangerous/commit/620448696c88ee209768b696383d2811e9d62a0c))

* fix: revert d7a4fb3

TEST BEFORE YOU PUSH, PETER ([`2f553a8`](https://github.com/eyeonus/Trade-Dangerous/commit/2f553a81f08008145838facd941d31307d3c0659))

### Refactor

* refactor: Remove maddavo.

It&#39;s not used anymore. It doesn&#39;t work with the site being inactive.

It is therefore useless and shall be deleted forthwith. ([`75d6f36`](https://github.com/eyeonus/Trade-Dangerous/commit/75d6f364bb09d3fc2f7cb6f4fe5b92683705dd0b))

### Style

* style: restore whitespace on all top-level files

I&#39;ll get to the rest eventually.

Blank lines should have whitespace to the same level as the line
immediately following:

```
    if something:
#This is the wrong amount of whitespace
        stuff()
        more_stuff()
#This is the wrong amount of whitespace
    while happening:
```

```
    if something:
        #This is the correct amount of whitespace
        stuff()
        more_stuff()
    #This is the correct amount of whitespace
    while happening:
``` ([`d509fda`](https://github.com/eyeonus/Trade-Dangerous/commit/d509fda783970ee0754752a79369b4d36c346258))

### Unknown

* 10.2.0

python-semantic-release automatic version update. ([`767521b`](https://github.com/eyeonus/Trade-Dangerous/commit/767521bac7d4b0f06f600944cb7bfd0fa3ba54b3))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous.git ([`6f778d9`](https://github.com/eyeonus/Trade-Dangerous/commit/6f778d910eecba5e625b5d2ca712e51170fc59f4))


## v10.1.2 (2019-02-14)

### Fix

* fix: Unable to save profile.&lt;current_time&gt;.json&#34; ([`fca7f26`](https://github.com/eyeonus/Trade-Dangerous/commit/fca7f2698a5ac83dd4011c4dcd3379d9cbed0274))

### Unknown

* 10.1.2

python-semantic-release automatic version update. ([`78329ee`](https://github.com/eyeonus/Trade-Dangerous/commit/78329eee0f76d6132e3f4571b957d76f92c513bc))


## v10.1.1 (2019-02-14)

### Fix

* fix: Unable to save tdh_profile.json ([`a2abe01`](https://github.com/eyeonus/Trade-Dangerous/commit/a2abe01ec25347191ac792f56ac966ff8533dfdc))

### Unknown

* 10.1.1

python-semantic-release automatic version update. ([`6e9cf97`](https://github.com/eyeonus/Trade-Dangerous/commit/6e9cf9792668572dd686b8159436c6e064811995))


## v10.1.0 (2019-02-13)

### Feature

* feat: automatically update Added.csv, RareItem.csv, TradeDangerous.sql

refactor: restore whitespace to tradedb.py

The template files may need updating, and if that is the case, any TD
database will need their copy updated as well.

Since TD detects changes to the &#39;cache&#39;, any updates to these files will
be integrated into TD the next time it is run.

Changes to the SQL will likely require doing a &#39;clean&#39; run with the
eddblink plugin as they are often breaking changes. ([`fe82c3a`](https://github.com/eyeonus/Trade-Dangerous/commit/fe82c3a503679bc63fdc1a95fd06849c377b89f4))

### Refactor

* refactor: remove template folder environment variable

The template folder contains the .sql file that is needed to build TD&#39;s
database.

TD copies these files whenever it needs to create a new database.

It is vital that these files exist and be correctly pointed to in order
for TD to work.

It makes absolutely no sense to make it possible for the user to even
accidentally point TD at a non-existant path or even an existing one
that simply doesn&#39;t have those files, and there is no need to have these
template files for any purpose other than that of TD using them to
create a new database.

In summary:
having this environment variable:
  usefulness: &lt;=0
  potential harm: &gt;0 ([`b388f60`](https://github.com/eyeonus/Trade-Dangerous/commit/b388f606cd8b4ce8d765034ff661e27e1cb1ee68))

### Unknown

* 10.1.0

python-semantic-release automatic version update. ([`18cf0ea`](https://github.com/eyeonus/Trade-Dangerous/commit/18cf0eaef4b0b6061df367ddc4d1c81c993d91ca))


## v10.0.3 (2019-02-13)

### Chore

* chore: Fix same typo in setup.py ([`d53bb14`](https://github.com/eyeonus/Trade-Dangerous/commit/d53bb1414b231d250c184b12a8975ddfd3430b8a))

* chore: Change autoversioning commit message.

This and previous commits combined fixes #32 ([`24f26c6`](https://github.com/eyeonus/Trade-Dangerous/commit/24f26c68ab523a219b0e1888b7ad266d24d0ea54))

* chore: Remove debug prints from travis.yml ([`5dd2d6d`](https://github.com/eyeonus/Trade-Dangerous/commit/5dd2d6d7c6b7c85dd5e47b4d6d7471a230cb9e75))

### Documentation

* docs: Fix typo in README.md ([`de0f4dc`](https://github.com/eyeonus/Trade-Dangerous/commit/de0f4dc378e467f1cb8fdb4a532d2120e38da4b8))

### Fix

* fix: package_data no longer pointing to wrong files.

This fixes the problem where the .sql file is not installed. ([`efc28f7`](https://github.com/eyeonus/Trade-Dangerous/commit/efc28f7dd3824a3e984e6d71c62e31af20dc5021))

* fix: include all packages

find_packages doesn&#39;t find misc or templates.

I don&#39;t think templates is needed, but batter safe than sorry, and misc
/IS/ needed.

M&lt;anually creating the packages list should fix the problem. ([`1595a3c`](https://github.com/eyeonus/Trade-Dangerous/commit/1595a3c096319eb419d24e746d2ebd503bcd1f7f))

* fix: Correct entry point. ([`c65f3bf`](https://github.com/eyeonus/Trade-Dangerous/commit/c65f3bf14891d2671ae56c2b70dd4fbf83cc984d))

### Refactor

* refactor: Don&#39;t include templates ([`d1c4226`](https://github.com/eyeonus/Trade-Dangerous/commit/d1c4226d67c45fde5f59edba4ffd143aa5218d63))

### Unknown

* 10.0.3

python-semantic-release automatic version update. ([`399112e`](https://github.com/eyeonus/Trade-Dangerous/commit/399112e36838b99c74f09476e8d75692f75d13d0))

* 10.0.2

python-semantic-release automatic version update. ([`857dda4`](https://github.com/eyeonus/Trade-Dangerous/commit/857dda4b7589304b7b64b4628d7f70b1430891c8))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous.git ([`b9d0e89`](https://github.com/eyeonus/Trade-Dangerous/commit/b9d0e893412fcd54f5eb3231236f715a68d63bb8))

* 10.0.1

python-semantic-release automatic version update. ([`5ab8274`](https://github.com/eyeonus/Trade-Dangerous/commit/5ab8274ebf4aa5f5738f9fb4fc99d131ef260978))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous.git ([`210b197`](https://github.com/eyeonus/Trade-Dangerous/commit/210b197e74ccc5523dbf4080c8993d0907adc125))


## v10.0.0 (2019-02-09)

### Breaking

* feat: Publish to pypi

Assuming everything actually works now.

BREAKING CHANGE:

API now accessed as &#39;cli.trade&#39;, rather than &#39;trade.main&#39;. ([`097dbf6`](https://github.com/eyeonus/Trade-Dangerous/commit/097dbf67e13fc5a8876a088462d05494b28f208a))

### Chore

* chore: revert last two commits

Time to ask about this upstream. ([`a44ca91`](https://github.com/eyeonus/Trade-Dangerous/commit/a44ca9149a0d8c06bab398fec8b383b71664f351))

* chore: Okay, try it fully local. ([`1803de4`](https://github.com/eyeonus/Trade-Dangerous/commit/1803de4769fff81f437d8c7d993997a9f8f4e7f5))

* chore: Try assigning the env again. ([`5798f4c`](https://github.com/eyeonus/Trade-Dangerous/commit/5798f4c5c22902492d8b82a7a0326cffe4adae00))

* chore: Check value of $PYPI_USERNAME before and after publish

The env is definitely set, so why is it acting like it&#39;s not? ([`d619bfb`](https://github.com/eyeonus/Trade-Dangerous/commit/d619bfb78d982aa21d45a6de9bab395af4202429))

* chore: Print $PYPI_USERNAME

For some reason it&#39;s trying to push to
&#39;https://github.com/$PYPI_USERNAME/Trade-Dangerous.git/&#39;

Which is wrong. ([`0f241f5`](https://github.com/eyeonus/Trade-Dangerous/commit/0f241f52763a7b3f475be47262cbb28412f2f198))

* chore: publish to pypi

Update how to publish to pypi
and some documentation about requirements. ([`5e55d0f`](https://github.com/eyeonus/Trade-Dangerous/commit/5e55d0f8209c35dbaaabdbe972269b620488cc37))

* chore: fix semantic-release ([`23420f8`](https://github.com/eyeonus/Trade-Dangerous/commit/23420f861914f1bf67a3310e53ef414d2bbe4805))

### Fix

* fix: bump version ([`34da73a`](https://github.com/eyeonus/Trade-Dangerous/commit/34da73a55ec4eb77d89ac45472a983d1757a19df))

* fix: Add module &#39;typing&#39; to the requirements. ([`f8b3f13`](https://github.com/eyeonus/Trade-Dangerous/commit/f8b3f1391ac699ed753706d5cd0a0fb2ced5a2c1))

* fix: Apparently can&#39;t test 3.7 because error 403.

Thanks upstream. ([`735234d`](https://github.com/eyeonus/Trade-Dangerous/commit/735234dd7fcc7ecd4bc5a3048f748bd8e9858a61))

### Refactor

* refactor: Don&#39;t publish until build works. ([`b5b2f88`](https://github.com/eyeonus/Trade-Dangerous/commit/b5b2f88e4048f05dc90caf9884806641de084718))

### Test

* test: travis with py3.7


test: travis use dist: xenial


chore: resync tag and version


docs: add info about deploy


chore: configure ci ([`a1626cd`](https://github.com/eyeonus/Trade-Dangerous/commit/a1626cdcadf73621500a9526448f58140ef73e60))

### Unknown

* 10.0.0

New version by CI ([`a94cd86`](https://github.com/eyeonus/Trade-Dangerous/commit/a94cd86610c6b48927c0a8d247f9d512d6c0b2a9))

* Merge branch &#39;master&#39; of https://github.com/kmpm/Trade-Dangerous.git

Conflicts:
	.travis.yml
	dev-requirements.txt ([`5ac899f`](https://github.com/eyeonus/Trade-Dangerous/commit/5ac899f8957af0f4f82e594e455a99f0595b94ba))

* Update .travis.yml ([`06c5adb`](https://github.com/eyeonus/Trade-Dangerous/commit/06c5adb47870d6df9c3ce4f5ab9d7de9126f7194))

* Update .travis.yml ([`48417c6`](https://github.com/eyeonus/Trade-Dangerous/commit/48417c66d89138e47e4dc8a2b9944c606965f58c))

* Trade-Dangerous as a module (#45)

* Created &#39;tradedangerous&#39; pgk and moved files there

* fix imports
* removed data and tmp folders
  data will be regenerated from traded/templates
  tmp will be recreated when needed
* added tox and pytest
* added travis config

* tests and sql

* More tests, fixes and documentation

- Enable TradeEnv to read environment variables, 
  TD_DATA, TD_TEMPLATES, TD_TMP
- docs using sphinx
- Test using tox and travis. Py34, Py35 and Py36
- Fixes some circular references that didn&#39;t work with Py3.4

* Fix issue with tdb kept open if error

* ensure target folder exists on download

Will fail silently otherwise

* test trade and import_eddblink

* chore: add sematic release

Add python-semantic-release to make life easier

* add semantic-release to travis

* chore: add deploy stage for master branch

Add a deploy stage that only run after
- ALL tests are ok
- On master branch
- only on one python version (3.6)

* refactor: Add py3.7 to version list, build lowest compat., init TD ver.

Lead developer is using 3.7, so obviously tests need to include that
version.

If we&#39;re only going to build for one python version, it should be the
lowest compatible version.

Last official version of TD was 7.4.0, back in 2016-01-29, so
considering how much has changed since then, should start at something
more like 10.

The .1 part of 10.0.1 is this specific refactor.

* refactor: Include py3.7 in tox script as well. ([`489f721`](https://github.com/eyeonus/Trade-Dangerous/commit/489f721a566e1f0d5cd8752625050f19e68a4eb4))


## v9.5.3 (2019-02-07)

### Refactor

* refactor: Add deprecation NOTE to progbar option.

Passing the progbar option now results in a NOTE: being printed
informing the user that the option has been deprecated and no longer
functions. ([`73ae3af`](https://github.com/eyeonus/Trade-Dangerous/commit/73ae3af8d9be226b7dd3d7a3ccb2e87dbe7f8809))

### Unknown

* Forgot to also remove the &#39;progress&#39; variable the &#39;(125/500) 25%&#39; used ([`afec7e6`](https://github.com/eyeonus/Trade-Dangerous/commit/afec7e604f1da76e5f3b6e228e8e2ccf6bc6cfd6))

* Remove the &#39;(125/500) 25%&#39; progress and make progbar the default option

Also remove the .gitignore in /data and add its entry to the top-level
.gitignore where it belongs. ([`977099b`](https://github.com/eyeonus/Trade-Dangerous/commit/977099b1005fe2e2aedef4b5bc8b92ec46193eb2))

* Make Avraham happy.

By doing it right. ([`4f628bf`](https://github.com/eyeonus/Trade-Dangerous/commit/4f628bff4e6676e294545f71ad98bac9713f521b))

* Revert sql change from last commit.

How did that happen? No idea. It only affects manually exporting the
.csv files, though, so no biggy. ([`7352b9f`](https://github.com/eyeonus/Trade-Dangerous/commit/7352b9fd5e45cb03a2fe780fd8ba60dcffb78f95))

* Update listings import to use faster method, various fixes.

Removed some old code that isn&#39;t needed anymore, added some code to make
the import a bit more stable and resistant to borking the database if
the program is exited early.

Changed the listings import method to use executemany instead of doing
each listings import as a separate transaction, resulting in a huge
speedup on the typical case and a pretty decent speed up in general. ([`48686db`](https://github.com/eyeonus/Trade-Dangerous/commit/48686db3ddfbf6e5dffc70087565c63d6d3a01c4))

* Fix #40 ([`c0fd39e`](https://github.com/eyeonus/Trade-Dangerous/commit/c0fd39e7f325950182fd9e9505277c36fa9e16da))

* gitignore update ([`beed86d`](https://github.com/eyeonus/Trade-Dangerous/commit/beed86d592363a727882001dddf2d5fe087fef89))

* Add &#34;--planetary&#34; option to olddata command. ([`e4edf47`](https://github.com/eyeonus/Trade-Dangerous/commit/e4edf4760fa908c117558981a6729d01c239a893))

* Olddata (#39)

* Added &#34;--no-planetary&#34; option to olddata command

* Added &#34;--ls-max&#34; option to olddata command ([`1aa7fc1`](https://github.com/eyeonus/Trade-Dangerous/commit/1aa7fc164449b8855094480a202fcb4147304e84))

* Only the &#34;profile&#34; part is used anyway....

We literally don&#39;t care about anything but what&#39;s in the &#34;profile&#34;
element, so there&#39;s no need to bother with anything else, which also
means no need to bother checking if anything else even exists. ([`c29c9d0`](https://github.com/eyeonus/Trade-Dangerous/commit/c29c9d0f8f107f3bc24d2df3793002c2e40d6891))

* Fix https://github.com/MarkAusten/TDHelper/issues/48 ([`dcf569b`](https://github.com/eyeonus/Trade-Dangerous/commit/dcf569be5afc04b3bb2cb2a0a3d87140fc60e6dd))

* Fix debug message.

Arg.

Still trying to figure out what&#39;s going on with
https://github.com/MarkAusten/TDHelper/issues/48 ([`f121b19`](https://github.com/eyeonus/Trade-Dangerous/commit/f121b19fb4ed7c0a90b1ee48dac16b4dd931700e))

* Add debug note to profile save.

Need it to track down https://github.com/MarkAusten/TDHelper/issues/48 ([`c4dd081`](https://github.com/eyeonus/Trade-Dangerous/commit/c4dd0815f696f4d8307ec12cad92e6e0614433ce))

* Minor edit to comment relevant to last commit. ([`dc82a20`](https://github.com/eyeonus/Trade-Dangerous/commit/dc82a204ea129ccc16d0f007ac5ebcd371d71325))

* Fix https://github.com/eyeonus/EDDBlink-listener/issues/17 ([`66e54b5`](https://github.com/eyeonus/Trade-Dangerous/commit/66e54b54b299549b80b778a319fa6407a3691ca7))

* Various Fixes.

Separate fdev_id and item_id as two unique fields, not unique in
combination. Fixes #35

Update EDDBlink to use the new v6 EDDB.io dumps. Fixes #37

Use EDCD as source for commodity list.

Add check to listings import that will see if the listing is using the
fdev_id as a temp item_id for an item that now has an actual item_id,
importing the listing using the actual item_id if so.

Delete the listings that no longer exist in the station we were just
checking from the station we were just checking, not the new station
we&#39;re about to check. ([`5d4c537`](https://github.com/eyeonus/Trade-Dangerous/commit/5d4c537860e93b63300a21ed22cf89bee37c7c4b))

* Fix #31.

Category.csv is deleted on a clean run, so it can&#39;t be used in that
case.

Added a default value of what the categories currently are to use when
the file doesn&#39;t exist.

It&#39;s not likely that the categories will ever change, but this is for in
case they do. ([`faa2ffd`](https://github.com/eyeonus/Trade-Dangerous/commit/faa2ffd5b1a5ac57b88046086240af7e8f9924e8))

* Generalize faulty EDDB.io entry check.

Any item that doesn&#39;t have an ed_id value is &#39;faulty&#39;, so skip importing
any of them.

As of right now, that&#39;s just #270 &#34;Occupied Cryo Pod&#39;, but thjat may
change in the future.

(&#34;OccupiedCryoPod&#34; is the symbol for &#34;Occupied Escape Pod&#34;.)

Also updated the manual corrections to include the escape pod. ([`2ee7b39`](https://github.com/eyeonus/Trade-Dangerous/commit/2ee7b3929745d0dec587f8dcddb6245923098ab3))

* More future proofing.

Updated EDDBlink plugin to use EDMC commodity list to check for items
missing in EDDB.io&#39;s commodities.json and automatically add any found
using the fdev_id as the item_id.

Since EDMC, unlike EDDB, is really quick at updating their list, this
means new items will be added to TD much more quickly, and allows the
listener to update the market data for those items sooner as well. ([`0887116`](https://github.com/eyeonus/Trade-Dangerous/commit/0887116f8d8b72a610fab830157171782689d426))

* Future-proofing, hopefully.

EDDBlink plugin updated to include newest items added in E:D,
temporarily using their fdev_id as their item_id.

EDDBlink plugin updated to detect when an item&#39;s item_id has changed
(such as when an item that was not in EDDB.io&#39;s commodity.json and was
using the fdev_id has been added to the json and therefore now has an
item_id (which definitely is not the fdev_id)) and update the database
to use the new item_id, using the item&#39;s fdev_id to check.

corrections.py updated to correctly mark the &#39;OCCUPIED CRYOPOD&#39; as
&#39;Occupied Escape Pod&#39; and not DELETED.

SQL script updated to make fdev_id in the Item table unique and and an
index using the fdev_id as key. (Does not take effect until a &#39;clean&#39;
run of the plugin is performed.) ([`a317b4a`](https://github.com/eyeonus/Trade-Dangerous/commit/a317b4ae32e9c78f001d9f5f6a2f221ab2c82ed9))

* Okay, the encoding problems should be fixed now. ([`88f57e1`](https://github.com/eyeonus/Trade-Dangerous/commit/88f57e1e8e820fb94e5cbecac43d598c9f1890ac))

* Arg. Encoding annoyance. ([`bc5c13b`](https://github.com/eyeonus/Trade-Dangerous/commit/bc5c13bbc92e672d04c536494e35d25ccc4ea316))

* Revert encoding screwup. ([`dc122c7`](https://github.com/eyeonus/Trade-Dangerous/commit/dc122c7c7ab1f99d08d976c4fe31751c45d2fafc))

* Update TD to use EDMC item names, not incorrect EDDB.io names. ([`e365caf`](https://github.com/eyeonus/Trade-Dangerous/commit/e365cafcb5ca3b8125e9c9e4096a2613bf711b8c))

* Add edapi token to gitignore, add field names to json output. ([`50ed5ae`](https://github.com/eyeonus/Trade-Dangerous/commit/50ed5ae0cca7f75c744cbc704d78b9a333752329))

* Incorporate bgol&#39;s updates to plugin to make it work with new cAPI.

Ought to work until FD changes the authentication method again. ([`c4bf271`](https://github.com/eyeonus/Trade-Dangerous/commit/c4bf271881553264b88d36b5c11bfd8817435951))

* Not implemented plugin finish() raises Warning, not Error, returns True

The finish() method should never be required to be implemented.

If the plugin needs to do something at the point where finish() is
called by the import command, then it&#39;s nice to have the option, but if
the plugin doesn&#39;t need to do anything there, it shouldn&#39;t be required
to implement the method anyway just to say &#34;Nope, I&#39;m good, get on with
it.&#34; and quit.

So, if the method is not implemented, instead of throwing an Exception,
it now throws a Warning, and returns True by default, True being the
&#34;Nope, I&#39;m good, get on with it.&#34; ([`74fdc48`](https://github.com/eyeonus/Trade-Dangerous/commit/74fdc487bfb9cd9de722c70193fbafeba0c43382))

* Apparently it is used. D&#39;oh. ([`e045371`](https://github.com/eyeonus/Trade-Dangerous/commit/e045371da72ae8c750afc238bf7a4706bafed5ca))

* Removed &#34;nolive&#34; as redundant.

&#34;fallback&#34; option has the same effect as nolive, making it useless. ([`38cfd98`](https://github.com/eyeonus/Trade-Dangerous/commit/38cfd980042dd045b0a20727b46b68ea178f64ab))

* Minor adjustment to &#34;nolive&#34; option description. ([`1415849`](https://github.com/eyeonus/Trade-Dangerous/commit/1415849d6a32eae88b11c4d1adcf3009cf31b768))

* Fix from_live to work correctly. ([`9639fdb`](https://github.com/eyeonus/Trade-Dangerous/commit/9639fdb777ae996e4ef2bbdcbc6ab9b9af254bdd))

* No &#34;nolive&#34; option for server use only. ([`a405682`](https://github.com/eyeonus/Trade-Dangerous/commit/a40568241065d8531abccb76f91ce96c0a717009))

* from_live still isn&#39;t working like it should. ([`3baef3d`](https://github.com/eyeonus/Trade-Dangerous/commit/3baef3dd6dda7d52d42708be04fcc3969f20db41))

* Revert last. ([`afc1a85`](https://github.com/eyeonus/Trade-Dangerous/commit/afc1a851482ddd748edaf52b3d1ebea77fa22544))

* from_live still isn&#39;t working right. ([`cf22aaf`](https://github.com/eyeonus/Trade-Dangerous/commit/cf22aafaa9595f83f2e3577757d36c5fa4a6b37d))

* Removed unused method from edmc plugin. ([`f96ca8c`](https://github.com/eyeonus/Trade-Dangerous/commit/f96ca8c5f01df695cd4898ab2ad5cac278625d47))

* Add edmc_batch plugin to import multiple .prices files (#29)

Plugin by Ryanel to import .prices files made by EDMC easier, by processing them all in one go. ([`c8be33d`](https://github.com/eyeonus/Trade-Dangerous/commit/c8be33d6254e72d2eb475c370081eed7ab29340d))

* Fix #27

Gain/Hop was a floating point number, so when it gets too large to fit
in the 10 spaces allowed to it, it converts itself to scientific
notation.

Making it be an integer fixes that problem. ([`f6e88f0`](https://github.com/eyeonus/Trade-Dangerous/commit/f6e88f044c10d12781850a0fe0be164c36993ce5))

* Remove unused import (auto-added during testing). ([`43150e6`](https://github.com/eyeonus/Trade-Dangerous/commit/43150e61aef417c68c8a6add8ac1415999c17bdd))

* Remove old tdh_profile before writing new, quit after save if TDH.

If the plugin was called specifically to provide TDH with the EDAPI
response (i.e., by using the &#34;tdh&#34; option), nothing needs to done once
the file has been saved, so exit immediately.

Also, because the plugin will be saving to the same filename every time,
delete the old file before saving a new one to prevent any weirdness
occurring. ([`2e92358`](https://github.com/eyeonus/Trade-Dangerous/commit/2e9235807e0b4d5c5dda0a89f9a0a4850d04b6aa))

* Add &#34;tdh&#34; option to edapi plugin for TDHelper to use.

Trade Dangerous Helper uses the EDAPI response to get information about
the CMDR, such as amount of credits, owned ships, etc.

Right now, it&#39;s using the edce client to get that response, but it can
just as easily use the EDAPI plugin included with TD.

The EDAPI plugin has a save option which outputs the EDAPI response to
&#34;&lt;TD Install&gt;/tmp/profile.&lt;current_date&gt;_&lt;current_time&gt;.json&#34;, eg.
&#34;profile.20181028_091544.json&#34;.

This has a couple drawbacks, one being that every time the plugin is run
with the save option, it creates a new file, which just means more
things for the client to take care of, and TDH would need to figure out
what the file is named everytime.

To circumvent both, a new option has been added to the plugin that will
cause the plugin to always save to &#34;&lt;TD Install&gt;/tmp/tdh_profile.json&#34;.

The original &#34;save&#34; option is unaffected.

The command to generate the TDH file is:
&#34;trade.py import -P edapi -O tdh&#34; ([`fbd5912`](https://github.com/eyeonus/Trade-Dangerous/commit/fbd5912851c3af340504f9170cc63778e2e7062d))

* Small formatting change for ease of readability (hopefully). ([`69eed0f`](https://github.com/eyeonus/Trade-Dangerous/commit/69eed0fe1332da822ab9f91c60c707d35e1a0346))

* Fix #20 ([`c203f8e`](https://github.com/eyeonus/Trade-Dangerous/commit/c203f8e81b46ff962d64fd52a7a70db74eb18632))

* Merge branch &#39;dev&#39; of https://github.com/eyeonus/Trade-Dangerous.git ([`8a43404`](https://github.com/eyeonus/Trade-Dangerous/commit/8a43404f04582823e81877adfeb55185c02a58e0))

* Fix some syntax errors. ([`2b617e8`](https://github.com/eyeonus/Trade-Dangerous/commit/2b617e8884180b361dd787774a7cf25a4ca4525a))

* Change env to python3 instead of python3.6

This change allows users with later versions of python3 to run the
program without having to make sure they have specifically python3.6
installed. ([`3c0ab29`](https://github.com/eyeonus/Trade-Dangerous/commit/3c0ab291e9babaeb01981e75ec946bcd940c7563))

* Change env to python3 instead of python3.6

This change allows users with later versions of python3 to run the
program without having to make sure they have specifically python3.6
installed. ([`2c897f8`](https://github.com/eyeonus/Trade-Dangerous/commit/2c897f87c142ea56a23f361e1e7ce045cb83e2b7))

* Untested attempt to address #25 ([`635ca06`](https://github.com/eyeonus/Trade-Dangerous/commit/635ca0634c5a026c0dcea6d0498a2ee05b91cde2))

* Fix #23 ([`de9ca7a`](https://github.com/eyeonus/Trade-Dangerous/commit/de9ca7a945e0c64b8685b21d51316a4c4eb5b2ac))

* Ignore unknown ships/upgrades when updating shipvendor/upgradevendor

#22 ([`80cdae9`](https://github.com/eyeonus/Trade-Dangerous/commit/80cdae94fef7a3af35acf1e66f225db9856c7b45))

* Revert &#34;Wreckage Components&#34; name change to &#34;Salvageable Wreckage&#34;.

EDDB.io is the odd man out, here. We&#39;re going to go with the majority,
so from this point forward we&#39;re keeping it as &#34;Wreckage Components&#34;. ([`ab896a7`](https://github.com/eyeonus/Trade-Dangerous/commit/ab896a75ccee40e15e36078f4ef8f6f80fcbdbf6))

* Added Ancient Key to manually added items, fixed ID#s of manual items.

Turns out EDDB.io does include these items on the site, they have their
own ID# and all the rest, but they&#39;ve never been added to the *API*.

Updated all the ID#s of the manually added items to have the same ID#
they have on EDDB.io, and added Ancient Key, making a total of four
(currently) Salvage Commodities that are not included in the API.
Argggg.... ([`6ac7cbd`](https://github.com/eyeonus/Trade-Dangerous/commit/6ac7cbd7e0249ed76267537f086365b276a5fb27))

* Update manually added items avg_price to null.

The listener has been updated to set the avg_price of commodities from
the EDDN, so there&#39;s no need to set it within the import, and since that
value is constantly changing anyway, it&#39;s kind of pointless to do so as
well. ([`d12643a`](https://github.com/eyeonus/Trade-Dangerous/commit/d12643a4d027a3f18f175c01716950a2898f1aed))

* Delete temp entries if EDDB does ever add them. ([`67094aa`](https://github.com/eyeonus/Trade-Dangerous/commit/67094aaae2c6e65d50aef04c591d71825e5f290a))

* Correctly test to see if item is already in the list. ([`b1655ea`](https://github.com/eyeonus/Trade-Dangerous/commit/b1655eafbccaa81d1223cc940dcf2ec2c46911dc))

* Try again, this time in a way that works. ([`e816682`](https://github.com/eyeonus/Trade-Dangerous/commit/e8166822d7369b977f5344bfeefd7d2990a51b4f))

* Manually add Salvage commodities missing from EDDB dump.

EBBD still hasn&#39;t gotten around to adding the Salvage items &#34;Antique
Jewellery&#34;, &#34;Gene Bank&#34;, and &#34;Time Capsule&#34;. At this point I don&#39;t think
they ever will, so we&#39;ll just add them manually. ([`3be8047`](https://github.com/eyeonus/Trade-Dangerous/commit/3be8047617e6a97b9ce9e497b11992c8ce050378))

* TD Crest as Windows Icon

Just for fun, the TD crest in Windows Icon form to make your shortcuts look cool. ([`bf68513`](https://github.com/eyeonus/Trade-Dangerous/commit/bf68513d167e2d5ae8d985604622f81805bc3e2c))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous ([`b22ba96`](https://github.com/eyeonus/Trade-Dangerous/commit/b22ba9618b4552ebd9058abb0a11358efd72e781))

* Reverting this change - it&#39;s a little TOO fragile.

Even a ctrl-c trashes the database and requires a -O clean. That might be just going too far :) ([`a9b0150`](https://github.com/eyeonus/Trade-Dangerous/commit/a9b0150877c38c43ef9d84b35386482d7d391d5e))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous.git ([`995a70a`](https://github.com/eyeonus/Trade-Dangerous/commit/995a70aea71c672b04e1129c12f97bf4fd02cc50))

* Fix #19 ([`51640c6`](https://github.com/eyeonus/Trade-Dangerous/commit/51640c60a466cc9abbedfe0a3b33a4e5a3dc3f3a))

* Cure another potential disk thrasher ([`6dcb086`](https://github.com/eyeonus/Trade-Dangerous/commit/6dcb08657bca0eda69a9cb32bcc19d821f19f78c))

* Make comment reflect &#39;progbar&#39; addition. ([`b5db1c6`](https://github.com/eyeonus/Trade-Dangerous/commit/b5db1c6df580698cb7fc96705a9dee004bf4b1d9))

* Add progbar to the does-not-override-default list of options. ([`9396380`](https://github.com/eyeonus/Trade-Dangerous/commit/939638062ce62e194d0cbd19938c0780d64580b0))

* Exclude Ship and Upgrade Vendor information in &#39;solo&#39; mode as well. ([`645903e`](https://github.com/eyeonus/Trade-Dangerous/commit/645903e363e9e567f347131756ff28be97c9d9a1))

* Add option for solo players to never get crowd-sourced market data. ([`0401aa0`](https://github.com/eyeonus/Trade-Dangerous/commit/0401aa0078bfc59eb8f836678fb0931c3888d0d7))

* Thanks to Bernd for pointing out an embarrassing typo.... ([`7bb9bfc`](https://github.com/eyeonus/Trade-Dangerous/commit/7bb9bfc143d2aedcaca59493e72fa73239b4ffe4))

* Make the ship name comment clearer as to intention of relevant code. ([`9f33d5d`](https://github.com/eyeonus/Trade-Dangerous/commit/9f33d5d910814aad454552d5848cff8dae80ccb3))

* Handle all variations of &#34;Mark&#34; in ship names and fix to be &#34; Mk. &#34;. ([`c613d54`](https://github.com/eyeonus/Trade-Dangerous/commit/c613d5473e2ca26b3763549ebdd075ba4c0c9582))

* Also handle cases with no leading space for ship names with a &#34;Mark&#34;. ([`7ec0d1a`](https://github.com/eyeonus/Trade-Dangerous/commit/7ec0d1a6a52243d408579f5ab4ab8f4a37ecb39b))

* Revert 36389d5, fix name properly. ([`cfe0ee2`](https://github.com/eyeonus/Trade-Dangerous/commit/cfe0ee2ea8bfff782fe9c741a22baf232217d095))

* Fix import of Krait Mk II

So, there is disagreement.

Coriolis has Krait Mk II
EDDB has Krait MkII

Unlike other similar ships it&#39;s not Mk.  (see the &#39;.&#39;) either, so completely different to other cases.

(In game it appears to actually be Krait MkII, so EDDB looks to be correct and maybe we blame FDEV for being inconsistent as the root of the problem)

So we have this fix until/unless things change. ([`36389d5`](https://github.com/eyeonus/Trade-Dangerous/commit/36389d56eaf01004d3eeb5a12329edcc5b61ccba))

* Make sure PRAGMA is set up every time.

synchronous and temp_store aren&#39;t persistent, so we need to do this every time we connect to the DB. ([`7b149ca`](https://github.com/eyeonus/Trade-Dangerous/commit/7b149cae20d0ce05278848580a768a5bae6a5b66))

* Database tunings

The data is easily replaced from master source, so do stuff in memory for additional speed and risk the power cut. ([`3174deb`](https://github.com/eyeonus/Trade-Dangerous/commit/3174deb49e5e152a7aeff5076a74e927b3e2b363))

* Fix #18 ([`8b4048e`](https://github.com/eyeonus/Trade-Dangerous/commit/8b4048e8eb401badfb45ca7463789fda97525600))

* Remove temporary code, problems fixed upstream. ([`aac50c3`](https://github.com/eyeonus/Trade-Dangerous/commit/aac50c32b33e772d78b88ec90c89c6f35219af61))

* Fix https://github.com/eyeonus/EDDBlink/issues/9 ([`97a3ef9`](https://github.com/eyeonus/Trade-Dangerous/commit/97a3ef99b64319d5412c71efe170f70ac974e7be))

* Add padSize to command line arguments and implement.

Fixes #9 ([`12b925b`](https://github.com/eyeonus/Trade-Dangerous/commit/12b925b2ca3edd006ef409584343b5694c520b17))

* Switch to MPL2 ([`49ce01a`](https://github.com/eyeonus/Trade-Dangerous/commit/49ce01aa12345b1e249e74933003c350b3f67436))

* Remove GPL ([`33973dc`](https://github.com/eyeonus/Trade-Dangerous/commit/33973dcb8eeecd75961db411549678c3cbce9c90))

* Give eyeonus his lower case &#39;e&#39; ([`4ce0642`](https://github.com/eyeonus/Trade-Dangerous/commit/4ce0642305a303d84b6e9e3388e013183705c2d6))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous.git ([`ae8793c`](https://github.com/eyeonus/Trade-Dangerous/commit/ae8793c2fc75e535fd7e4743d44f3ebc32c9f9cf))

* Temp. fix to new ships not in EDDB yet.

When EDDB adds the new ships, we&#39;ll have to change the code to reflect
that. ([`7a6e25f`](https://github.com/eyeonus/Trade-Dangerous/commit/7a6e25f91f29be60aa23949ee465a727cf6c75b4))

* Add newest rares &amp; corrections per BGOL release. ([`1e077b9`](https://github.com/eyeonus/Trade-Dangerous/commit/1e077b98df765998c29efc7da1f7b2fbf0c128a5))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous.git ([`af12a33`](https://github.com/eyeonus/Trade-Dangerous/commit/af12a3399ba52d56c1a87930f8e242c550172cff))

* Only catch DB locked exception. ([`f5ef573`](https://github.com/eyeonus/Trade-Dangerous/commit/f5ef573c5d3204ac19681d0d11d38abcff41b5e4))

* eyeonus prefers a small &#39;e&#39; ([`7e6c11f`](https://github.com/eyeonus/Trade-Dangerous/commit/7e6c11f10e2874969cee5cddb25794aee29e2267))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous ([`86fa3eb`](https://github.com/eyeonus/Trade-Dangerous/commit/86fa3eb173d2b9e308f77ac36c8addd413c51f51))

* Updated copyright &amp; shebangs in main code. ([`14068ab`](https://github.com/eyeonus/Trade-Dangerous/commit/14068aba7a75b34103cd39af1785e0f81392e497))

* Changed to GPL 3.0

Oliver&#39;s original copyright allowed anything
# You are free to use, redistribute, or even print and eat a copy of
# this software so long as you include this copyright notice.
# I guarantee there is at least one bug neither of us knew about.

So long as this is maintained, adding a more restrictive license should be no problem.
Note that EDDBLink standalone is separately released under LGPL 3.0 ([`1d3b120`](https://github.com/eyeonus/Trade-Dangerous/commit/1d3b1200c02f3290c6d6152ab76ae185c5c629f5))

* Fix typo. ([`5aad063`](https://github.com/eyeonus/Trade-Dangerous/commit/5aad06314c68dbc003eb2f874180ce310f6ebe4a))

* Fix typo. ([`874b71e`](https://github.com/eyeonus/Trade-Dangerous/commit/874b71e70cf50e51838ee6d3f324f0ef6e3c60a0))

* 2-space line breaks... again ([`4debbb7`](https://github.com/eyeonus/Trade-Dangerous/commit/4debbb762f792be864a1e94306e30662d8d386b4))

* 2 space line breaks... ([`1aa41f5`](https://github.com/eyeonus/Trade-Dangerous/commit/1aa41f5d240d1986d19631523d3d23fa3cec13aa))

* Drastically shorten readme.

Remove the long documentation from the readme - migrated into wiki.  Update copyright. Add wiki links.
Oh and put the picture in, pictures are cool. ([`1414a0d`](https://github.com/eyeonus/Trade-Dangerous/commit/1414a0d83f7ca319d5a4c65407b0d2d10e34e366))

* Update main copyright ([`6824f4e`](https://github.com/eyeonus/Trade-Dangerous/commit/6824f4e9ee5c11227d751be5093730a3b78f7eb4))

* Update lsp default to 12.5

Fix #11 ([`7e382ae`](https://github.com/eyeonus/Trade-Dangerous/commit/7e382aecc3b5b5ece44126ee156b79f81365218c))

* Always update from_live to 0.

Need to come up with a better way to make plugin not update from_live to
0 when updating a listener server using a &#39;listings_live.csv&#39;.

This method causes more problems than it solves. ([`3556ebc`](https://github.com/eyeonus/Trade-Dangerous/commit/3556ebc92485de7bf4c09062247a9ab08fc7e5c8))

* Updated shebang for server ([`bc8b8a6`](https://github.com/eyeonus/Trade-Dangerous/commit/bc8b8a67cfc1037559e57e3bb704691ed001feca))

* Keep penalty within [0,1] (#13)

* Update tradecalc.py

Cap distance penalty proportion at 1 to prevent weirdness if passing numbers greater than 100. Anyway, it is defined as a percentage so should be strictly in [0, 1].

* Keep value &gt;=0 too, while we&#39;re at it. ([`1cb0b4d`](https://github.com/eyeonus/Trade-Dangerous/commit/1cb0b4df30c3724d7216a9f5dc61cb47db9ec324))

* Move from_live assignment outside of if statement. Fix #12 ([`71405b2`](https://github.com/eyeonus/Trade-Dangerous/commit/71405b2c48a79b62e711876ebe05c19402df9a23))

* Print headers if TD detects no content-length header on non-chunked. #10 ([`5fe7e8a`](https://github.com/eyeonus/Trade-Dangerous/commit/5fe7e8a20599a1d2defed7d3d294187d6fdb82c0))

* Update progress bar to include percentage. ([`aba4715`](https://github.com/eyeonus/Trade-Dangerous/commit/aba4715f76e3c0be6f7b2492126c09bebf6ef6b7))

* Update from_live based on which listings file the data is coming from. ([`62269f8`](https://github.com/eyeonus/Trade-Dangerous/commit/62269f8a33b27dc1a9906b0c3461be616824cc0c))

* Reduce number of requests to server. ([`f291a56`](https://github.com/eyeonus/Trade-Dangerous/commit/f291a569cffa2661e85c2a1301d37bc674690a74))

* Make the actual default ls penalty match documentation. ([`224b8f3`](https://github.com/eyeonus/Trade-Dangerous/commit/224b8f35c2bb1c25ef91dfb807dfa4f71855a879))

* Too many 0&#39;s. ([`4696f07`](https://github.com/eyeonus/Trade-Dangerous/commit/4696f07ca8b6c908cdcfba813f86df26beeb8a05))

* Apparently the default penalty was 0, not 0.5

Revert last and change the default to what it &#34;should&#34; be. May decide to
change the boost back, but I want to see my results with the default
first. ([`862736d`](https://github.com/eyeonus/Trade-Dangerous/commit/862736dbbd3217494045e96227c488f4f4789818))

* Reduced maximum boost to +0.1.

+0.5 is obviously way too high. I keep getting stations in my route that
are &gt;50Kls, all because of one hop that&#39;s &lt;20ls. ([`4da78e8`](https://github.com/eyeonus/Trade-Dangerous/commit/4da78e85eb3afdcd6272c97d691bfd5cf1dbfefb))

* Constrain progress bar to standard terminal width. ([`9b2ef08`](https://github.com/eyeonus/Trade-Dangerous/commit/9b2ef08f300d511490c3e2aa9cbb6c8e1475fad7))

* Pass on error if it&#39;s not due to locked DB. ([`c3dfab9`](https://github.com/eyeonus/Trade-Dangerous/commit/c3dfab9384d2642901a27fe021ac9a48c752c217))

* Let&#39;s do that is a slightly better way, instead. ([`3debd2d`](https://github.com/eyeonus/Trade-Dangerous/commit/3debd2dde8cd7d5dfb69393f15794136c4da8f0c))

* Fix plugin getting stuck trying to re-add column. ([`eff6cd8`](https://github.com/eyeonus/Trade-Dangerous/commit/eff6cd800d9739d565b5b6cd82d76e85bd10fbc7))

* Don&#39;t regenerate .prices file unless listings have updated. ([`a2ab13c`](https://github.com/eyeonus/Trade-Dangerous/commit/a2ab13c0df669e20f599fdfd59c1e82edaee7e88))

* Give type_id default value of 0 when no value in source. ([`94f5489`](https://github.com/eyeonus/Trade-Dangerous/commit/94f5489680874f9349adb5bc928b358b48eeaa33))

* Remove depugging print statement. ([`41021b9`](https://github.com/eyeonus/Trade-Dangerous/commit/41021b90991c2692488e585c1a2739a467bb4aa3))

* Fix running with default options. ([`21f8e44`](https://github.com/eyeonus/Trade-Dangerous/commit/21f8e44772ed0f8e591986db4768a9e8ba339d57))

* Update to include type_id in Station table.

Adding this column allows us to track the mobile stations and update the
system they are in when they move. ([`2f9fd35`](https://github.com/eyeonus/Trade-Dangerous/commit/2f9fd35e519f78ffd2950a478678260ebba662e2))

* Added &#39;progbar&#39; option.

Passing &#39;progbar&#39; to the EDDBlink plugin will cause it to display
progress as a bar, as in:
`[=====               ]`
rather than the default format:
`Progress: (125/500) 25%` ([`31a58f3`](https://github.com/eyeonus/Trade-Dangerous/commit/31a58f33eef02fdf47105dc833fa36b8e443ea1d))

* Bring eye-TD plugin version and solo plugin versions in line. ([`1a991ee`](https://github.com/eyeonus/Trade-Dangerous/commit/1a991ee0b3c80cf19a5b739ba069edfdd824fa14))

* Fix requests installation.

&#39;pip.main([&#34;install&#34;, &#34;--upgrade&#34;, &#34;requests&#34;])&#39; raises the error:
&#34;AttributeError: &#39;module&#39; object has no attribute &#39;main&#39;&#34;, so update the
call to use the officially supported method. ([`2611f0a`](https://github.com/eyeonus/Trade-Dangerous/commit/2611f0ad4a74cd8a867a5040a2f4a8c6638d5c6d))

* Fix import. ([`d777cf8`](https://github.com/eyeonus/Trade-Dangerous/commit/d777cf853898ed2f2cf34193650e36bd21b99330))

* Remove recursionLimitedFit. Finalized switching over to using simpleFit. ([`19c854e`](https://github.com/eyeonus/Trade-Dangerous/commit/19c854ec3c111b1ad94a3a3d406b519cda624c80))

* Missed a cr. ([`dcf171b`](https://github.com/eyeonus/Trade-Dangerous/commit/dcf171b5520c17b3d457491f348cc5f1d84648ff))

* Added recursionLimitedFit and simpleFit fit functions.

recursionLimitedFit is precisely the same as fastFit, bnut with a
recursion limiter.

simpleFit is as described on the forum thread.

The line that sets which fitFunction to use:
&#34;self.defaultFit = fit or self.fastFit&#34;

has been commented out and duplicated with the two new functions to make
it a bit easier to switch between them during testing.

Will probably add a command-line switch at some point. ([`09cd464`](https://github.com/eyeonus/Trade-Dangerous/commit/09cd4648c7bd28883ea5655b823e9ec54acc5468))

* Oops. ([`63102b8`](https://github.com/eyeonus/Trade-Dangerous/commit/63102b8af0214a30c2130e1e8ccfe802d1afc634))

* Fix incorrect variable being passed. ([`1f0ce2b`](https://github.com/eyeonus/Trade-Dangerous/commit/1f0ce2b8c7c6804a24a87bacacba8296925f5f3e))

* Use limit-&gt;∞ of formula (= -0.5) when formula overflows. ([`6a7704d`](https://github.com/eyeonus/Trade-Dangerous/commit/6a7704d532712a22bbacf08a09a714fdd600e721))

* Update tradecalc.py (#7)

Python uses ** for exponentiation, not the caret (^). Otherwise we get &#34;TypeError: unsupported operand type(s) for ^: &#39;float&#39; and &#39;float&#39;&#34;. Also, am I scary enough to need scare quotes? That&#39;s not a handle, that&#39;s my name :) ([`1f001df`](https://github.com/eyeonus/Trade-Dangerous/commit/1f001dfb2b644e4e3c2d1f5492b35886d3dc5f25))

* Merge branch &#39;master&#39; of https://github.com/eyeonus/Trade-Dangerous.git ([`2475607`](https://github.com/eyeonus/Trade-Dangerous/commit/2475607bfffeda2e37bdc0dba86f0be4de6ff1fe))

* Update penalty calculation to formula that doesn&#39;t drop into negatives.

Fixes bgol/#14, bgol/#15 ([`35a9067`](https://github.com/eyeonus/Trade-Dangerous/commit/35a9067efa1e8f7ccbbbaae655eba7a287d65b18))

* Merge pull request #3 from aadler/patch-1

Update exceptions.py - Convert mentions of maddavo&#39;s plugin and Oliver&#39;s original wiki to EDDBlink and the current Wiki. ([`9bba6d2`](https://github.com/eyeonus/Trade-Dangerous/commit/9bba6d2eb4782bba2f05673847916b59d01540e5))

* Update exceptions.py

Convert mentions of maddavo&#39;s plugin and Oliver&#39;s original wiki to EDDBlink and the current Wiki. ([`e065327`](https://github.com/eyeonus/Trade-Dangerous/commit/e06532708f82c33905e64f907b8a15ef19fb3778))

* Merge pull request #2 from aadler/patch-4

Update README.md ([`cffd34d`](https://github.com/eyeonus/Trade-Dangerous/commit/cffd34df4259dbb10a4233ac6b9f0b1a482afa2b))

* Update README.md

Remove references to now-defunct Maddavo and replace with EDDBlink ([`bc8b7e1`](https://github.com/eyeonus/Trade-Dangerous/commit/bc8b7e1aaf46967e074cf43948e5fd136afb3713))

* First pass on broken Markdown

Lots of apparently broken markdown in this document, original author appears to have intended headers, but did them wrong.  Will need a lot more going over to standardize the whole layout, but this is better.
Also fixed eddblink options - the name of my pain is Atom. When I press TAB I want a TAB not fscking 3 spaces. Back to notepad++ my old faithful friend. ([`db573f8`](https://github.com/eyeonus/Trade-Dangerous/commit/db573f80c9e870a7538d3bedb48cbb0c701db92c))

* Fix (hopefully) EDDBlink options ([`6b15705`](https://github.com/eyeonus/Trade-Dangerous/commit/6b1570526a60ad315c90acfa0bb5620cd66a6e5a))

* Remove/Replace references to Maddavo plugin ([`00d7807`](https://github.com/eyeonus/Trade-Dangerous/commit/00d780716904caf162504ef90d2118903cdd546a))

* Create LICENSE ([`a99f942`](https://github.com/eyeonus/Trade-Dangerous/commit/a99f9421ffa64c359211883e53dd5aa9c8a39146))

* Don&#39;t need to print default.

Forgot to remove that line when I finished testing. ([`debd14f`](https://github.com/eyeonus/Trade-Dangerous/commit/debd14f43d57a03b50539395a0b0b2e3e47f74fb))

* Run with &#39;listings&#39; enabled by default.

If no options have been passed, enable listings as a default.

The options &#39;force&#39; and &#39;fallback&#39; are excluded from this, as they don&#39;t
say what to import so much as how.

The option &#39;skipvend&#39; is excluded because it says what /not/ to import.

If no options other than these are passed, listings will be enabled. If
any of the others are passed, the plugin will proceed as normal. ([`a16e363`](https://github.com/eyeonus/Trade-Dangerous/commit/a16e3631a06eb0d4bd104cb5f9da2dfc4e0f328c))

* Integrate EDDBlink changes into TD, remove change code from plugin.

The changes previously made by the EDDBlink plugin to the database and
csvexport.py have been merged into those files, so the plugin no longer
needs to check for those changes or make them if they haven&#39;t happened.

As such, that code has been removed from the plugin.

EDDBlink plugin previously checked if it was the first run by looking
for one of those changes. It now checks to see if the
TradeDangerous.prices file exists. The plugin WILL run a &#39;clean&#39; import
if it sees that the prices file has not been created, fair warning.

Since most of the data will now be updated automatically by the plugin,
those .csv files have been added to gitignore and removed from the repo. ([`9f6f022`](https://github.com/eyeonus/Trade-Dangerous/commit/9f6f022173eefafd4b30499c7764a605db200f32))

* merger ([`660c6da`](https://github.com/eyeonus/Trade-Dangerous/commit/660c6da08e1fc59e704b0cba16e8e67db984381f))

* EDAPI update ([`501208b`](https://github.com/eyeonus/Trade-Dangerous/commit/501208bdeccd9ec01a56dec4cc49af0e59cfc069))

* changelog ([`f6ea4be`](https://github.com/eyeonus/Trade-Dangerous/commit/f6ea4beacbebd9fab50f1384f64c381cc77e2ff2))

* beyond data maintenance ([`05438ca`](https://github.com/eyeonus/Trade-Dangerous/commit/05438ca740f33bdf81ad0378287cd067c0c37729))

* data maintenance ([`bb45911`](https://github.com/eyeonus/Trade-Dangerous/commit/bb45911ddc03fae9a11fc9954778355c81c31fd1))

* changelog ([`baf4e57`](https://github.com/eyeonus/Trade-Dangerous/commit/baf4e574621658f88986ce50d225064ca73326cf))

* bump version ([`6793e3a`](https://github.com/eyeonus/Trade-Dangerous/commit/6793e3a984eae98c70c863f595b09d810971b79f))

* Reworked &#34;/market&#34; and &#34;/shipyard&#34; check from cAPI. ([`f8fb580`](https://github.com/eyeonus/Trade-Dangerous/commit/f8fb580fe1ea430c8d1a0b335d6757fc794b833d))

* Don&#39;t stop if something is wrong with a line, just skip it. ([`ae44352`](https://github.com/eyeonus/Trade-Dangerous/commit/ae443521ef4c6030f1952a453ad7f8b6c815f487))

* 2.4 price update ([`4b46b71`](https://github.com/eyeonus/Trade-Dangerous/commit/4b46b71736356a41e94dfb27c80441aac158242f))

* some text and sorting updates ([`055f525`](https://github.com/eyeonus/Trade-Dangerous/commit/055f5258c783a4c68018b7bf518dddc75d7788fa))

* &#39;Salvageable Wreckage&#39; is the name of the place where you can find &#39;Wreckage Components&#39; ([`a08d6a5`](https://github.com/eyeonus/Trade-Dangerous/commit/a08d6a505ffc88e9b09e963c671d887971d455d5))

* one new salvage and renumbering ([`cfc8ec8`](https://github.com/eyeonus/Trade-Dangerous/commit/cfc8ec8c16f87bbee009a177e20f946965d8c42e))

* The &#34;Crystal&#34; is just missing in the list not on the upper right detail view. ([`52a2569`](https://github.com/eyeonus/Trade-Dangerous/commit/52a25697519d3ff78fda76b1b0edb3309a6e4f66))

* that&#39;s the escape pod. ([`1142ba4`](https://github.com/eyeonus/Trade-Dangerous/commit/1142ba4d284d916d7bef90be44886e39e18ea883))

* more FDEV-IDs ([`2f33079`](https://github.com/eyeonus/Trade-Dangerous/commit/2f33079e99d93bcb6384c075ee24b5d79d203c6b))

* That&#39;s a rare item. ([`78b6307`](https://github.com/eyeonus/Trade-Dangerous/commit/78b63073e7de2808ec9696cd0d19eb11938257fe))

* There is only one type of &#34;Cooling Hoses&#34;. ([`00ea6b5`](https://github.com/eyeonus/Trade-Dangerous/commit/00ea6b541eae558fb017cced86679233a9d44e24))

* Include the MultipleItemEntriesError() in the ignore switch.
This is needed for the Item cleanup. ([`dea2aa8`](https://github.com/eyeonus/Trade-Dangerous/commit/dea2aa8ff454d04a5a4d5d27c5de1a60f41bbb99))

* maddavo data update ([`f23354d`](https://github.com/eyeonus/Trade-Dangerous/commit/f23354d63aa0b93bfd40120b18bb3924558cd24c))

* pay more attention to the stock and demand brackets. ([`5b8e632`](https://github.com/eyeonus/Trade-Dangerous/commit/5b8e632c73e8a60e96ad0b40252ebc1b7f094fb9))

* use &#34;StationServices&#34; if available (comes with ED 2.4 update) ([`0a38c0f`](https://github.com/eyeonus/Trade-Dangerous/commit/0a38c0fcfc87e2c1fa88bbc3f06928e111c3c0c7))

* Updated item handling for upcoming ED 2.4 cAPI changes. ([`262bc72`](https://github.com/eyeonus/Trade-Dangerous/commit/262bc72396350e917e6a0ecaf04ba46aeddc0802))

* first save then abort ([`1f69fd1`](https://github.com/eyeonus/Trade-Dangerous/commit/1f69fd1fa43b927017451b67b02cf332f71e5fbd))

* Get station data from the new services entry if available. ([`f42273f`](https://github.com/eyeonus/Trade-Dangerous/commit/f42273f245299cd112a0127fbf3ee25f1798983f))

* removed unneeded code ([`08da7fd`](https://github.com/eyeonus/Trade-Dangerous/commit/08da7fd47031e134f7155bf38b91b874eb42190c))

* Added &#34;/market&#34; and &#34;/shipyard&#34; check from cAPI which is comming with ED
update 2.4. ([`e537531`](https://github.com/eyeonus/Trade-Dangerous/commit/e5375316e3f43e61d93febad72050bcd4b71c889))

* The average column was removed from EDCD/FDevIDs/commodity.csv ([`c8df3a7`](https://github.com/eyeonus/Trade-Dangerous/commit/c8df3a74ceec51637a46c17914a060b770630b97))

* changed most event parsing to if-elif ([`eec383f`](https://github.com/eyeonus/Trade-Dangerous/commit/eec383f9c3082db6ecc3126a8a5709a342b3b032))

* Aehem, don&#39;t ignore the leaving :) ([`3745011`](https://github.com/eyeonus/Trade-Dangerous/commit/37450113bb67654f4d4a9345c782bf00cd07fa7b))

* EDDN Server Migration ([`4c82de7`](https://github.com/eyeonus/Trade-Dangerous/commit/4c82de7b8e2ac13a14186783573ae17f71e0e607))

* Merged in bgol/tradedangerous/horizon (pull request #143)

Horizon

Approved-by: Michael Wilcox &lt;michael.wilcox2016@gmail.com&gt; ([`c9bc653`](https://github.com/eyeonus/Trade-Dangerous/commit/c9bc653382e4d72ffcd00ceacb1ef0415ea85fb3))

* into horizon ([`bce8483`](https://github.com/eyeonus/Trade-Dangerous/commit/bce8483127eea9d3e4d02efa52d40c2f32cbadf9))

* Some new salvage items and updated average prices. ([`f80fd87`](https://github.com/eyeonus/Trade-Dangerous/commit/f80fd870f4da068d1ba2b470c479d8a332a8cbfb))

* double entry in wrong category ([`ab57255`](https://github.com/eyeonus/Trade-Dangerous/commit/ab57255a3b8c0327ea55056a4829050a2ebe0ddf))

* there could be a OutpostCommercial ([`09f0bb3`](https://github.com/eyeonus/Trade-Dangerous/commit/09f0bb33bb1ef1901a1ccdae7fa9221cf2c57e3c))

* no station if undocked ([`8e8302f`](https://github.com/eyeonus/Trade-Dangerous/commit/8e8302f521315d3b55c01bfa40fafabd351f52f5))

* use keyword for the len parameter ([`874c900`](https://github.com/eyeonus/Trade-Dangerous/commit/874c90022993420e2a816a24f3a9d04f07f3688d))

* output category name of item in detailed view ([`ca86a62`](https://github.com/eyeonus/Trade-Dangerous/commit/ca86a6273d41fb1558449e030bd7c4caabf90d13))

* now it&#39;s the newest ([`47fda0e`](https://github.com/eyeonus/Trade-Dangerous/commit/47fda0e25411b986fa36e7e83c4885df858834f2))

* ignore all events while in multicrew ([`f1583d0`](https://github.com/eyeonus/Trade-Dangerous/commit/f1583d0d4ecf44f0885ecded8a4f56bb09c63013))

* ups, we need an boolean. ([`3b6e7ce`](https://github.com/eyeonus/Trade-Dangerous/commit/3b6e7ce4d358b2a4e438363e0c7503d7065ab305))

* played for some hours, working fine. ([`b647445`](https://github.com/eyeonus/Trade-Dangerous/commit/b6474451f718ad110429438fdbc7d397eb2e4130))

* check for black market ([`3c306ca`](https://github.com/eyeonus/Trade-Dangerous/commit/3c306cadec4b3ba6555bda6cbdf757343969c269))

* Change &#34;Location&#34; to &#34;Docked&#34; if docked ([`1b5034f`](https://github.com/eyeonus/Trade-Dangerous/commit/1b5034f6ea98aa71bad6d0273b9d5085a7d7c458))

* Updated EDAPI plugin to version 4.1.1 ([`73774a5`](https://github.com/eyeonus/Trade-Dangerous/commit/73774a547dbdfef2ed2baaa7bf864ce3680a0e1f))

* only change planetary if specified ([`4841a03`](https://github.com/eyeonus/Trade-Dangerous/commit/4841a03237539d835955d4c5d73d4adc077812fc))

* maddavo data update ([`9e3265f`](https://github.com/eyeonus/Trade-Dangerous/commit/9e3265fcf235b21b3b22b7a086d188722d472127))

* show category name of items for more detail view ([`63b7ef5`](https://github.com/eyeonus/Trade-Dangerous/commit/63b7ef5b075cb00633ff4ed1287ebf2b4d3e4d0b))

* new plugin for Journal parsing to import systems and stations ([`1a8f25a`](https://github.com/eyeonus/Trade-Dangerous/commit/1a8f25aff888e4222176827f214ef9e6f8d3f278))

* No more tabs to be consistent with the rest of the codebase. ([`4249ea6`](https://github.com/eyeonus/Trade-Dangerous/commit/4249ea6edcc37679044f8a693dccb91a3a23ed80))

* some price correction ([`1f24096`](https://github.com/eyeonus/Trade-Dangerous/commit/1f2409639b7ae46062d8b6d480ba26f01d299072))

* Data and RareItem update ([`c68567d`](https://github.com/eyeonus/Trade-Dangerous/commit/c68567de618cf8212f5a787282a278788b83708d))

* Updated EDAPI plugin to version 4.1.0 ([`3b2e3b7`](https://github.com/eyeonus/Trade-Dangerous/commit/3b2e3b7e16cb8cbcc14b523442d7ea2cd3ca6019))

* Data update from maddavo. ([`ac9eb43`](https://github.com/eyeonus/Trade-Dangerous/commit/ac9eb43fdbbc426383ddb98b496e8371fc122178))

* updated wording ([`5ec3b59`](https://github.com/eyeonus/Trade-Dangerous/commit/5ec3b598e577bdd2bad681ef074d75d4b5eeb1dc))

* Added Dolphin ([`e5353f5`](https://github.com/eyeonus/Trade-Dangerous/commit/e5353f578c4545d1f211fdd1396c4140b1ff5ac6))

* Updated the &#34;netLog&#34; plugin to parses new format since 2.3 ([`d012475`](https://github.com/eyeonus/Trade-Dangerous/commit/d012475ede3915d64a883b2e7f96d899505d87cd))

* save option is working again ([`b98ee31`](https://github.com/eyeonus/Trade-Dangerous/commit/b98ee3132a79ba474d05cf83863768998d78c381))

* Data update from maddavo ([`0fa0dbe`](https://github.com/eyeonus/Trade-Dangerous/commit/0fa0dbe919a9f8abf08066c6042afb0ea388c057))

* EDAPI update to 4.0.0 ([`49aff09`](https://github.com/eyeonus/Trade-Dangerous/commit/49aff09997dc100717922de315e1d93a0dabf263))

* Even with zero demandunits the station does pay the price ([`c6ed613`](https://github.com/eyeonus/Trade-Dangerous/commit/c6ed613248d79a77cfedb765d290fff8cd1348cd))

* maddavo data update ([`cdb48bb`](https://github.com/eyeonus/Trade-Dangerous/commit/cdb48bb296d8d6b01447cb8134d3ff11d3b7ed88))

* Beluga Liner ([`826cf7e`](https://github.com/eyeonus/Trade-Dangerous/commit/826cf7e46502acc53733e6308f3caffba9f1e18e))

* maddavo data update ([`9bc7242`](https://github.com/eyeonus/Trade-Dangerous/commit/9bc7242a0123815e8378c8b879ea02d009ea83aa))

* maddavo data update ([`9744fb3`](https://github.com/eyeonus/Trade-Dangerous/commit/9744fb338402c6a3321acd6b0614682d22f158c5))

* New EDDN schemas ([`5cbcdcc`](https://github.com/eyeonus/Trade-Dangerous/commit/5cbcdcc2e65086ab6b6b9f9618226460f49ad467))

* maddavo data update ([`53a7f98`](https://github.com/eyeonus/Trade-Dangerous/commit/53a7f98380843fcbc50d8ee14a94d1990416d3d3))

* Import from EDCD/FDevIDs: Add FDev symbols for modules and ships ([`309c356`](https://github.com/eyeonus/Trade-Dangerous/commit/309c35620e46e786439f1bc8ef40a629b0057828))

* maddavo data update ([`02e2481`](https://github.com/eyeonus/Trade-Dangerous/commit/02e2481fc59bbf4c12e8aa92029e86e2ce557833))

* maddavo data update ([`4b11cf3`](https://github.com/eyeonus/Trade-Dangerous/commit/4b11cf30cec283dac99166d131cb71ca91cd8177))

* maddavo data update ([`a333230`](https://github.com/eyeonus/Trade-Dangerous/commit/a3332304080e1b6043171ce1aa8129b583587856))

* I give up, make it a list. ([`86f9468`](https://github.com/eyeonus/Trade-Dangerous/commit/86f9468501498984c628b5c49ca9717a8c19259b))

* I don&#39;t like MD syntax ([`c0504a9`](https://github.com/eyeonus/Trade-Dangerous/commit/c0504a94290950f42ae4a517a1595a5ed91555c2))

* more playing with the MD syntax ([`daea97c`](https://github.com/eyeonus/Trade-Dangerous/commit/daea97cb78cf2b937c516631cca7ecd0da646266))

* Updated EDAPI plugin to version 3.7.4 ([`f800b0c`](https://github.com/eyeonus/Trade-Dangerous/commit/f800b0c05f1ea4c45a68c1a4d6d0cd1c40a7187c))

* Ask for station update if a API&lt;-&gt;DB diff is encountered. ([`bcd8fab`](https://github.com/eyeonus/Trade-Dangerous/commit/bcd8fabd733894557b9afcdfbbee4668e42b6e57))

* New option &#34;test=[FILENAME]&#34; to test the plugin. ([`8458893`](https://github.com/eyeonus/Trade-Dangerous/commit/845889390c6992613154763e7085e337f39ace50))

* Let the user know about the API response. ([`0b061d9`](https://github.com/eyeonus/Trade-Dangerous/commit/0b061d928e80ad82f0d7755f09af68bb2534e588))

* Updated EDAPI plugin to version 3.7.3 ([`65776ab`](https://github.com/eyeonus/Trade-Dangerous/commit/65776ab8e23e475b45ab04398ef8515d591129ce))

* reworked station data handling and consistency check. ([`39aca09`](https://github.com/eyeonus/Trade-Dangerous/commit/39aca095b72501af494a915f124ecc15e2432e8b))

* still playing with the MD syntax ([`11600b5`](https://github.com/eyeonus/Trade-Dangerous/commit/11600b532233247468ca6685f216d65fce51c74c))

* playing with the MD syntax ([`9ea4346`](https://github.com/eyeonus/Trade-Dangerous/commit/9ea434679b680fba9eca60d712189db2cc42066a))

* More help for missing &#39;FDEVLOGDIR&#39; ([`fcb90ac`](https://github.com/eyeonus/Trade-Dangerous/commit/fcb90ac45f5b89db1d6384bcc3864fe01935ab89))

* ups, missed dictionary TradeDB.itemByFDevID for new EDCD plugin. ([`0929a43`](https://github.com/eyeonus/Trade-Dangerous/commit/0929a43a1b222126a043698b791c104e44838d06))

* added EDCD plugin bash completition ([`dfe167b`](https://github.com/eyeonus/Trade-Dangerous/commit/dfe167b9aa49ff8af7e5bcdf621005abce05fc18))

* data update from maddavo ([`c573443`](https://github.com/eyeonus/Trade-Dangerous/commit/c5734430d313a3a77fec991d1f0808f443bab86f))

* updated docu ([`1535aeb`](https://github.com/eyeonus/Trade-Dangerous/commit/1535aebce6258c2437c7ccb7da90047bec44f0e0))

* EDCD plugin is working :) ([`f8df71b`](https://github.com/eyeonus/Trade-Dangerous/commit/f8df71bc191d20244c37c13c03fe518fb87f0e3a))

* not in use anymore ([`96fa5a2`](https://github.com/eyeonus/Trade-Dangerous/commit/96fa5a21635d78ff4ced74911ca82cc682f10f38))

* search also for backslash (because of some shell path mangling). ([`0affbd1`](https://github.com/eyeonus/Trade-Dangerous/commit/0affbd1b1ed0bf0ff8253e7678a033ae6959dafc))

* some more rework, allow stations without market but maybe outfitting or shipyard.
Make the consistency check not only for EDDN but also for the database. ([`b9b52c3`](https://github.com/eyeonus/Trade-Dangerous/commit/b9b52c36ee6f8c3ee9419de306fd661f966f35d8))

* Added consistency check for what to post to EDDN compared to what the station should offer. ([`9ce9f87`](https://github.com/eyeonus/Trade-Dangerous/commit/9ce9f870effef6884b88ae4a563a7f1659f2c029))

* reworked demand/supply handling ([`9cfde03`](https://github.com/eyeonus/Trade-Dangerous/commit/9cfde0314891f340dad4f91f77d4b1344a49f926))

* we have planetStates for the planetary column ([`1adeab6`](https://github.com/eyeonus/Trade-Dangerous/commit/1adeab6a705cf3dda262562853e995fef4ac2922))

* Show fullname of commontity &#39;Category/ItemName&#39; ([`385a06a`](https://github.com/eyeonus/Trade-Dangerous/commit/385a06affa5fb8a0acdded8082449fcdb5d8044b))

* Corrected Exception message. ([`13a1779`](https://github.com/eyeonus/Trade-Dangerous/commit/13a17792913e5c7d349755404dda69573e491dd0))

* Call new EDCD plugin for option &#39;edcd&#39; ([`1a53ea6`](https://github.com/eyeonus/Trade-Dangerous/commit/1a53ea6db896063b41b7ac6a410cef3db55954ca))

* New EDCD plugin which also can update the items.
Updated some data. ([`749f47b`](https://github.com/eyeonus/Trade-Dangerous/commit/749f47b4a4e3405db666a9e5ee58d7b4829148e3))

* Ups, one too many. ([`9ace01d`](https://github.com/eyeonus/Trade-Dangerous/commit/9ace01dca3a00293df9721a8590aab07b6d6a397))

* Added new columns to Ship() and Item() class. ([`e989696`](https://github.com/eyeonus/Trade-Dangerous/commit/e989696bbaac33dcb3c12fcc5c3757fde0547ef5))

* updated rare items ([`7b27c32`](https://github.com/eyeonus/Trade-Dangerous/commit/7b27c32ea82b007baa14f4e2e3e049a13806db24))

* Corrected column order ([`d2241ec`](https://github.com/eyeonus/Trade-Dangerous/commit/d2241ec535c8dd8bd16b4e3546e8878f2ae02062))

* Show Category/Itemname if more detail is requested. ([`c5b7840`](https://github.com/eyeonus/Trade-Dangerous/commit/c5b784060c4299494afbae91b5d84122cfd9c25d))

* Added category and suppressed to RareItem and updated data. ([`4c5b040`](https://github.com/eyeonus/Trade-Dangerous/commit/4c5b0408055521e92949c3c35a5adfa79643c826))

* updated optionlist fro plugins ([`d8855ef`](https://github.com/eyeonus/Trade-Dangerous/commit/d8855ef286d19170923ee6a5dc59ad01463865b1))

* show actuall options from the plugin ([`3f802f5`](https://github.com/eyeonus/Trade-Dangerous/commit/3f802f559ccc2a1cd4bb76cce2173003dcd956ff))

* new revision, no code change ([`9924dc5`](https://github.com/eyeonus/Trade-Dangerous/commit/9924dc5f8ce77778e607fe49bdeb7709ae90e32c))

* updated option description ([`5305f04`](https://github.com/eyeonus/Trade-Dangerous/commit/5305f0430e180283ddff7e59fb8e3ef254b5f198))

* added netlog plugin and options ([`082df4e`](https://github.com/eyeonus/Trade-Dangerous/commit/082df4e1524d04aefe5d8cb25a771813688ff5e2))

* New import plugin &#39;netLog&#39; ([`6c65846`](https://github.com/eyeonus/Trade-Dangerous/commit/6c658464c4593283e3fbf1b050163d9d3ddaae58))

* Added &#34;edcd&#34; option to completion ([`23b0244`](https://github.com/eyeonus/Trade-Dangerous/commit/23b02448b6a1692c34ed68189e819a6f174a96db))

* Added new options to EDAPI description ([`af5a113`](https://github.com/eyeonus/Trade-Dangerous/commit/af5a113e31075fcd66d0e30f78a2a912a540c719))

* check for argument class instead of colCount ([`aa53faa`](https://github.com/eyeonus/Trade-Dangerous/commit/aa53faa800532af80c8f66c0331b64054174bfc2))

* added list of changes (implemented issue #5) ([`5507a12`](https://github.com/eyeonus/Trade-Dangerous/commit/5507a129f778ffa2fcb749282e0736a5f70087d0))

* Added &#34;--planetary&#34; argument to to buy, local, nav, rares, run and sell
command. The &#34;--no-planet&#34; and &#34;--planetary&#34; arguments are mutually
exclusive. ([`32f2d9c`](https://github.com/eyeonus/Trade-Dangerous/commit/32f2d9c0f559e795a85c39e5031ee594019e33d7))

* Data update from maddavo ([`b84678a`](https://github.com/eyeonus/Trade-Dangerous/commit/b84678a8a2c82923b270e4b9adb14541f6990940))

* merge comment ([`58dc961`](https://github.com/eyeonus/Trade-Dangerous/commit/58dc9611a7555a8ba8a029068b79b1d6a19a4d79))

* added list of changes ([`da3e31b`](https://github.com/eyeonus/Trade-Dangerous/commit/da3e31ba87201a4a3cc687f1cc53fc1935d52d8b))

* Update EDAPI plugin to version 3.7.0:
- New option &#34;edcd&#34; to download FDevShipyard and FDevOutfitting data.
- Using new mapping classes to map the IDs from the API.
- Delete old ShipVendor entries to avoid stale data. ([`3aba6a9`](https://github.com/eyeonus/Trade-Dangerous/commit/3aba6a9da9c3d754787b2c145d0bc36783e2ee25))

* Added FDEVMapping classes for Items, Ships, Shipyard and Outfitting. ([`8ce1edf`](https://github.com/eyeonus/Trade-Dangerous/commit/8ce1edf67e1e58b9bebe1479d9798090a208373d))

* Added new tables for FDevID -&gt; EDDN mapping.
Ignore the corresponding csv files because these should be downloaded from
https://github.com/EDCD/FDevIDs ([`d5e73fb`](https://github.com/eyeonus/Trade-Dangerous/commit/d5e73fb3f8d153c435d0cf51069ce5405186186b))

* Always try to get the length. ([`96cec80`](https://github.com/eyeonus/Trade-Dangerous/commit/96cec8023f5a22777e4e8f3defe6b399afb7faa6))

* &#34;Chunked&#34; transfers don&#39;t need a length header. ([`89ef16e`](https://github.com/eyeonus/Trade-Dangerous/commit/89ef16e5d3fcf0124501818f7d62f90d0c6fd1e1))

* Added FDEV ID to Item and Ship table for API mapping and average price to
Item table. ([`d13ee39`](https://github.com/eyeonus/Trade-Dangerous/commit/d13ee3994ee85869037e175953f922718e0d227e))

* added atoconfirm ([`435b26c`](https://github.com/eyeonus/Trade-Dangerous/commit/435b26cc9e41fa4c927d9f64c39fea52862afb94))

* more to complete ([`f4570df`](https://github.com/eyeonus/Trade-Dangerous/commit/f4570df4dfd4b1461629c37d1fe53ef9c2a0df7e))

* Update EDAPI plugin to version 3.6.3 ([`3bf89c6`](https://github.com/eyeonus/Trade-Dangerous/commit/3bf89c63422dd53b7003b143760b739e4330e4f9))

* added EDSM to Added :) ([`3f99d2f`](https://github.com/eyeonus/Trade-Dangerous/commit/3f99d2fe6174251e68a7dad18086344dcd50f47b))

* added EDSM utils (implemented issue #1) ([`5788d10`](https://github.com/eyeonus/Trade-Dangerous/commit/5788d10d823c9212629a5f9c83bd7e36a8387abc))

* Renamed &#34;Low Temperature Diamond&#34; to &#34;Low Temperature Diamonds&#34; ([`3d61eb0`](https://github.com/eyeonus/Trade-Dangerous/commit/3d61eb0f8490dd9b3734e007a30f44a9c1a46276))

* imported maddavo data ([`61900ea`](https://github.com/eyeonus/Trade-Dangerous/commit/61900eacdb32e069799ce66b2bf0a34e0e4c486a))

* Renamed item &#34;Power Transfer Conduits&#34; to &#34;Power Transfer Bus&#34; ([`1991e6c`](https://github.com/eyeonus/Trade-Dangerous/commit/1991e6c9010fff51a7e2a90bdaca36dc5acbca90))

* undo last change, we do have a &#39;Power Transfer Conduits&#39; item. This will need more work and a correction for maddavo plugin ([`8b5085c`](https://github.com/eyeonus/Trade-Dangerous/commit/8b5085c082b0499a6a9b97c31adf557d841eed7a))

* one more mapping (reported by Eventure for EDMC) ([`6db031a`](https://github.com/eyeonus/Trade-Dangerous/commit/6db031a5192b2488867785f15b63bfde42f7f68c))

* synced with kfsone/master ([`83f1588`](https://github.com/eyeonus/Trade-Dangerous/commit/83f1588d0e6b965bd6ba4a273c73c35751c5bd3f))

* log changes ([`20de379`](https://github.com/eyeonus/Trade-Dangerous/commit/20de379666b8fffa9d1ea3abc39287cfaba2b85f))

* data update from maddavo ([`62650a2`](https://github.com/eyeonus/Trade-Dangerous/commit/62650a298d3fda9521a40f9de6fc4c2ab3c856e2))

* &#34;--no-planet&#34; switch now requires planetry to be &#34;N&#34; (issue #5) ([`f5a481b`](https://github.com/eyeonus/Trade-Dangerous/commit/f5a481b241e453974cf4686b20c1461ba20fbc84))

* Updated README with &#34;--no-planet&#34; switch and some small corrections. ([`3a732ec`](https://github.com/eyeonus/Trade-Dangerous/commit/3a732ec85436706561d27f936718c7b8a52d1e7d))

* New commodities for 2.1 update.y ([`71b955d`](https://github.com/eyeonus/Trade-Dangerous/commit/71b955d63637fe7b8191ab835f2f2a737040287e))

* Updated CHANGES and Data ([`03416f0`](https://github.com/eyeonus/Trade-Dangerous/commit/03416f0355df0ad6d2298f805eca125dc98b0abd))

* Merged in orphu/tradedangerous/eddn_shipyards (pull request #138)

Add support for posting shipyards to EDDN. Bug fixes. ([`c5adcd3`](https://github.com/eyeonus/Trade-Dangerous/commit/c5adcd371691612025d5417c2115aa7572577e06))

* Imported lots of new data from Maddavo ([`b6ab93e`](https://github.com/eyeonus/Trade-Dangerous/commit/b6ab93e5f20904110d08e0898463420bc39d6871))

* Horizon ship updates (thanks dave, fixes #4) ([`8b88dd8`](https://github.com/eyeonus/Trade-Dangerous/commit/8b88dd8ed16d9b5ab4803383bf1fac657fd94fd6))

* Ups, make it ship again ;) ([`6f243bc`](https://github.com/eyeonus/Trade-Dangerous/commit/6f243bc73edab65427ad632c18b89085a80224f2))

* Overlooked one check for noPlanet switch. Fixes bug #2 ([`db124eb`](https://github.com/eyeonus/Trade-Dangerous/commit/db124eb4cc29a458e839d283c660ff9d0279826d))

* Latest maddavo data update. ([`ac290d3`](https://github.com/eyeonus/Trade-Dangerous/commit/ac290d31822588518181c99cf7360cd421c2a874))

* Update EDAPI plugin to version 3.6.0 ([`561cfe3`](https://github.com/eyeonus/Trade-Dangerous/commit/561cfe364dfcf75e589d4066c594af74c53aa1bb))

* updated edapi plugin to lates version (and include planetary) ([`424a726`](https://github.com/eyeonus/Trade-Dangerous/commit/424a7260b90088dcc33baf8325c2b758f714c8e5))

* Added &#34;planetary&#34; column to station table and maddavo import.
Added &#34;--planetary&#34; argument to station command.
Added &#34;--no-planet&#34; switch to buy, local, nav, rares, run and sell command.
Added &#34;Plt: X&#34; output. ([`349967e`](https://github.com/eyeonus/Trade-Dangerous/commit/349967eaae73c931c5b294fcab4f6c6ab8f6253e))

* data update from maddavo ([`2a04bd1`](https://github.com/eyeonus/Trade-Dangerous/commit/2a04bd1eb3218857e61ecadfc11b0daf324d8568))

* New items with version 1.5/2.0 of ED ([`60981d8`](https://github.com/eyeonus/Trade-Dangerous/commit/60981d89e294a64452c72fbd57493f5eaee82153))

* Don&#39;t merge the prices form maddavo anymore (use --merge-import if you
need it). ([`08e1b85`](https://github.com/eyeonus/Trade-Dangerous/commit/08e1b85d26e3ae5d2adfb317179b9d6fa6f54783))

* Merge branch &#39;master&#39; into eddn_shipyards ([`1a20458`](https://github.com/eyeonus/Trade-Dangerous/commit/1a20458bdd1c9aaa6c70a9c989009993ada81f94))

* Merged kfsone/tradedangerous into master ([`975867d`](https://github.com/eyeonus/Trade-Dangerous/commit/975867db63a9a711133bfa6406cbe72733e1d443))

* Data ([`85a8152`](https://github.com/eyeonus/Trade-Dangerous/commit/85a81529263c85ec87e697e82fddc450e1a78365))

* Improved spinner ([`0614d8f`](https://github.com/eyeonus/Trade-Dangerous/commit/0614d8fb516d58ff308b3360056c8d77285eccc5))

* Merge branch &#39;master&#39; into eddn_shipyards ([`d819186`](https://github.com/eyeonus/Trade-Dangerous/commit/d8191866575e7888eb4c94e961f0063ee527b56b))

* Merged kfsone/tradedangerous into master ([`a58a0a2`](https://github.com/eyeonus/Trade-Dangerous/commit/a58a0a29395a4bd213e09c21655566a954b3a954))

* Ask user for market and shipyard if the api doesn&#39;t return one. He should know. ([`a94ec22`](https://github.com/eyeonus/Trade-Dangerous/commit/a94ec22d283d99052b3ca53d772bb3bca90f413b))

* Mad&#39;s ship data ([`55d4da6`](https://github.com/eyeonus/Trade-Dangerous/commit/55d4da6656d43feeca639d042d29801965cf0eae))

* Derp defense ([`04815c2`](https://github.com/eyeonus/Trade-Dangerous/commit/04815c21dae544386f50d29c3ff8871aff6e549f))

* More data, ... ([`7fd66ce`](https://github.com/eyeonus/Trade-Dangerous/commit/7fd66ce6b5d80a4fee327725ef906c3c6e13645a))

* Also, missing ships ([`722fdf3`](https://github.com/eyeonus/Trade-Dangerous/commit/722fdf36cfba33b906da10e931ffd5a33560308b))

* Big maddavo import of the year ([`1302c44`](https://github.com/eyeonus/Trade-Dangerous/commit/1302c4472e45b988618274c8b901c67589bde4f8))

* New items from Bernd. ([`72c3695`](https://github.com/eyeonus/Trade-Dangerous/commit/72c36958753ca6a1893070d160e01c3fcb104b4d))

* Fix plugin posting shipyards and modules without -O eddn. ([`c0f1d5e`](https://github.com/eyeonus/Trade-Dangerous/commit/c0f1d5e99d77fe7201e39378740f6310c9da5ebc))

* If the stockBracket is zero, ignore any stock. ([`8dba7c4`](https://github.com/eyeonus/Trade-Dangerous/commit/8dba7c41667ad0449f6292b17d899926a83b217e))

* Apply int casting fixes to EDDN. ([`a2cb3dd`](https://github.com/eyeonus/Trade-Dangerous/commit/a2cb3dda6a3e60ec14c764b943970aadbe91e065))

* Fixes crash in outfitting. Adds info to Ls from star prompt. ([`c07be5d`](https://github.com/eyeonus/Trade-Dangerous/commit/c07be5de4a4de769e5ba573e1feb72fbe65a86a7))

* Fix cast to int in lsFromStar. ([`2e61a70`](https://github.com/eyeonus/Trade-Dangerous/commit/2e61a70aa931d3fc67805323e50ad0b40f473be3))

* Version bump. ([`81482d3`](https://github.com/eyeonus/Trade-Dangerous/commit/81482d33eb773d6043c2c5fd029c8604df3466fc))

* Add EDDN outfitting v1. ([`019c1a9`](https://github.com/eyeonus/Trade-Dangerous/commit/019c1a985e4467aed705e8cc69828773fa038012))

* Adds 1.4 ships. ([`d48fd84`](https://github.com/eyeonus/Trade-Dangerous/commit/d48fd84c7bf601f0505655c5cdfa5f09f95d97e5))

* Work around a race condition in login. ([`131864d`](https://github.com/eyeonus/Trade-Dangerous/commit/131864df5d62e91768bce0ae4de0c51a7e33b545))

* Stop sell price thrashing. ([`a201ed2`](https://github.com/eyeonus/Trade-Dangerous/commit/a201ed25a774912a62a22dcb66cdf13e28199495))

* README Update. ([`8e45d14`](https://github.com/eyeonus/Trade-Dangerous/commit/8e45d14c9adcf69e38d07cba53054a60a5e8c8b8))

* Make updating ShipVendor.csv optional. ([`726b330`](https://github.com/eyeonus/Trade-Dangerous/commit/726b33066f6737ede3923d0ad9e93121c669338a))

* Removed duplicate EDDN def and cleanup. Oops. ([`d11dd04`](https://github.com/eyeonus/Trade-Dangerous/commit/d11dd04cc79c829ad13946f1ea95fbdc218f83be))

* Add support for posting shipyards to EDDN. ([`da4e44e`](https://github.com/eyeonus/Trade-Dangerous/commit/da4e44ef30c0a62013cccdfe79d54391b5f2bc4e))

* Merged kfsone/tradedangerous into master ([`b3c478b`](https://github.com/eyeonus/Trade-Dangerous/commit/b3c478b41d890f9fee6b25fdbdf29b1bf02ecdc1))

* Data cleanup per maddavo ([`81090cb`](https://github.com/eyeonus/Trade-Dangerous/commit/81090cb63890987b7e0bf4c715455bdc74f9dde4))

* 7.3.2 Another fix for EDAPI ([`1ffc7e3`](https://github.com/eyeonus/Trade-Dangerous/commit/1ffc7e3c06ebf8fe63744897b7685555d834a45a))

* Merged in maddavo/tradedangerous (pull request #137)

System name fixes ([`cd98fcf`](https://github.com/eyeonus/Trade-Dangerous/commit/cd98fcfc18bdea976710c1f8cf749110df8810e5))

* Merged kfsone/tradedangerous into master ([`803b207`](https://github.com/eyeonus/Trade-Dangerous/commit/803b207e8e18d1f058e0cb2c7fab4bdfdc63a3ad))

* Fixed issue with EDAPI plugin ([`f6e4298`](https://github.com/eyeonus/Trade-Dangerous/commit/f6e4298d8421d69bd6c2c8f01225effca1ea99d3))

* System name fixes ([`02588bd`](https://github.com/eyeonus/Trade-Dangerous/commit/02588bd0291bc84bb740ddf6f78db5349ed57aea))

* Merged kfsone/tradedangerous into master ([`879468f`](https://github.com/eyeonus/Trade-Dangerous/commit/879468f0ef1fff80aac7183759ecc4cf457635d8))

* Fixed division by zero in transfers.py ([`40a5f03`](https://github.com/eyeonus/Trade-Dangerous/commit/40a5f03bffab859de6021bf6220a22376aa90c06))

* Merged kfsone/tradedangerous into master ([`4256b31`](https://github.com/eyeonus/Trade-Dangerous/commit/4256b31317c1e222fbfc8947ef0c621ff4f178c0))

* Fred&#39;s categories change ([`4626a29`](https://github.com/eyeonus/Trade-Dangerous/commit/4626a2989fe6322ce85e2206f192db7195263d51))

* Refactor of ahamid&#39;s fromfile support ([`b8f0ddd`](https://github.com/eyeonus/Trade-Dangerous/commit/b8f0ddd1fe4a4e5026fee804a0cdcb3d4694e7e7))

* Merged in FredDeschenes/tradedangerous/buy-by-category (pull request #135)

Add search by category in &#39;buy&#39; command ([`c6ec3de`](https://github.com/eyeonus/Trade-Dangerous/commit/c6ec3def92281473ca6ab81c0511d0d84fce3efa))

* Add search by category in &#39;buy&#39; command ([`ff9b33c`](https://github.com/eyeonus/Trade-Dangerous/commit/ff9b33c0ab8c3651cafa75f895057f6a24ab53fb))

* Merged kfsone/tradedangerous into master ([`375a65e`](https://github.com/eyeonus/Trade-Dangerous/commit/375a65e77a1efdf8c168d2bf6f56d658bd555e9d))

* Data import ([`6a44638`](https://github.com/eyeonus/Trade-Dangerous/commit/6a4463848cd432f3fc1756cf744c4c64e917f22b))

* Another 100 systems ([`f12bcd7`](https://github.com/eyeonus/Trade-Dangerous/commit/f12bcd762b1727705a9f4c84b9410fa428b3dfa0))

* Today&#39;s change log ([`33e6e4f`](https://github.com/eyeonus/Trade-Dangerous/commit/33e6e4f0c4b924d9bf560469cfc1af6cd7351e53))

* Tiny optimization for tradedb ([`87c9e28`](https://github.com/eyeonus/Trade-Dangerous/commit/87c9e288c5ebd7b3d38980b5494609d7000cec66))

* Trivial optimization for tradecalc ([`64211b9`](https://github.com/eyeonus/Trade-Dangerous/commit/64211b9368732c37414d780b36283c4e98f75a0b))

* Lots of new systems ([`aa55436`](https://github.com/eyeonus/Trade-Dangerous/commit/aa5543627b57809c96725eb8315e3d536a4f9efa))

* Added --max-systems to edscupdate.py ([`d259e43`](https://github.com/eyeonus/Trade-Dangerous/commit/d259e43a6f7cb287eeb95271b9e75442fb6a753d))

* Bad name ([`84075a0`](https://github.com/eyeonus/Trade-Dangerous/commit/84075a06404656a62dde7ee91f7608ee108168e1))

* 7.2.1 just data ([`6a16f22`](https://github.com/eyeonus/Trade-Dangerous/commit/6a16f228a98ebe642832a61bc1eafd9cba019f5a))

* Merged kfsone/tradedangerous into master ([`6c6a1f0`](https://github.com/eyeonus/Trade-Dangerous/commit/6c6a1f074d5361cefec2d64b25d12da3443bf891))

* 7.2 merged Orphu&#39;s edapi plugin ([`511d7ea`](https://github.com/eyeonus/Trade-Dangerous/commit/511d7ea3c2d5bedb73d884bd30c8b486504a1d0a))

* Merged in maddavo/tradedangerous (pull request #134)

Fix some systems that moved ([`aa471ba`](https://github.com/eyeonus/Trade-Dangerous/commit/aa471ba7d12d2c12cdacd1ecb41895275c82dc0b))

* Merged in orphu/tradedangerous/edapi (pull request #133)

Add an API plugin ([`eb1c48e`](https://github.com/eyeonus/Trade-Dangerous/commit/eb1c48ead02f8b820429a1877cd3d2619d250d3c))

* More system fixes and added systems ([`4b8d118`](https://github.com/eyeonus/Trade-Dangerous/commit/4b8d11812349b14aab7af5429788b262edf1608c))

* More System updates ([`2368b84`](https://github.com/eyeonus/Trade-Dangerous/commit/2368b84fae651016268efb4d8d65c3f251064f5d))

* Fix BACTONDINKS and CORNGARI ([`6a7c3a3`](https://github.com/eyeonus/Trade-Dangerous/commit/6a7c3a3d57f68973bd8c00ed4dcd09c3f15670e2))

* Merged kfsone/tradedangerous into master ([`f709544`](https://github.com/eyeonus/Trade-Dangerous/commit/f70954411e6d61a99cd5ee3d5b5b3cee771b4149))

* Differentiate EDDN app info. ([`5269b73`](https://github.com/eyeonus/Trade-Dangerous/commit/5269b73730046a43487a220ebf6a2bb0aadba670))

* Add EDDN support to edapi_plug. Add plugin to README ([`8bceff2`](https://github.com/eyeonus/Trade-Dangerous/commit/8bceff28e468e7167ea12973c499cf95065b0b2f))

* Merge branch &#39;master&#39; into edapi ([`e643c74`](https://github.com/eyeonus/Trade-Dangerous/commit/e643c749ab259373f96ed7c0590b03ce9d304886))

* Merged kfsone/tradedangerous into master ([`7c6ecf5`](https://github.com/eyeonus/Trade-Dangerous/commit/7c6ecf5c92635058ad1a598d32d07a07d97ca046))

* added --ref to edscupdate ([`b1128a8`](https://github.com/eyeonus/Trade-Dangerous/commit/b1128a8435095e1a4dd077fc097f59de3185e711))

* v7.1.2 1.3 data fixes #241 fixes #240 ([`df1f1a0`](https://github.com/eyeonus/Trade-Dangerous/commit/df1f1a0c93e624cbfc2ca2dc1675a987d3e8511d))

* Salvage is okay. &#39;SAP 8 Core Container&#39; name correction. ([`0bdcd9c`](https://github.com/eyeonus/Trade-Dangerous/commit/0bdcd9caa38035ede733ca5a0195aa4bd4d51d05))

* 1.3 Fixes

Add new ships.
    DiamondBack
    DiamondBackXL
    Empire_Courier
Deal with demand better.
Ignore &#34;Salvage&#34; ([`10657ea`](https://github.com/eyeonus/Trade-Dangerous/commit/10657ea1c83789cb8d49c472969bcfaf37a79364))

* Added category correction for Slavery. ([`44a4ec6`](https://github.com/eyeonus/Trade-Dangerous/commit/44a4ec685e40ec9abff66aad06bfa12fee3eee53))

* Adds an API plugin.

* Station info.
* Market data on current station.
* Shipyard info at current station. ([`91c0f4f`](https://github.com/eyeonus/Trade-Dangerous/commit/91c0f4f7aac8e1d76e9d0c448e221cbb80745004))

* Merged kfsone/tradedangerous into master ([`b3f4f12`](https://github.com/eyeonus/Trade-Dangerous/commit/b3f4f12ae013dd0f7b3b59eca521a3a029073085))

* Merged kfsone/tradedangerous into master ([`fde6578`](https://github.com/eyeonus/Trade-Dangerous/commit/fde6578d532fdec42a14fbacb4449ba4e42ab615))

* 500+ new systems ([`ce748c3`](https://github.com/eyeonus/Trade-Dangerous/commit/ce748c3120a184153df73ace94a339390a8774de))

* added --distance to edscupdate ([`d84f492`](https://github.com/eyeonus/Trade-Dangerous/commit/d84f492603d45c7b1e6af4aeb1b607fbdb5a5eac))

* Merged kfsone/tradedangerous into master ([`f054f9d`](https://github.com/eyeonus/Trade-Dangerous/commit/f054f9da46ae4bc4dbd0e5a453784f60c2690c25))

* Merged in bgol/tradedangerous/devel (pull request #132) ([`3704a67`](https://github.com/eyeonus/Trade-Dangerous/commit/3704a672a821f3403ccad5fe8b2b1239aac6804c))

* Fixes #236 unicode errors ([`ae7bfa6`](https://github.com/eyeonus/Trade-Dangerous/commit/ae7bfa618e4da766c5570dff1271ca358e980355))

* Changed display of &#34;adding/removing ships&#34; in shipvendor sub-command and
handling of allready added/removed ships in the local database. ([`57218a2`](https://github.com/eyeonus/Trade-Dangerous/commit/57218a25128cbe517fd1edce34aa636b041de838))

* Fixed #234 presentation of adding ship in maddavo plugin ([`2bfce62`](https://github.com/eyeonus/Trade-Dangerous/commit/2bfce62263a64f1e0f750376eb617ffb096e0bb0))

* Fixed #233 Show &#34;system&#34; distance in run -v

. (kfsone) &#34;run&#34; command:
    - Added &#34;--show-jumps&#34; (aka -J)
    - Jumps are no-longer shown by default,
    - Request #233 Jumps now include distance
    - If start and end station of a hop are in the same system,
      display &#34;Supercruise to ...&#34; instead of a jump
    - When a hop involves multiple jumps using --show-jumps, it will
      tell you the direct and total distances,
. (kfsone) Revamped the intro of the README.md (http://kfs.org/td/source) ([`a4a6ce8`](https://github.com/eyeonus/Trade-Dangerous/commit/a4a6ce804aba8fb31a0e89b7898bbe644f03956b))

* Gazelle&#39;s utf corrections ([`c87246b`](https://github.com/eyeonus/Trade-Dangerous/commit/c87246bf491dc9fdc0bfdb00d5e60df3772ce5d3))

* Merged in bgol/tradedangerous/data (pull request #131)

Seems like FD has renamend the accented system names. ([`0e6b336`](https://github.com/eyeonus/Trade-Dangerous/commit/0e6b3361452b0a702bf3f31cc332edc6294ec7ff))

* Seems like FD has renamend the accented system names. ([`e424828`](https://github.com/eyeonus/Trade-Dangerous/commit/e4248288ee3a3cc267b2eeb5ec7ca87c12f08fcb))

* Merged kfsone/tradedangerous into master ([`f601305`](https://github.com/eyeonus/Trade-Dangerous/commit/f6013059c501745c160555f77784a4511efacc6a))

* Fix --age ([`0b1b78b`](https://github.com/eyeonus/Trade-Dangerous/commit/0b1b78bb69f7462f7733e9391e8d3229dbcf6575))

* maxAge vs station was broken ([`4b2d1b4`](https://github.com/eyeonus/Trade-Dangerous/commit/4b2d1b4c35ef32e3ba4421095e51df9233ae4466))

* Merged kfsone/tradedangerous into master ([`f66b150`](https://github.com/eyeonus/Trade-Dangerous/commit/f66b150ec4e675a331fdc3745e8c2f21cf55ad31))

* Fixes #232 &#39;supply&#39; values ignored in &#39;run&#39; ([`3644d11`](https://github.com/eyeonus/Trade-Dangerous/commit/3644d1130ce6cb704a3acef0eac8a05bf8586e54))

* Fixes #231 exception using --quantity with &#39;buy&#39; ([`eab6a6c`](https://github.com/eyeonus/Trade-Dangerous/commit/eab6a6c496f4b0a61f0a6235c2aec03617a217a5))

* Fixes #182 Add --demand option to run ([`73d4991`](https://github.com/eyeonus/Trade-Dangerous/commit/73d4991a3c847e58b342b7ce3e0cc26d3dc4c6c7))

* Numpy fix change entry ([`36331a8`](https://github.com/eyeonus/Trade-Dangerous/commit/36331a841f5a2613193d5065d9b6f1fa0c75e508))

* Typo ([`cbb123f`](https://github.com/eyeonus/Trade-Dangerous/commit/cbb123f12e02ce4cb7246003de3ca40e4fc3151f))

* Fix for disabling numpy requirement correctly ([`a949eab`](https://github.com/eyeonus/Trade-Dangerous/commit/a949eab2993e4cfe2fe90c1dcf9d1794344ca75b))

* Extra data and rares ([`fb43940`](https://github.com/eyeonus/Trade-Dangerous/commit/fb4394029e90e37b92d46900303a5db7d6917b30))

* Data ([`3554053`](https://github.com/eyeonus/Trade-Dangerous/commit/3554053e9f7338efa473b7875651aecf2fc5af87))

* Don&#39;t allow the impossible divide-by-zero in bandwidth ([`4092c99`](https://github.com/eyeonus/Trade-Dangerous/commit/4092c994bb9f6774255055d0fff0ca9468cba541))

* v7.0.1 ([`49ae455`](https://github.com/eyeonus/Trade-Dangerous/commit/49ae455f93703c07fd4893f47364b0e3859d1cea))

* Fix how we access avgBuy/avgSell ([`e699f0c`](https://github.com/eyeonus/Trade-Dangerous/commit/e699f0ca782b97d102ee28c04ff7f2128431bb01))

* Removed reference to tradingWith ([`4396779`](https://github.com/eyeonus/Trade-Dangerous/commit/439677957af9eb3d3c7f73a44a9f5b4e998dbb0e))

* Fixed exception caused by typos ([`2294898`](https://github.com/eyeonus/Trade-Dangerous/commit/22948989b1c30ff0a7f81e5c3ab9c2402d742038))

* Fix how we populate avgBuy/avgSell

We weren&#39;t populating Paninite (46) because there were no prices for it ([`8aeb45d`](https://github.com/eyeonus/Trade-Dangerous/commit/8aeb45d925b7836a3e7098fda9eb696d02e222a0))

* Merged kfsone/tradedangerous into master ([`e8bfdb6`](https://github.com/eyeonus/Trade-Dangerous/commit/e8bfdb66ae5f0b3d78492f1cfe110ab9889b9b6c))

* Try to provide more help with requests ([`e58dae5`](https://github.com/eyeonus/Trade-Dangerous/commit/e58dae5f419181388bdacd5818e0713ae29e0ae7))

* Merged kfsone/tradedangerous into master ([`951eec2`](https://github.com/eyeonus/Trade-Dangerous/commit/951eec234b365170f8609fc3b9e9035ee9704970))

* Version 7.0.0

Also Fixes #205 maddavo import behavior ([`954b5a7`](https://github.com/eyeonus/Trade-Dangerous/commit/954b5a7871832f54ce219178b9363a17e5d7dd18))

* Data update ([`8b6118a`](https://github.com/eyeonus/Trade-Dangerous/commit/8b6118aa03fc591052d00652ed17a82f5fcbdc3e))

* Try to avoid numpy experiment impacting regular usage ([`e15f9fc`](https://github.com/eyeonus/Trade-Dangerous/commit/e15f9fc80090dd0d652badcf2053405838ef674c))

* Making Avi&#39;s README.md the defacto README ([`38af9ca`](https://github.com/eyeonus/Trade-Dangerous/commit/38af9ca9d459d246f0f7c5f7c8a020334ebc7874))

* Rare column ([`4047755`](https://github.com/eyeonus/Trade-Dangerous/commit/40477551efc1b7122d5b70be824de087d4ed60a3))

* Added --illegal and --legal options to &#39;rare&#39; sub-command ([`5ba59ec`](https://github.com/eyeonus/Trade-Dangerous/commit/5ba59ecd5b0f3dd0a6d9b9d44c0567f4d3dbf075))

* It takes a while ([`c2c0444`](https://github.com/eyeonus/Trade-Dangerous/commit/c2c0444c2774e3d7cc2d6d33bab9e6a00f58d52d))

* Version 7.0.0

Includes:
Fixes #222 odd import behavior - see &#34;import --merge&#34;,
. (kfsone) Consistency of various commands:
. (kfsone) &#34;market&#34; command:
. (kfsone) &#34;nav&#34; command:
. (kfsone) &#34;buy&#34; and &#34;sell&#34; commands:
. (kfsone) Performance: ([`211523b`](https://github.com/eyeonus/Trade-Dangerous/commit/211523b05d49075643707d6a1cb8f6e851f17866))

* Normalized --avoid for places ([`95b3dbd`](https://github.com/eyeonus/Trade-Dangerous/commit/95b3dbd4faa148e90420068d32bda9b3652ef86e))

* Fixes #212 add --avoid to buy and sell ([`846b68f`](https://github.com/eyeonus/Trade-Dangerous/commit/846b68f7c1a436ed2c34228ecc9ba3b14ea622bd))

* Added --black-market to buy/sell ([`0f2fed2`](https://github.com/eyeonus/Trade-Dangerous/commit/0f2fed2be4d188eabb3c522727256ef7bfa224cb))

* buy/sell were using the wrong column name for price ([`95b0cd0`](https://github.com/eyeonus/Trade-Dangerous/commit/95b0cd043ce1ae376f2e202d0ece4217a17be283))

* Cleanup ([`109fcee`](https://github.com/eyeonus/Trade-Dangerous/commit/109fceea0846aa6026795515d095c7ea6f0a073c))

* Fix age -&gt; dataAge ([`5629c8b`](https://github.com/eyeonus/Trade-Dangerous/commit/5629c8b26e91c6ddd58bd6b6e7f491c4c1198326))

* Normalized --black-market, made use of helpers ([`6a7edbf`](https://github.com/eyeonus/Trade-Dangerous/commit/6a7edbfa0a5579f2d4e40c3d610eb44ffef2ea61))

* Helpers for standard arguments ([`ec93e46`](https://github.com/eyeonus/Trade-Dangerous/commit/ec93e4622636aec33483dc3bd208dfe865550777))

* Removed tradingWith default dataAge to None for stations ([`c7951a9`](https://github.com/eyeonus/Trade-Dangerous/commit/c7951a9bc25fc49885277c3b17820b28f29a14f5))

* Consistent use of data age

Added itemDataAgeStr to Station ([`4ad6bb4`](https://github.com/eyeonus/Trade-Dangerous/commit/4ad6bb4e78ba8737587c8d8992b95ce059011200))

* Make use of PadSizeArgument for consistency ([`19499ec`](https://github.com/eyeonus/Trade-Dangerous/commit/19499ece474d5004eade8b76bd09d3e7272951de))

* Added PadSizeError ([`707e79f`](https://github.com/eyeonus/Trade-Dangerous/commit/707e79f020d19bcd85722dfab805a63973249d02))

* Added parsing.PadSizeArgument ([`1caacc6`](https://github.com/eyeonus/Trade-Dangerous/commit/1caacc6bbb1e7832ec1f64d2c4b8ff901417bc2f))

* Cosmetic ([`8482c1b`](https://github.com/eyeonus/Trade-Dangerous/commit/8482c1baece35f1604f79588f3f58d2031eee4e8))

* Fix for &#34;nav&#34; using the wrong age calculation ([`285ff1f`](https://github.com/eyeonus/Trade-Dangerous/commit/285ff1fc9bc5f8709349365c4f53203caa76766a))

* All commands need to import * from parsing ([`e5e042f`](https://github.com/eyeonus/Trade-Dangerous/commit/e5e042fa8df882a13164bf74b7651621110d812a))

* Moved credit parser to parsing.py

All parser helpers should be in parsing.py, moved registration function there too ([`16cd764`](https://github.com/eyeonus/Trade-Dangerous/commit/16cd7643d35d1bfa0fbb9d9813302fea909e0fd9))

* Improved station loading

- Fixed how we load data age (some values were wrong),
- Improved performance, ([`112173b`](https://github.com/eyeonus/Trade-Dangerous/commit/112173b33e5575af2d630c0f08b0127a9c3e5f52))

* Merged kfsone/tradedangerous into master ([`3d4d9e3`](https://github.com/eyeonus/Trade-Dangerous/commit/3d4d9e3fed736d7e84b8c0cff55c5bfcc58ff26f))

* SQL for rare change ([`77c0343`](https://github.com/eyeonus/Trade-Dangerous/commit/77c03435f00a4afc6e59adaee90799bd09d31ae1))

* Fixes #217 add illegal flag to rares ([`fc804e3`](https://github.com/eyeonus/Trade-Dangerous/commit/fc804e38557b504a6222514931f9cd29121679c2))

* Data update ([`6e8af5b`](https://github.com/eyeonus/Trade-Dangerous/commit/6e8af5bbc2074e38729560b99a4b288c20edc886))

* Merge branch &#39;master&#39; into development

Conflicts:
	README.txt ([`dfcb44c`](https://github.com/eyeonus/Trade-Dangerous/commit/dfcb44c675b4f9259b9a4b6272613230e0d30b35))

* Only average non-zero prices ([`97f4a24`](https://github.com/eyeonus/Trade-Dangerous/commit/97f4a2414117f94df420fd6de8524e222aa05c10))

* Adding a system needs to invalidate the stellar grid ([`d7a2692`](https://github.com/eyeonus/Trade-Dangerous/commit/d7a2692ee4cf71f54112c9002a5f889ae1230b2a))

* Use requests for transfers.download

- transfers module now requires &#39;requests&#39;,
- automatic support for gzip/deflate compression of downloads,
- refactored the progress bar,
- cheap handling of &#39;no length available&#39; case. ([`72e378a`](https://github.com/eyeonus/Trade-Dangerous/commit/72e378afb5951c1271d0777158f63a50d2015f09))

* End of file cleanup ([`d2075a1`](https://github.com/eyeonus/Trade-Dangerous/commit/d2075a1361fabe791970bb19ebde149a196c1b3d))

* Fixed #230 SrcSystem not defined w/--unique ([`b319f07`](https://github.com/eyeonus/Trade-Dangerous/commit/b319f079e523b436293194435ab85d7f5b5dff52))

* fixes #229 -s and --toward ([`0def779`](https://github.com/eyeonus/Trade-Dangerous/commit/0def779bd2de4912e8946a269bf7677ff2266f21))

* Experimental numpy usage ([`5c99213`](https://github.com/eyeonus/Trade-Dangerous/commit/5c99213d8b7712395df08fe4a7bcbb3219d3473c))

* Make System.stations a tuple ([`5571916`](https://github.com/eyeonus/Trade-Dangerous/commit/55719165443d174124d9918ac856ee03e1251ecc))

* Merged kfsone/tradedangerous into master ([`ab41831`](https://github.com/eyeonus/Trade-Dangerous/commit/ab418314b1f56008b329ed11efe49fc7e8417863))

* Added --pad support to getRoute

This allows &#34;nav --pad&#34; to require a route with refuelling stops of a given pad size. ([`b11e3c8`](https://github.com/eyeonus/Trade-Dangerous/commit/b11e3c843d71703e4023b7d7d5f467fca3e61a2f))

* Perf tweaking of getRoute ([`0dc6c96`](https://github.com/eyeonus/Trade-Dangerous/commit/0dc6c964e77370bc87d94a7a5aff623d2d010879))

* Added --padSize to nav command ([`7be4cf0`](https://github.com/eyeonus/Trade-Dangerous/commit/7be4cf00b1412d2229803a218a631c8a4a3eb81c))

* Nav command cleanup

Use the existing &#34;dataAge&#34; value on station rather than trying to query it separately ([`ca23a05`](https://github.com/eyeonus/Trade-Dangerous/commit/ca23a059467f5d07e68934ecba1ad4b05e65088f))

* Minor cleanup ([`6d72f8b`](https://github.com/eyeonus/Trade-Dangerous/commit/6d72f8b7b2ddae469e5602d7c1e0cc1589d4e0ca))

* unused functions ([`fa56ce7`](https://github.com/eyeonus/Trade-Dangerous/commit/fa56ce78fb7eade475574212d2db2f45194dc9c1))

* Unused variable ([`99938c4`](https://github.com/eyeonus/Trade-Dangerous/commit/99938c4f728fd58528af14ec760110421cafe7a6))

* Merged in aadler/tradedangerous (pull request #130)

README updates ([`f8ebea1`](https://github.com/eyeonus/Trade-Dangerous/commit/f8ebea18da41d16421398865863a3ad0befb44f1))

* README.md created online with Bitbucket ([`cc87ebf`](https://github.com/eyeonus/Trade-Dangerous/commit/cc87ebf2778f95b0e5a76c449fe2c9883cc50090))

* README.txt edited online with Bitbucket ([`3680362`](https://github.com/eyeonus/Trade-Dangerous/commit/3680362680ed62756ffa6598c25d4edfdb7d56e8))

* Unbroke update command ([`9ac3406`](https://github.com/eyeonus/Trade-Dangerous/commit/9ac3406c188ffc58b235648a452fed13ca1525c8))

* Oops ([`de9cf38`](https://github.com/eyeonus/Trade-Dangerous/commit/de9cf389907324e4006c3cdb7632313b50b0ed20))

* Cleanup how we do distance pruning ([`52e4e4a`](https://github.com/eyeonus/Trade-Dangerous/commit/52e4e4aee2574a0b7fe6720fe2663e77d77c0ec2))

* Fix how we debug routes ([`5c8037c`](https://github.com/eyeonus/Trade-Dangerous/commit/5c8037c9e780ffee39191e11352acf148c3a8aa4))

* Merged kfsone/tradedangerous into master ([`c3d6308`](https://github.com/eyeonus/Trade-Dangerous/commit/c3d6308b6eaee46dfc95e10b01d9315821275842))

* cleanup ([`8a2b0be`](https://github.com/eyeonus/Trade-Dangerous/commit/8a2b0be7db387eb74d8c060a969d4746d20c207c))

* getTrades: one less store ([`e53e2eb`](https://github.com/eyeonus/Trade-Dangerous/commit/e53e2eb0b446c196e79d63496bfaf6fc0db1f121))

* unused variable ([`55f3310`](https://github.com/eyeonus/Trade-Dangerous/commit/55f331091ed302d2c4cf13190464f939694c2a77))

* Perf refactor of fastFit._fitCombos ([`21a228c`](https://github.com/eyeonus/Trade-Dangerous/commit/21a228cf130b6b28c372577e92dc39f0469cd44a))

* Optimized System distance functions

Less readable but all the extra stores added up ([`2a44a2d`](https://github.com/eyeonus/Trade-Dangerous/commit/2a44a2d7cdb37135bad8a11b6a2f68f34ef594b0))

* PyProj updates ([`2db75fb`](https://github.com/eyeonus/Trade-Dangerous/commit/2db75fb96697b0aae7d043b16460d7a30e047b96))

* Get best trades optimization ([`3e3530f`](https://github.com/eyeonus/Trade-Dangerous/commit/3e3530f4467bf2c9ed1cea55e97d06daa96d6b13))

* Fix pyproj test arguments ([`739db4d`](https://github.com/eyeonus/Trade-Dangerous/commit/739db4d5ef5717232251d2ed64607ee96c3e78a0))

* Whitespace/indent cleanup ([`95de1cf`](https://github.com/eyeonus/Trade-Dangerous/commit/95de1cf78bd8e071ab4e2e220801f101eabe21ac))

* Newlines at end of file cleanup ([`6ea2deb`](https://github.com/eyeonus/Trade-Dangerous/commit/6ea2debed90c49d9794b3a18cf31cd34185c0604))

* Debug assistance for update command exceptions

Honor the &#34;EXCEPTIONS&#34; environment variable used elsewhere. ([`831ff40`](https://github.com/eyeonus/Trade-Dangerous/commit/831ff4050c59c16a1967a4793f016df185f9eb05))

* Change default import behavior back to destructive,

- Added &#34;--merge-import&#34; option to import,
- Made mergeImport default behavior for maddavo&#39;s plugin,
- Renamed &#34;--reset&#34; to &#34;--reset-all&#34; so it&#39;s more obvious what it does, ([`5060a6d`](https://github.com/eyeonus/Trade-Dangerous/commit/5060a6debc735d43714337bf5e1d99ea9e85e779))

* Recombine Buying and Selling tables

- Moved StationBuying and StationSelling values into StationItem,
- Added StationBuying and StationSelling views,
- Changed &#34;stock&#34; to &#34;supply&#34; consistently,
- Added PARTIAL indexs to StationItem (where supply_price &gt; 0 and where demand_price &gt; 0), ([`68bf986`](https://github.com/eyeonus/Trade-Dangerous/commit/68bf986162d7cb90b45e27e60977fb89e5da4841))

* Minor tweak to how we declare routeStillHasAChance

Manually hoisting the conditional out of the loop, like it matters. ([`0a3c27f`](https://github.com/eyeonus/Trade-Dangerous/commit/0a3c27f47949475671ee026fbd251ef75a9b689c))

* Micro-optimization: Favor tuples over lists ([`14f82ef`](https://github.com/eyeonus/Trade-Dangerous/commit/14f82ef87722948245232395904bef3c182a0713))

* Fixed #227 start-jumps feedback

When start-jumps and end-jumps couldn&#39;t find a matching station, they fell through to other behavior rather and then failed elsewhere (telling the user no trade data was found) rather than indicating to the user that they are indirect origin/end searches.

This change provides clear feedback that it was looking for stations and found none ([`c0503f5`](https://github.com/eyeonus/Trade-Dangerous/commit/c0503f57fd4a89d77bf9df99ed1506029975e86c))

* Implements #219 Show gpt ([`acf7c7f`](https://github.com/eyeonus/Trade-Dangerous/commit/acf7c7fce842233b7a6741f1ed78f3e1730bf13c))

* GPT calculations

- Route.gpt does what it should,
- Route.avggpt does what Route.gpt used to do ([`0e3f35a`](https://github.com/eyeonus/Trade-Dangerous/commit/0e3f35a2e55a19212c501ad7b3dc2c7bf875b83c))

* Fix for --prune-score in README ([`b3ac41b`](https://github.com/eyeonus/Trade-Dangerous/commit/b3ac41b09b7cb866cbc86b1a4e371d0be0287f82))

* vs2015 version of pyproj ([`62c8c8b`](https://github.com/eyeonus/Trade-Dangerous/commit/62c8c8bfda95711c9544cea4d25a82c6b98943b8))

* Merged kfsone/tradedangerous into master ([`9883a8d`](https://github.com/eyeonus/Trade-Dangerous/commit/9883a8d20d9d413fb64e3135a11974e11738e97f))

* Reduced the cost of &#39;getTrades&#39; ([`4fbfb52`](https://github.com/eyeonus/Trade-Dangerous/commit/4fbfb52adec03e0d97945f88d8f5ac7547060a4a))

* Fixes #225 Generator already running ([`221d82b`](https://github.com/eyeonus/Trade-Dangerous/commit/221d82b6d6ec4dd93988ce4dbcfc0985208aa23c))

* Merge remote-tracking branch &#39;origin/master&#39;

Conflicts:
	tradecalc.py
	tradedb.py ([`1547da1`](https://github.com/eyeonus/Trade-Dangerous/commit/1547da1eefad61a466cfcb8cdd56026f0571b06a))

* Merged kfsone/tradedangerous into master ([`b1a4e7c`](https://github.com/eyeonus/Trade-Dangerous/commit/b1a4e7c220de10f96942dc3e01d709919512d1a8))

* v6.18.5 ([`a35ef74`](https://github.com/eyeonus/Trade-Dangerous/commit/a35ef74b297d5de38e464da5827603e6733d2a12))

* Fixes #224 run -vv was broken ([`967a7b5`](https://github.com/eyeonus/Trade-Dangerous/commit/967a7b50929f1a9ee71c102f0739d521adc519d4))

* Fixes #223 &#34;unrecognized system&#34; / &#34;unrecognized item&#34; errors after import ([`ffc7abe`](https://github.com/eyeonus/Trade-Dangerous/commit/ffc7abee957343b6af6d38a712771e3f13a3aece))

* Fix type error spotted by gazelle ([`28a357d`](https://github.com/eyeonus/Trade-Dangerous/commit/28a357d2a3574688935019c6f83794b3b4633286))

* Merged in bgol/tradedangerous/data (pull request #127)

some updates ([`857a2b7`](https://github.com/eyeonus/Trade-Dangerous/commit/857a2b765e5321240d24754b2d2a545a96dc2860))

* Revert &#34;Some minor python perf tuning&#34;

This reverts commit f831f56771f86e6052e663123436e2401038081e. ([`fdc90d1`](https://github.com/eyeonus/Trade-Dangerous/commit/fdc90d11e1d8b8fc6cd9a429fe552c7b49ab40e3))

* Merged kfsone/tradedangerous into master ([`5117425`](https://github.com/eyeonus/Trade-Dangerous/commit/511742516a30d90f9dbb6c4922b06cf03e009037))

* Some minor python perf tuning ([`f831f56`](https://github.com/eyeonus/Trade-Dangerous/commit/f831f56771f86e6052e663123436e2401038081e))

* Merged in bgol/tradedangerous/devel (pull request #128)

added the new parameters to the bash-competion ([`0500d8e`](https://github.com/eyeonus/Trade-Dangerous/commit/0500d8e3561849d0599bb6177a9608f945d81182))

* Merge commit &#39;18ea04c5e06e86516c624fcdf71b7b8d3072a9c9&#39;

* commit &#39;18ea04c5e06e86516c624fcdf71b7b8d3072a9c9&#39;:
  Fix for updateLocalSystem ([`e90b38e`](https://github.com/eyeonus/Trade-Dangerous/commit/e90b38e6c34858d5c3c0d1b8d75c222e323e2f38))

* Merged in maddavo/tradedangerous (pull request #129)

Fixed coordinates for PADHYAS ([`b4d5823`](https://github.com/eyeonus/Trade-Dangerous/commit/b4d58238784185553201429242d00cb5a66e08da))

* Fix for updateLocalSystem ([`18ea04c`](https://github.com/eyeonus/Trade-Dangerous/commit/18ea04c5e06e86516c624fcdf71b7b8d3072a9c9))

* Fixed coordinates for PADHYAS ([`71cdfee`](https://github.com/eyeonus/Trade-Dangerous/commit/71cdfee8f1b8f433d7d292d6e65ef4138074dff4))

* Merged kfsone/tradedangerous into master ([`788efbb`](https://github.com/eyeonus/Trade-Dangerous/commit/788efbb128a5defd0249281e22af81758932f1c7))

* Use score instead of gpt for shorten ([`a4dfadc`](https://github.com/eyeonus/Trade-Dangerous/commit/a4dfadcc547035fae6d9e06aa5f156fe1c0f535d))

* some updates ([`6281ba8`](https://github.com/eyeonus/Trade-Dangerous/commit/6281ba84973895e9d0802ae2f0810f55cfe6431d))

* Station data ([`9110082`](https://github.com/eyeonus/Trade-Dangerous/commit/911008200c5c4bc583b3374ee380a77ef51d7c04))

* Slight refactor of how shorten/loop pick routes ([`bd13be5`](https://github.com/eyeonus/Trade-Dangerous/commit/bd13be5d2a026515ebde07032939be900d80243c))

* Complain about --shorten and --loop first ([`f872467`](https://github.com/eyeonus/Trade-Dangerous/commit/f8724671f6db2f51bece06ac724276e743ede3b9))

* Two new parameters ([`f0c436d`](https://github.com/eyeonus/Trade-Dangerous/commit/f0c436dc30002614b15702e0bfcd86e2573741f3))

* Merge branch &#39;master&#39; into devel ([`c2580aa`](https://github.com/eyeonus/Trade-Dangerous/commit/c2580aab4522de90d38bcf953663bde50d82e3e1))

* Handful more systems ([`cc89031`](https://github.com/eyeonus/Trade-Dangerous/commit/cc890314fc06eca9734230c575766de093d44055))

* Added timestamp sanity check for Systems to avoid constraint errors during importing new systems ([`6257bdc`](https://github.com/eyeonus/Trade-Dangerous/commit/6257bdcd1d31d503e416b5e016a95af4e6fdba91))

* More systems ([`5df60bd`](https://github.com/eyeonus/Trade-Dangerous/commit/5df60bd0c7b1577865c733ad369318dabf0a9014))

* One last tweak of shorten debugging ([`78f9c5d`](https://github.com/eyeonus/Trade-Dangerous/commit/78f9c5d7bdcabb3b561c669054e9ad91dacdd8c0))

* Minor tidy up of shorten ([`0762035`](https://github.com/eyeonus/Trade-Dangerous/commit/07620353c7a5cff8f0f962b41c3a93121bf5d06c))

* When using --shorten, don&#39;t barf if we can&#39;t make the last hop ([`5d20a43`](https://github.com/eyeonus/Trade-Dangerous/commit/5d20a43008d6790c5c39e240adf4bbdbe80b651e))

* Merged kfsone/tradedangerous into master ([`00874c4`](https://github.com/eyeonus/Trade-Dangerous/commit/00874c4b57f61482e34e51da4c9995615d298180))

* Couple more systems ([`4d9514c`](https://github.com/eyeonus/Trade-Dangerous/commit/4d9514cb78ab7c07c115bed40d1260a41f3b0c28))

* Data ([`2c6a088`](https://github.com/eyeonus/Trade-Dangerous/commit/2c6a088065fc41b2ab093d0f8a60cd957cf67ebd))

* +300 systems ([`16c9a8b`](https://github.com/eyeonus/Trade-Dangerous/commit/16c9a8b1f802e6f30e05e17d4f4cc419684488f1))

* --shorten ([`6aa2c98`](https://github.com/eyeonus/Trade-Dangerous/commit/6aa2c98b52343ece9f4d5ecdaf085fbd6ee5a103))

* Another bad system ([`2781a88`](https://github.com/eyeonus/Trade-Dangerous/commit/2781a882780d579fcb44f310c426c865a475797d))

* 6.18.2 Added --loop-int ([`c74e137`](https://github.com/eyeonus/Trade-Dangerous/commit/c74e1376be5c084dbaabbc80e9d854d699c28aaa))

* Merge branch &#39;master&#39; into devel ([`928450c`](https://github.com/eyeonus/Trade-Dangerous/commit/928450c5f9ee2bae91462da8f85f0a9f05aa5432))

* Merged kfsone/tradedangerous into master ([`a2e98b4`](https://github.com/eyeonus/Trade-Dangerous/commit/a2e98b4876f1e26b04e889b50fcb5ef6ae6a8c46))

* Merged in maddavo/tradedangerous (pull request #126)

Fix for corrections.py ([`4c20208`](https://github.com/eyeonus/Trade-Dangerous/commit/4c202082fff12201a24156be080f59387ebc4cdd))

* Removed corrections referring to same station ([`6fd61f6`](https://github.com/eyeonus/Trade-Dangerous/commit/6fd61f6d37aefa118e1a7de4d5d91386b7af864d))

* Merged kfsone/tradedangerous into master ([`9f14c50`](https://github.com/eyeonus/Trade-Dangerous/commit/9f14c5020947fc13b98590280c0c07803c88d34c))

* 200+ new systems ([`438f0cc`](https://github.com/eyeonus/Trade-Dangerous/commit/438f0ccd38e9437d46da0e3f8abfe510db38e0ab))

* Chunk more systems ([`244f2ce`](https://github.com/eyeonus/Trade-Dangerous/commit/244f2cec4b7e49443e210fd5b03bb8431494df29))

* Market flags ([`222b624`](https://github.com/eyeonus/Trade-Dangerous/commit/222b62492517cbf358597e279640e07b695bf920))

* Data ([`8b5e520`](https://github.com/eyeonus/Trade-Dangerous/commit/8b5e520cd628e4289b982f860f14840f8371a824))

* Try a little harder to use mad&#39;s corrections ([`a4ea8c0`](https://github.com/eyeonus/Trade-Dangerous/commit/a4ea8c00da8452ff5ab235b9e402466a3e19711c))

* Use mad&#39;s corrections during the import

As we load his corrections, also add them to our own, so that
we won&#39;t immediately ignore them and re-import data that the
correction list told us was bad. ([`3c8ccc8`](https://github.com/eyeonus/Trade-Dangerous/commit/3c8ccc82bdfaf7c499d9bbb18fa56c6aa3e7a56b))

* 6.18.1 ([`bd17935`](https://github.com/eyeonus/Trade-Dangerous/commit/bd179354fa6568eb5fdf259355c259c1802b73a1))

* Force market flag to &#39;Y&#39; when we have items after import ([`f9c31a1`](https://github.com/eyeonus/Trade-Dangerous/commit/f9c31a1f44aeee9583fcb590207ffa3231255ffc))

* Force market to behave as &#34;Y&#34; when there are items at a station ([`08fc775`](https://github.com/eyeonus/Trade-Dangerous/commit/08fc77566544b1c396597b636cc96965c34e8fb8))

* Merged kfsone/tradedangerous into master ([`fec9815`](https://github.com/eyeonus/Trade-Dangerous/commit/fec98151188278a9ba0e4f1b369e429cba971bce))

* Merge branch &#39;master&#39; into devel ([`0e48be7`](https://github.com/eyeonus/Trade-Dangerous/commit/0e48be7316c3199b7f3a208ccf48efd2a6ede542))

* Fixes ([`da6bf0a`](https://github.com/eyeonus/Trade-Dangerous/commit/da6bf0ab4db079dfcafd4afc3fb06c60bec35b81))

* Last bit of data for today ([`0fa6269`](https://github.com/eyeonus/Trade-Dangerous/commit/0fa62695904fcd66a1b3bc7f0bc820d3a735fa32))

* Minor tweaks ([`a54287a`](https://github.com/eyeonus/Trade-Dangerous/commit/a54287a9017eb7fae9d72e08d12def7fd4e2328e))

* Merged in bgol/tradedangerous/data (pull request #125)

Argl, the keys must be UPPERcase ([`d962bc0`](https://github.com/eyeonus/Trade-Dangerous/commit/d962bc06fcc80680fe50023b5c6d2dac7cd55589))

* Argl, the keys must be UPPERcase ([`ea05580`](https://github.com/eyeonus/Trade-Dangerous/commit/ea05580a02d24c3522361477f8c584db0752316b))

* More data ([`78ea7eb`](https://github.com/eyeonus/Trade-Dangerous/commit/78ea7eb605a65a9730a88d2dd60927d53d370ccc))

* Data fixes ([`f591c81`](https://github.com/eyeonus/Trade-Dangerous/commit/f591c813f9eaa7b5971d121295350d912eb0aefd))

* Merge branch &#39;master&#39; into devel ([`18bfd80`](https://github.com/eyeonus/Trade-Dangerous/commit/18bfd8016fcac1e287e85f93529ba4aa4ff6e768))

* More systems ([`16498d8`](https://github.com/eyeonus/Trade-Dangerous/commit/16498d893a35e5d9c2b7ea0a78441a267febd307))

* Fixes #216 --direct crashed with no --ly or --jumps ([`b33ccff`](https://github.com/eyeonus/Trade-Dangerous/commit/b33ccff3c8d78f65f921dd56b8795bdf42d82710))

* 6.18.0 Fixes #215 Removing AltItemName table ([`9263e72`](https://github.com/eyeonus/Trade-Dangerous/commit/9263e728a5b33e9eaa8e6d7ac343f2d9d8edc8e6))

* Data update ([`74ff12a`](https://github.com/eyeonus/Trade-Dangerous/commit/74ff12a41c3b4eaa6a49b77b19bbca1ccc927303))

* Merged in bgol/tradedangerous/data (pull request #124)

data update ([`a535291`](https://github.com/eyeonus/Trade-Dangerous/commit/a535291116bdbcf15b1b1a74471470b1b2d54954))

* data update ([`6f5649d`](https://github.com/eyeonus/Trade-Dangerous/commit/6f5649d98af96bb861f70c1afa6a411c0993ed30))

* Merge branch &#39;master&#39; into devel ([`e4af51a`](https://github.com/eyeonus/Trade-Dangerous/commit/e4af51ac3162eb6b90d7cda73c7b4aa31a4072a9))

* Little bit more data ([`64f3e88`](https://github.com/eyeonus/Trade-Dangerous/commit/64f3e882ee83b6b8842220bbf438d002098d33be))

* More systems ([`d569ba9`](https://github.com/eyeonus/Trade-Dangerous/commit/d569ba9ed214d8d1543f83b129e0baa52337c0f9))

* More systems ([`1a79992`](https://github.com/eyeonus/Trade-Dangerous/commit/1a79992728ae35b7548e390920db6ed5651ed23c))

* Merge branch &#39;master&#39; into devel ([`76e8f02`](https://github.com/eyeonus/Trade-Dangerous/commit/76e8f02c980782000df8386d803dbf9d2d309210))

* Data ([`d82dd97`](https://github.com/eyeonus/Trade-Dangerous/commit/d82dd97b87291a2495545d752dd9e717296f359b))

* Merged kfsone/tradedangerous into master ([`276c4e5`](https://github.com/eyeonus/Trade-Dangerous/commit/276c4e50c93d1115408e29078b3adde4c1fa306f))

* 6.17.5 Fixed problem with &#39;import&#39; not updating dates ([`30f77f7`](https://github.com/eyeonus/Trade-Dangerous/commit/30f77f7527d502277999eb3ad982d92d469f60dc))

* minor tweaks ([`c87df6e`](https://github.com/eyeonus/Trade-Dangerous/commit/c87df6e61d9a4be34f1fc43f790dd2b8f957b737))

* Presentation of the import command ([`2db7114`](https://github.com/eyeonus/Trade-Dangerous/commit/2db71145b4091b0974f71574f1920c6d30260042))

* Added &#34;-P&#34; alias for &#34;--plug&#34; option of &#34;import&#34; command ([`183eb1e`](https://github.com/eyeonus/Trade-Dangerous/commit/183eb1e023e3ee82a972c25c28b7f6bfb24afa3c))

* Merge branch &#39;master&#39; into devel ([`4bbf2a9`](https://github.com/eyeonus/Trade-Dangerous/commit/4bbf2a9f65846a4b57e8c36af2e978b17685a2e4))

* commands ([`d553e5a`](https://github.com/eyeonus/Trade-Dangerous/commit/d553e5a15a5c803f1c7e2bd754cf8d9a2d2c621e))

* Data ([`a49db41`](https://github.com/eyeonus/Trade-Dangerous/commit/a49db41ef808a53252cd5caf4f082e3cf61327f8))

* Fixed setting 0 in the UI not removing an item

Because deletes don&#39;t have dates, they could never superceed the
data they were trying to remove, so the incremental update change
had broken the ability to remove an item from a station. ([`9850b8f`](https://github.com/eyeonus/Trade-Dangerous/commit/9850b8f437d40a29e37013e1bc7e7546a8311cfb))

* Merge branch &#39;master&#39; into devel ([`e6b00f1`](https://github.com/eyeonus/Trade-Dangerous/commit/e6b00f11ba15096cc6bc784c42ad0a3c117b08c9))

* two new options for run command ([`813223f`](https://github.com/eyeonus/Trade-Dangerous/commit/813223f8141bad36a20d2a4920e54f612926fc9c))

* More data ([`2d7809f`](https://github.com/eyeonus/Trade-Dangerous/commit/2d7809ffa8eea2af3f0b7fb7b1c62c57486a48c5))

* Eddb merge ([`28186ed`](https://github.com/eyeonus/Trade-Dangerous/commit/28186edfea47727735a0edbba0eb4ad3b52fbca4))

* More data ([`2fde3df`](https://github.com/eyeonus/Trade-Dangerous/commit/2fde3df7687716d43bf4979cb4f4f3b7d0125762))

* More data ([`ac83194`](https://github.com/eyeonus/Trade-Dangerous/commit/ac83194237147486a6696e67dba53309e7266170))

* Data ([`f88bc32`](https://github.com/eyeonus/Trade-Dangerous/commit/f88bc324904a5c0f5f9fec3d221f3f0c553c0673))

* Don&#39;t sort by proximity when using near ([`5ca3ddb`](https://github.com/eyeonus/Trade-Dangerous/commit/5ca3ddbb9384d07ef9703ea20653d86caaeb8a4b))

* Tightened --summary ([`2f94584`](https://github.com/eyeonus/Trade-Dangerous/commit/2f94584ed6ebdf94d6fb719fb54e21f1cb4b1da2))

* 6.17.3 ([`da3006b`](https://github.com/eyeonus/Trade-Dangerous/commit/da3006be3f090a268f933dc3868cd3c5c0e69d7a))

* Fix for an error that can occur when pruning finds nowhere to go ([`6bf07b7`](https://github.com/eyeonus/Trade-Dangerous/commit/6bf07b7e1632d6ebc25021fc5821f9e2eed6621e))

* Credits for gazelle/bash completion ([`26d8e43`](https://github.com/eyeonus/Trade-Dangerous/commit/26d8e43016b2a8605f21b9ebafef92c582f370c3))

* Merged in bgol/tradedangerous/devel (pull request #123)

bash completion update to current version ([`6884613`](https://github.com/eyeonus/Trade-Dangerous/commit/6884613b21a983a3c7f803fa1eec879d5986e227))

* Data ([`a11b534`](https://github.com/eyeonus/Trade-Dangerous/commit/a11b534973883a5e21c6809110146edd38aa28c1))

* 6.17.2 ([`5b553e9`](https://github.com/eyeonus/Trade-Dangerous/commit/5b553e9d21c06a46d39c7f3642afc5669f05a5a9))

* Systems/Data ([`0ef6e0b`](https://github.com/eyeonus/Trade-Dangerous/commit/0ef6e0be1a6330c7ca3fd7f74c444d7b76762113))

* Put the --from at the end of the command line to make it easier to remove ([`4c2aea8`](https://github.com/eyeonus/Trade-Dangerous/commit/4c2aea88a53d9534da50e16bc57b55bf5aff52d0))

* 6.17.1 ([`5890b08`](https://github.com/eyeonus/Trade-Dangerous/commit/5890b08b082998855cb1b12a753fa2ba9f5f732c))

* Merge branch &#39;devel&#39; of bitbucket.org:bgol/tradedangerous into devel ([`626b8d5`](https://github.com/eyeonus/Trade-Dangerous/commit/626b8d59f7ca474ee6d0d73c32e24fa7fde69124))

* adapted to current version (6.17.0) ([`61b3662`](https://github.com/eyeonus/Trade-Dangerous/commit/61b36622cb4736237d804cd406f81b046e399d3d))

* added missing T ;) ([`108ab4f`](https://github.com/eyeonus/Trade-Dangerous/commit/108ab4f74b2d7ad35a33fec4f1a86a201c35c9b9))

* More data ([`a139fd8`](https://github.com/eyeonus/Trade-Dangerous/commit/a139fd84feffa79085f3f323aacb9f7fd40ecb24))

* Data ([`d050d41`](https://github.com/eyeonus/Trade-Dangerous/commit/d050d41620c1acd2686f00eb6d5e251448956930))

* 100+ new systems ([`5ce258a`](https://github.com/eyeonus/Trade-Dangerous/commit/5ce258aa290f966d507d76437755fa352d7e23b5))

* Fix for conf 0 ([`5433e6c`](https://github.com/eyeonus/Trade-Dangerous/commit/5433e6c4ef66f71b190a4af94346a20bbd1ce7ae))

* Couple of improvements to &#39;old&#39; command ([`3ecfd46`](https://github.com/eyeonus/Trade-Dangerous/commit/3ecfd46444e85bd859caf72e4c27f39c24a964d6))

* adapted to current version (6.17.0) ([`c1842fa`](https://github.com/eyeonus/Trade-Dangerous/commit/c1842faef276558baa79123ca30bfc540df96067))

* Data ([`1b684aa`](https://github.com/eyeonus/Trade-Dangerous/commit/1b684aa610ec382776ac452ee1cb67d1fab068a2))

* Additional detail on progress lines in run command ([`da2719e`](https://github.com/eyeonus/Trade-Dangerous/commit/da2719eb151bb40d1e754091640bf9af28b4b401))

* gpt properties for TradeLoad and Route ([`b2e5f12`](https://github.com/eyeonus/Trade-Dangerous/commit/b2e5f12168a677d71365a70e3cd8158827508b72))

* added missing T ;) ([`d9d41f4`](https://github.com/eyeonus/Trade-Dangerous/commit/d9d41f428849258e5e88e520a97de7c34a6c38da))

* Data ([`9f5035b`](https://github.com/eyeonus/Trade-Dangerous/commit/9f5035ba18ee4e58bd84185c8e79c9e349a7bde8))

* Formatting fix ([`463b5ee`](https://github.com/eyeonus/Trade-Dangerous/commit/463b5ee6153737c620ef55c056f855bd4ea7170b))

* Oops ([`aff35b6`](https://github.com/eyeonus/Trade-Dangerous/commit/aff35b652051ef807b95c3d2c6e0e1b0f4fd43f5))

* Documenting tKe&#39;s changes for 6.17 ([`ed61b8a`](https://github.com/eyeonus/Trade-Dangerous/commit/ed61b8abc3ee42789c88067bdb45e9bdb2fb7544))

* Merged in tKe/tradedangerous/import-changes (pull request #122)

Import: Never overwrite prices with older data ([`8ab1c45`](https://github.com/eyeonus/Trade-Dangerous/commit/8ab1c4539d68554617beafd76287c9a3490c9c9f))

* Merged in tKe/tradedangerous/issue-145 (pull request #121)

Issue #145 - Implemented CreditParser ([`e0b92cf`](https://github.com/eyeonus/Trade-Dangerous/commit/e0b92cfa2f080a0fa222747e10b4e6d6b0348f86))

* Merged in tKe/tradedangerous/run-prune-fix (pull request #119)

Fix prune order for Run command ([`d262cf8`](https://github.com/eyeonus/Trade-Dangerous/commit/d262cf8cab13708cce83e563673a2be4dfbd041c))

* Resolves #211 Lousy formatting of local command ([`c56288e`](https://github.com/eyeonus/Trade-Dangerous/commit/c56288ee53286c15b37d978270129fd0f0167387))

* improved logging for import ([`e97452a`](https://github.com/eyeonus/Trade-Dangerous/commit/e97452ac7c70e5bd49daa09df0006c8de701f93d))

* only insert new data on import ([`0503c5f`](https://github.com/eyeonus/Trade-Dangerous/commit/0503c5ffa24a2331aa6950edf6871f241cdd9f4f))

* add --reset to import command ([`5b2e059`](https://github.com/eyeonus/Trade-Dangerous/commit/5b2e059bad9d13c174f39a00d15b2a289176bb61))

* Merged kfsone/tradedangerous into master ([`7cbb98a`](https://github.com/eyeonus/Trade-Dangerous/commit/7cbb98ac22ff2c51478cc1738de22e6b07b6b976))

* added CreditParser and switched appropriate arguments ([`be57302`](https://github.com/eyeonus/Trade-Dangerous/commit/be57302e3763e7f98e2478770ae7ea151856c06c))

* also fixed pruning being applied to initial origins

we have no way of choosing one origin over another at this point so there is no weighting to what we prune. ([`de489f4`](https://github.com/eyeonus/Trade-Dangerous/commit/de489f452af3c1837f723c242c112ebfa7fe4c58))

* fix prune order to ensure max-routes still applies ([`a4b1ec7`](https://github.com/eyeonus/Trade-Dangerous/commit/a4b1ec7b2557f560489f5df8162c4b4d50a7b879))

* Merged kfsone/tradedangerous into master ([`3fb59f6`](https://github.com/eyeonus/Trade-Dangerous/commit/3fb59f6f84370b9a006ae49444834f1aa00d362a))

* Merge remote-tracking branch &#39;upstream/master&#39; ([`be2af91`](https://github.com/eyeonus/Trade-Dangerous/commit/be2af91389d5b34350b45228f4f27b7c65223822))

* Merge remote-tracking branch &#39;upstream/master&#39; ([`e6a73d5`](https://github.com/eyeonus/Trade-Dangerous/commit/e6a73d59f91140347ee8983cba7973a47d7fcb7b))

* Systems ([`336a7fe`](https://github.com/eyeonus/Trade-Dangerous/commit/336a7fe64eee01e7595d5bea4e649412a5b6b736))

* Data ([`8202780`](https://github.com/eyeonus/Trade-Dangerous/commit/8202780a2b5101efbcf47e5d086c7d127d8f1d0f))

* Data, because I hadn&#39;t checked any in for hours! ([`4c171a0`](https://github.com/eyeonus/Trade-Dangerous/commit/4c171a0d7fea9f6978b2db2667e1e9a0f361c639))

* I think I&#39;ve flipped ([`f1abe92`](https://github.com/eyeonus/Trade-Dangerous/commit/f1abe926684ee3a9e1d59ede8a3894a5cf9a751c))

* For shits and giggles(*).

(* Because any time you see a commit that says &#39;for shits and giggles&#39; you should really, really be afraid) ([`83e1b04`](https://github.com/eyeonus/Trade-Dangerous/commit/83e1b044842379b7d6c199a766f35b70814322ab))

* Disallow --loop --direct because that would be silly ([`58f8cac`](https://github.com/eyeonus/Trade-Dangerous/commit/58f8cac5c2e94a900621c80a84b315019603d378))

* Data ([`08aa8d9`](https://github.com/eyeonus/Trade-Dangerous/commit/08aa8d95868e0fd5388a2fd8b74ab813dc911bac))

* Sort old data by distance when showing --near ([`12dba70`](https://github.com/eyeonus/Trade-Dangerous/commit/12dba709256b9a5b6347db9dfb21ea2f3cb917d5))

* Speed bump for loop optimizations ([`12785dd`](https://github.com/eyeonus/Trade-Dangerous/commit/12785dd81bf254ff9eed2c15e4627d85332c3553))

* Debugging fix ([`a984161`](https://github.com/eyeonus/Trade-Dangerous/commit/a984161afa156de0c6c50a17a4cc3a4982575fcf))

* tKE credit for loop ([`bea45b2`](https://github.com/eyeonus/Trade-Dangerous/commit/bea45b2fed824ce6742120f1da192cd4466929d1))

* Minor hosts to improve loop perf ([`616b3bd`](https://github.com/eyeonus/Trade-Dangerous/commit/616b3bd66263396e12e0e8c895cfc6de15984a60))

* Change default str() for Station ([`46ec99f`](https://github.com/eyeonus/Trade-Dangerous/commit/46ec99f8043c7e236a06cc4c1bd8d8d96c0a75c7))

* Merged in tKe/tradedangerous/run-improvements (pull request #116)

Destination-based pruning and loop option ([`154c952`](https://github.com/eyeonus/Trade-Dangerous/commit/154c9527e3823ab834e5f54c947193516daeed79))

* Merge remote-tracking branch &#39;upstream/master&#39; ([`efc6ef5`](https://github.com/eyeonus/Trade-Dangerous/commit/efc6ef5acd964ca2a3f297ee19f7d534d7cf69b0))

* Merged in bgol/tradedangerous/data (pull request #118)

data update ([`f3b504f`](https://github.com/eyeonus/Trade-Dangerous/commit/f3b504f140718bf79a3076adb1e323a1805a6c90))

* rebase remote ([`caad132`](https://github.com/eyeonus/Trade-Dangerous/commit/caad1327998e175248c3d4ee0253b130ae9b6db8))

* sorting after rebase ([`4dc6aba`](https://github.com/eyeonus/Trade-Dangerous/commit/4dc6aba37265d7b4f6890f6f2cfc5b425cb49a03))

* some data ([`8e5eae3`](https://github.com/eyeonus/Trade-Dangerous/commit/8e5eae3444abfd04ac16296e59e7a6f863540ed7))

* some data ([`3db6b3f`](https://github.com/eyeonus/Trade-Dangerous/commit/3db6b3f61dec48c2e945801a80ca7fa89abbc57f))

* More data ([`ff820f5`](https://github.com/eyeonus/Trade-Dangerous/commit/ff820f563bddf0dc1284a3fef9385fd116cbdd9e))

* Data ([`1b13534`](https://github.com/eyeonus/Trade-Dangerous/commit/1b1353462104115893f04b61c2c1fa56ac2f19d7))

* Added over 100 more systems ([`ff5db1b`](https://github.com/eyeonus/Trade-Dangerous/commit/ff5db1b779136ba6bc0c1d420f3324a97e4b55f4))

* Data ([`b3a1f79`](https://github.com/eyeonus/Trade-Dangerous/commit/b3a1f79bba0362f5c0d9b35a983b8fda1690269d))

* added --loop option ([`029dcd3`](https://github.com/eyeonus/Trade-Dangerous/commit/029dcd307e355e4465f67346fb6c17e42837d186))

* add pruning based on distance from any defined stopStations

if there isn&#39;t enough jumps to reach any of the destinations, there&#39;s no point in continuing with that route. ([`c277813`](https://github.com/eyeonus/Trade-Dangerous/commit/c2778135236d9c8546586fc25e6816f01cf42ea5))

* I assume this is what was meant here. ([`b19113d`](https://github.com/eyeonus/Trade-Dangerous/commit/b19113db8a207b5c0fccf63482ba67a81ea10dca))

* Merge remote-tracking branch &#39;upstream/master&#39; ([`3ee37c7`](https://github.com/eyeonus/Trade-Dangerous/commit/3ee37c782d1d5c8011c389a616af15c37a918f6c))

* Refresh .prices file when removing a station that had items listed ([`c81229e`](https://github.com/eyeonus/Trade-Dangerous/commit/c81229e81a6803e70aec6934de9ec90815b6f146))

* Maddavo&#39;s plugin &#39;corrections&#39; support ([`bdb24cb`](https://github.com/eyeonus/Trade-Dangerous/commit/bdb24cbff93526ac32f823e49bcf0bfb17b5255c))

* Tolerance for utf-8 decode errors ([`61b0298`](https://github.com/eyeonus/Trade-Dangerous/commit/61b0298a8a47d19d2fb6729e48a71e9f58630872))

* Slight restructure of maddavo plugin ([`571a7e0`](https://github.com/eyeonus/Trade-Dangerous/commit/571a7e0bac14c4c8ceec2be92b513a65b51e07fa))

* Make the upload file look more like an upload ([`6775cdd`](https://github.com/eyeonus/Trade-Dangerous/commit/6775cdd5cbf58bd9d7df6d53583ced111e3933da))

* Minor tweak ([`54a77e9`](https://github.com/eyeonus/Trade-Dangerous/commit/54a77e90f8535e71f68b1daa531fde387dbc84e0))

* New Yembo&#39;s Under Construction is now Unity ([`94853bf`](https://github.com/eyeonus/Trade-Dangerous/commit/94853bf5792ca3c3aa98ed9053379d0c9ba6e2ce))

* Presentation ([`d770e43`](https://github.com/eyeonus/Trade-Dangerous/commit/d770e432f47e44566d5102d24f57fb13a31790c3))

* Lots more data ([`2266915`](https://github.com/eyeonus/Trade-Dangerous/commit/2266915846c8707ef9d369617efa4f958c4457df))

* Merged kfsone/tradedangerous into master ([`c3400f2`](https://github.com/eyeonus/Trade-Dangerous/commit/c3400f2245e573908463bd8e88c0e87ccd0bc412))

* Keep it simple ([`0a3e92e`](https://github.com/eyeonus/Trade-Dangerous/commit/0a3e92e6f92a091bb3c8b446367530f1c00193a6))

* Presentation ([`17c17b4`](https://github.com/eyeonus/Trade-Dangerous/commit/17c17b489dcf29b444d02f57acc69786a162b042))

* Better presentation of &#39;DUMB&#39; ([`de25266`](https://github.com/eyeonus/Trade-Dangerous/commit/de25266a09fcf40e8e9bd8893145b9d3c866c527))

* Ignore zero prices ([`8e29bdc`](https://github.com/eyeonus/Trade-Dangerous/commit/8e29bdc4e1784b127df8b1429dd10e05bfdebcf0))

* Made item names case insensitive in .price files ([`43c1998`](https://github.com/eyeonus/Trade-Dangerous/commit/43c19980eea42074e522f16e43a5cb713c2f00cc))

* Merged kfsone/tradedangerous into master ([`8590e2a`](https://github.com/eyeonus/Trade-Dangerous/commit/8590e2aee0a7f557f205cad1e6e3d302536c1755))

* CHANGE log ([`b3031c8`](https://github.com/eyeonus/Trade-Dangerous/commit/b3031c8a50a0f76a75572a5ffef75f0071ce226a))

* Merge commit &#39;b7b159d58b0343c864930c9fe317256793ced305&#39;

* commit &#39;b7b159d58b0343c864930c9fe317256793ced305&#39;: (21 commits)
  Change log addendum
  CHANGE log
  AI Relics and Antiquities added
  Fix for attribute error when something was out of price range
  Fixed #210 confusing run error message
  price checker
  Fixes #209 Exception when you can&#39;t afford something
  Data cleanup
  Ignore anything with .txt in data
  I want the last line, not the first (test relict)
  max is a var
  Bash script for station and shipvendor inserts
  Fixed Pandemonium
  revert run change
  FLECHS correction
  Run and system changes
  Data updates
  v6.14.3 eddb v3 support
  Station stats
  Windows fix and better error handling for madupload
  ...

Conflicts:
	CHANGES.txt ([`44e0b9f`](https://github.com/eyeonus/Trade-Dangerous/commit/44e0b9f6cdc2f9227c65bd9b21fc7c88e8ef2c09))

* Change log addendum ([`b7b159d`](https://github.com/eyeonus/Trade-Dangerous/commit/b7b159d58b0343c864930c9fe317256793ced305))

* CHANGE log ([`e68f59e`](https://github.com/eyeonus/Trade-Dangerous/commit/e68f59ebf21b6c31b8ac021720d98b3509d421df))

* AI Relics and Antiquities added ([`49b8cd3`](https://github.com/eyeonus/Trade-Dangerous/commit/49b8cd37298f5730158f82cc1793d3a8af6b9036))

* Fix for attribute error when something was out of price range ([`5c043f4`](https://github.com/eyeonus/Trade-Dangerous/commit/5c043f46a7ef0dcccab44cc67c7285a87dbadb44))

* Fixed #210 confusing run error message ([`8f4a65a`](https://github.com/eyeonus/Trade-Dangerous/commit/8f4a65aa90ea3c3a2355b427ca1c718133dd747b))

* Merged kfsone/tradedangerous into master ([`72dc782`](https://github.com/eyeonus/Trade-Dangerous/commit/72dc782263003476a344a0734ba87b1eb181da5d))

* price checker ([`f685cd7`](https://github.com/eyeonus/Trade-Dangerous/commit/f685cd7172674312b725428fdc8c6a60117d6bd7))

* Fixes #209 Exception when you can&#39;t afford something ([`7331f1d`](https://github.com/eyeonus/Trade-Dangerous/commit/7331f1d29b84ae29f46ea92a280dbd77dcbe923d))

* Data cleanup ([`3be1eac`](https://github.com/eyeonus/Trade-Dangerous/commit/3be1eac0ddaf790d0c6f5b71c6e8d0b5295c6d9b))

* Ignore anything with .txt in data ([`3dd91a9`](https://github.com/eyeonus/Trade-Dangerous/commit/3dd91a95c1dd25541e949550c3322a17595fc2d3))

* Merged in bgol/tradedangerous/devel (pull request #115)

Bash script for station and shipvendor inserts ([`a9e2d2f`](https://github.com/eyeonus/Trade-Dangerous/commit/a9e2d2f36ae6b8728100fa8ea79101b20cb80ad0))

* I want the last line, not the first (test relict) ([`1db77c8`](https://github.com/eyeonus/Trade-Dangerous/commit/1db77c85598bf24ada8ffc1f47beac7d77a49bea))

* max is a var ([`c0a8f62`](https://github.com/eyeonus/Trade-Dangerous/commit/c0a8f624cef9e3823812c7ff896cf5b9230d6e33))

* Bash script for station and shipvendor inserts ([`a021033`](https://github.com/eyeonus/Trade-Dangerous/commit/a0210330d9eddfc3b581adcf6a36a61b7dc227e1))

* Merged kfsone/tradedangerous into master ([`862b283`](https://github.com/eyeonus/Trade-Dangerous/commit/862b283dec1da0ce13b7b609b73e899987f4261a))

* Merged in maddavo/tradedangerous (pull request #114)

system update ([`be188a4`](https://github.com/eyeonus/Trade-Dangerous/commit/be188a49ff8c79066bab9f4b928f3ff6864a571d))

* Fixed Pandemonium

FD must have fixed a typo ([`690a2a1`](https://github.com/eyeonus/Trade-Dangerous/commit/690a2a1154495de4290daaa18c0e223d8607d6d7))

* revert run change ([`9889ada`](https://github.com/eyeonus/Trade-Dangerous/commit/9889adaf2597420ca7ed936bae6c013b74f464e5))

* FLECHS correction ([`7107642`](https://github.com/eyeonus/Trade-Dangerous/commit/710764273ab97580088228d9d419dd46a39d6574))

* Run and system changes

Run works when --from station doesn&#39;t match pad size criteria.
FLECHS system doesn&#39;t exist anymore (renamed to IC... something which is
already in list). ([`cde5f32`](https://github.com/eyeonus/Trade-Dangerous/commit/cde5f320b6d59ace6f713a8fba7ec5acd5a009bd))

* Merged kfsone/tradedangerous into master ([`a5d0dba`](https://github.com/eyeonus/Trade-Dangerous/commit/a5d0dbaa1ad5e4a7eb3199c6c6dca00093fb6da0))

* Data updates ([`ef55042`](https://github.com/eyeonus/Trade-Dangerous/commit/ef550424b99c6c0f6134b98e96fa16129da5ebea))

* v6.14.3 eddb v3 support ([`99d9015`](https://github.com/eyeonus/Trade-Dangerous/commit/99d9015f027a886e159c79180a14f6c5e7f41fda))

* Station stats ([`d08eb86`](https://github.com/eyeonus/Trade-Dangerous/commit/d08eb86647e1cebcb8fd35b05e7d68e397d0268d))

* Windows fix and better error handling for madupload ([`638600f`](https://github.com/eyeonus/Trade-Dangerous/commit/638600fb8fd0645f0a523aeb1891e65839722e17))

* v6.14.3 --towards should be much better behaved ([`8bc3a72`](https://github.com/eyeonus/Trade-Dangerous/commit/8bc3a72680cceb5b44189099c5e75bdd7a486bb7))

* Improvement to how we handle --toward ([`6dbbcde`](https://github.com/eyeonus/Trade-Dangerous/commit/6dbbcdebffcbf81384c0b1d6415d35abc3ca4142))

* Don&#39;t spam the user when no the last hop is not profitable without --from ([`145caad`](https://github.com/eyeonus/Trade-Dangerous/commit/145caade1f41c176ba3dc39180915544aede209f))

* Merged kfsone/tradedangerous into master ([`2d10728`](https://github.com/eyeonus/Trade-Dangerous/commit/2d10728eda7bc6188c37d2dfe2722999364d985c))

* Merged kfsone/tradedangerous into master ([`1522ef1`](https://github.com/eyeonus/Trade-Dangerous/commit/1522ef1645629588cef2426dbdf95a09dde42682))

* Correction ([`8a8e2d6`](https://github.com/eyeonus/Trade-Dangerous/commit/8a8e2d6cb51fc124c5bf943039514f996450f6f3))

* removed 4a5040 ([`b9c6ef2`](https://github.com/eyeonus/Trade-Dangerous/commit/b9c6ef2b3a4378b01325f71a6b4a791a8931e4cc))

* Fixed no details ([`5a60712`](https://github.com/eyeonus/Trade-Dangerous/commit/5a607123f302402c9e0e54780bed9ce3f75f09e2))

* Bit of cleanup and tuning ([`2633c33`](https://github.com/eyeonus/Trade-Dangerous/commit/2633c33d5957323e82f063313e84fd2a42400ad0))

* UTF8 characters in cache.py ([`a09afd9`](https://github.com/eyeonus/Trade-Dangerous/commit/a09afd944adbf90e48a7283e70c01b7d27f2d1ff))

* 6.14.2 ([`759ef9b`](https://github.com/eyeonus/Trade-Dangerous/commit/759ef9b5592424f701ca37a929976af0672ea5a1))

* Data ([`702b062`](https://github.com/eyeonus/Trade-Dangerous/commit/702b0628dae46d2aebef1fda8f0d372fd7adc9d7))

* Fixed minor bug ([`05ac79e`](https://github.com/eyeonus/Trade-Dangerous/commit/05ac79ecdd28128edad47b3163a4a46608e85706))

* Do --max-routes after --prune ([`368655c`](https://github.com/eyeonus/Trade-Dangerous/commit/368655c0106b3cd804eb276b9629d39d09df1da6))

* Fixed --max-routes ([`c1fec63`](https://github.com/eyeonus/Trade-Dangerous/commit/c1fec63d9d2fbbe9ee279f53b650906616d6f426))

* Made --prune stuff work more sensibly ([`381db3b`](https://github.com/eyeonus/Trade-Dangerous/commit/381db3b56c66bc3d94e3c9b19284d6752bede857))

* Fixed why shorter routes don&#39;t win out more often ([`20423ea`](https://github.com/eyeonus/Trade-Dangerous/commit/20423ea870d7340743e39baf228d5d412f76cdcf))

* Stations ([`b9b9352`](https://github.com/eyeonus/Trade-Dangerous/commit/b9b9352f9eb1fd8b8fc80af23b91402868dd6297))

* 25 more systems ([`c0ae211`](https://github.com/eyeonus/Trade-Dangerous/commit/c0ae211657fa0e4521faf991a0999653a4150c69))

* More systems ([`8e66def`](https://github.com/eyeonus/Trade-Dangerous/commit/8e66def03dd6ddcb434b21b3d04f515a9a55a876))

* More station data in run output ([`6700e7d`](https://github.com/eyeonus/Trade-Dangerous/commit/6700e7d829c5017af779920f8f7de7ef96f2192b))

* Data ([`cf9d50f`](https://github.com/eyeonus/Trade-Dangerous/commit/cf9d50f28471361205f4a74aeadac826b607b52b))

* Data ([`601f183`](https://github.com/eyeonus/Trade-Dangerous/commit/601f1836e4e141ee23e78bcf0db46b7771ad2b1d))

* 40 more systems ([`4db9eb1`](https://github.com/eyeonus/Trade-Dangerous/commit/4db9eb1b6c0e593bdb405eaa5d501365b0af5206))

* Updated data ([`c542aa4`](https://github.com/eyeonus/Trade-Dangerous/commit/c542aa46b90ec2d939c9b8ab97ee164dfcc49bcb))

* Imported lots of station attributes from eddb to populate new fields ([`72cd90c`](https://github.com/eyeonus/Trade-Dangerous/commit/72cd90c8f03794c3effe9548d871f9aec4b8da1b))

* Added tool to import station properties from eddb ([`4014897`](https://github.com/eyeonus/Trade-Dangerous/commit/4014897eadbd6fed4a69e71abc5abcd4d24410b5))

* Derp defense ([`b17a2f6`](https://github.com/eyeonus/Trade-Dangerous/commit/b17a2f64d8672b6e8c382ee1eff9702567373276))

* Reworked eddb api ([`89cf30d`](https://github.com/eyeonus/Trade-Dangerous/commit/89cf30ddd99b2c2f682b130119d9a24fb0c9318d))

* 6.14.0 Added outfitting, readme, refuel and repair properties to stations ([`f94d1f8`](https://github.com/eyeonus/Trade-Dangerous/commit/f94d1f8f40340626876c2b70f5be58bf181d18df))

* Removed tkinter dependency in maddavo&#39;s plugin ([`4abbfc7`](https://github.com/eyeonus/Trade-Dangerous/commit/4abbfc70603c986460509d9d521998f35b5f53bb))

* 16.3.4 --mgpt ([`d4579da`](https://github.com/eyeonus/Trade-Dangerous/commit/d4579da5b80611520316fe72d0848037dd4c2d19))

* Merged in WombatFromHell/tradedangerous (pull request #107)

Added max-gain-per-ton to the Run command ([`b7b372e`](https://github.com/eyeonus/Trade-Dangerous/commit/b7b372ed2d789719626e4b3e80ba7c7d725f4167))

* Merged kfsone/tradedangerous into master ([`3db5988`](https://github.com/eyeonus/Trade-Dangerous/commit/3db59886d867b7185d414d32f6ae3e29cfbbbd25))

* CHANGE Log ([`087d6a8`](https://github.com/eyeonus/Trade-Dangerous/commit/087d6a86237412fd200db3d7f19a4bc4165ffd2f))

* Resolves #203 1.2.03 ship prices ([`605f2b2`](https://github.com/eyeonus/Trade-Dangerous/commit/605f2b2370777bcb4b00a5caea37e42f0118a7d0))

* Merged in orphu/tradedangerous/updates (pull request #113)

A few ship vendor updates. ([`695e3f7`](https://github.com/eyeonus/Trade-Dangerous/commit/695e3f7da7b413934dfeb38d5b292ea979c5bc03))

* try to defer the &#39;requests&#39; dependency as late as possible ([`1b29f92`](https://github.com/eyeonus/Trade-Dangerous/commit/1b29f922ed3519ac238f66fc2d4f2d9f4ad11c39))

* Require 3.4.2 not 3.4.1 ([`b465dda`](https://github.com/eyeonus/Trade-Dangerous/commit/b465ddae58223045f2a312a7203c34e809ba8c8a))

* A few ship vendor updates. ([`d4b25e8`](https://github.com/eyeonus/Trade-Dangerous/commit/d4b25e870fda7b47c462b085c26e066f7bb5745f))

* Merge branch &#39;master&#39; into updates

Conflicts:
	data/ShipVendor.csv ([`87c8164`](https://github.com/eyeonus/Trade-Dangerous/commit/87c8164b57b5d924dbc261f38746c568a7c9dd88))

* Merged kfsone/tradedangerous into master ([`df6abf1`](https://github.com/eyeonus/Trade-Dangerous/commit/df6abf1ffce82f97b547df46339cd0ec5bbb965b))

* Final batch of systems for tonight ([`b9f544f`](https://github.com/eyeonus/Trade-Dangerous/commit/b9f544ff1dcd2eb414f9820f2dc3fc420a07eb28))

* More systems ([`4774ba8`](https://github.com/eyeonus/Trade-Dangerous/commit/4774ba87a2ab27c9c26465cd6e829c86524bf976))

* More systems ([`012c8a1`](https://github.com/eyeonus/Trade-Dangerous/commit/012c8a1b894f56d17d12c2c4c77f7322aab16aa5))

* More systems ([`ef6fa4b`](https://github.com/eyeonus/Trade-Dangerous/commit/ef6fa4b2762fa61899e5fd614f567f013078217f))

* Improved logging of edsc module ([`4e76e18`](https://github.com/eyeonus/Trade-Dangerous/commit/4e76e181b2e7ba36da77ca151f898503020aa364))

* 10 more systems ([`b1b607d`](https://github.com/eyeonus/Trade-Dangerous/commit/b1b607d5dd9f5600489d2ea52d335a0ec5a10cfa))

* More derp tweaks and station cleanup ([`cff412c`](https://github.com/eyeonus/Trade-Dangerous/commit/cff412c08a30e232a9b0f56f2089c86430cb16a3))

* Data sync ([`d82dcd4`](https://github.com/eyeonus/Trade-Dangerous/commit/d82dcd49d9f03bb98b3524efc90c4645894b68a4))

* CHANGE log ([`eb75e98`](https://github.com/eyeonus/Trade-Dangerous/commit/eb75e987aae4f17c0dd886c73b61b32f793696ed))

* Derp cleanup ([`d5211bc`](https://github.com/eyeonus/Trade-Dangerous/commit/d5211bce6facdcde6ff951aff8b114160eebaf73))

* Station cleanup ([`88f4345`](https://github.com/eyeonus/Trade-Dangerous/commit/88f4345a4444ddbccbf6a3c2f677adf25eca9a68))

* OCR Derp fixes ([`024cf3b`](https://github.com/eyeonus/Trade-Dangerous/commit/024cf3b037c839d21548c88504d8af0f5d14a61d))

* Fixed application of station corrections to maddavo&#39;s plugin ([`60210de`](https://github.com/eyeonus/Trade-Dangerous/commit/60210de744b24a42e4ddc9541189132d12fb2b99))

* Description of --pick ([`77a73fc`](https://github.com/eyeonus/Trade-Dangerous/commit/77a73fc0778b112291b879ad88cafb03aede6a11))

* Added 103 systems ([`080481e`](https://github.com/eyeonus/Trade-Dangerous/commit/080481e84bb2d22e4237787faa258a57f4dfb14a))

* fixes for edscupdate ([`8a9b948`](https://github.com/eyeonus/Trade-Dangerous/commit/8a9b94895e32066f1844845122049c76214b3592))

* Fixed updateLocalSystem ([`e57d2cc`](https://github.com/eyeonus/Trade-Dangerous/commit/e57d2ccc4a5889b4ab48a674c2940d34a9eca541))

* Resolves #200 New ships for 1.2 ([`0d35374`](https://github.com/eyeonus/Trade-Dangerous/commit/0d353744d1e5daa437849d5e20ae1adfff587651))

* Case matters ([`50448aa`](https://github.com/eyeonus/Trade-Dangerous/commit/50448aa1b6a0d1ebdbf3c4794bb8853710e57bb1))

* Fixed broken --blackmarket and --trading in &#39;local&#39; ([`32c63b0`](https://github.com/eyeonus/Trade-Dangerous/commit/32c63b08c9848cf6ab60262ca2c7c9785dc284f6))

* Station.isTrading is supposed to be a property ([`72e207a`](https://github.com/eyeonus/Trade-Dangerous/commit/72e207abd1e5bc850f0b03309f1135c4493dd015))

* Merged kfsone/tradedangerous into master ([`cbe7d4b`](https://github.com/eyeonus/Trade-Dangerous/commit/cbe7d4b0f627ff8650c4463ba9644191323e679a))

* 112 new systems ([`35c0ebb`](https://github.com/eyeonus/Trade-Dangerous/commit/35c0ebb86d2fe7074a3e0d906b21e793e2f4863c))

* Another bad system ([`9ab1ce0`](https://github.com/eyeonus/Trade-Dangerous/commit/9ab1ce0da308fa9b43befe698cd748fb82f9a372))

* Live long and prosper ([`3cc78ee`](https://github.com/eyeonus/Trade-Dangerous/commit/3cc78eedc4b95bbbd1e48aa9cc2264f38434ea81))

* --opt now accepts comma-separated options, e.g. --opt=systems,stations ([`7a7bd17`](https://github.com/eyeonus/Trade-Dangerous/commit/7a7bd1777585e70453bfce15d62cbee9f38d6fc2))

* Fixes #199 Added Painite ([`2461b71`](https://github.com/eyeonus/Trade-Dangerous/commit/2461b7150f2e07da40fc5a6b7724f449f6a7426a))

* Merged kfsone/tradedangerous into master ([`f5cd784`](https://github.com/eyeonus/Trade-Dangerous/commit/f5cd784e1d004111cacd24eb713e23ccf7c39942))

* Fixes #197 pad size not working with run and --start/--end ([`8ba08b9`](https://github.com/eyeonus/Trade-Dangerous/commit/8ba08b9de5bfda86244a923a1912b3d6b5564cd0))

* Merged kfsone/tradedangerous into master ([`7282d9e`](https://github.com/eyeonus/Trade-Dangerous/commit/7282d9ecf46eea23cc23f0366e40d4831ae04587))

* Merged kfsone/tradedangerous into master ([`be1c45a`](https://github.com/eyeonus/Trade-Dangerous/commit/be1c45a5a617dc92b1d3f6b87e5c5a6bdd6c6c18))

* CHANGES.txt ([`b379508`](https://github.com/eyeonus/Trade-Dangerous/commit/b379508ae515ab5468290f6826908ef01642b324))

* Fixes #195 max_len doesn&#39;t like empty iterator ([`a587967`](https://github.com/eyeonus/Trade-Dangerous/commit/a58796785b3103e12f21c29204350b63065e5a5b))

* ShipVendors ([`1b55106`](https://github.com/eyeonus/Trade-Dangerous/commit/1b55106a44381fbf0231db696525764b455ff531))

* Resolving #196 &#39;shipvendor&#39; command now defaults to listing ships at a station ([`086a52b`](https://github.com/eyeonus/Trade-Dangerous/commit/086a52b29fcb79a9e2deb0f2bb7193e0928ad38a))

* Cosmetic cleanup ([`f6f9cba`](https://github.com/eyeonus/Trade-Dangerous/commit/f6f9cba66188ba21a29984749f1e8b4645bfbf4b))

* Finessing of the maddavo plugin ([`5e88222`](https://github.com/eyeonus/Trade-Dangerous/commit/5e88222b0f613213d186290c69d5678bb888affd))

* Handle bad/float lsFromStar values from maddavo ([`5e2206e`](https://github.com/eyeonus/Trade-Dangerous/commit/5e2206e05872cb29a9a33cc831abdaa0082e9e31))

* Added TradeEnv.WARN ([`a66b670`](https://github.com/eyeonus/Trade-Dangerous/commit/a66b6702e0f3d9198cc84ad94fe7efaff600cfe1))

* Merged in DRy411S/tradedangerous-dry411s-fork (pull request #112)

Resubmit previously submitted ships + some more following change of file format ([`354d940`](https://github.com/eyeonus/Trade-Dangerous/commit/354d94045c6f72039ede3bb88af72f8501156156))

* Don&#39;t prevent the user from setting maxGPT to a very high number ([`a0c028d`](https://github.com/eyeonus/Trade-Dangerous/commit/a0c028d61a7d0d0abc46923aed7d253cd9ff1a7f))

* Resubmit previously submitted ships + some more following change of file format

Signed-off-by: DRY411S &lt;dsryalls@gmail.com&gt; ([`9541de0`](https://github.com/eyeonus/Trade-Dangerous/commit/9541de095f10d65d6827ae3ddde0448a2d79a2de))

* Merged kfsone/tradedangerous into master ([`8eefa29`](https://github.com/eyeonus/Trade-Dangerous/commit/8eefa29179e8a92f1b745d0a0d259713bee6282f))

* Merged kfsone/tradedangerous into master ([`635e407`](https://github.com/eyeonus/Trade-Dangerous/commit/635e407414a1eefcfbc5e8a5bb15d61fe39eba88))

* Fixed the CHANGES file ([`b712e28`](https://github.com/eyeonus/Trade-Dangerous/commit/b712e2885ed86a24e0da2c3f92804dbe038d3e3b))

* Correct version number in CHANGES.txt ([`59b64b4`](https://github.com/eyeonus/Trade-Dangerous/commit/59b64b4354d7d06da1ca1e43ee1731686a5a3226))

* All kinds of improvements to feedback of &#34;run&#34; command with bad inputs ([`c013d81`](https://github.com/eyeonus/Trade-Dangerous/commit/c013d81155849471e237f57e991f9742a1e9c3e7))

* Fix errant assignment of populated list in local command ([`3dfc41d`](https://github.com/eyeonus/Trade-Dangerous/commit/3dfc41d44108cccaffa6ca2dec13a10b4fbe5a89))

* Raise NoHopsError when getBestHops is asked to find routes with no reachable destinations ([`ea4f74f`](https://github.com/eyeonus/Trade-Dangerous/commit/ea4f74f31d15190fef1b5dc21b2ee9b954362202))

* Perf tweaks to getBestHops ([`786a7c7`](https://github.com/eyeonus/Trade-Dangerous/commit/786a7c75379e21c0b793561c39d1007f356a4e0b))

* Performance tweak: yield destinations rather than building a destination list ([`d0d958f`](https://github.com/eyeonus/Trade-Dangerous/commit/d0d958f99b08b5e9abcf1a54c3913d84fad646f7))

* Merged kfsone/tradedangerous into master ([`9bb0f81`](https://github.com/eyeonus/Trade-Dangerous/commit/9bb0f8195d6644105814b9ad82c8dc6cf7311330))

* Improved help of import command ([`d506bf0`](https://github.com/eyeonus/Trade-Dangerous/commit/d506bf036891e53f36dd264a19eeb3f8f8576fb7))

* Better explanation of not finding a trade route ([`2816783`](https://github.com/eyeonus/Trade-Dangerous/commit/2816783f7bc02a67d284df1ebd9bed7bb529e8d1))

* Made it easier to access first/last station properties of a Route object ([`c6f43c6`](https://github.com/eyeonus/Trade-Dangerous/commit/c6f43c64434d3707c5c8199a133c5ba0f0731680))

* Added --stations, --trading, --blackmarket and --shipyard to local sub-command ([`7158256`](https://github.com/eyeonus/Trade-Dangerous/commit/71582569809511bdce5bdff9316cdf8e8adb0429))

* Added &#39;-csvs&#39; option to maddavo&#39;s plugin to import all the csvs at once ([`12c1877`](https://github.com/eyeonus/Trade-Dangerous/commit/12c1877dddc35528e9e5b442cb299f1f2387e237))

* Improved &#39;market&#39; command, --buy --sell is default behavior ([`7d66fbf`](https://github.com/eyeonus/Trade-Dangerous/commit/7d66fbfa2fe6385b95d8ad06f71c3f3b662d9389))

* Resolving #194 Added --opt=shipvendors to Maddavo&#39;s plugin ([`ac01fdd`](https://github.com/eyeonus/Trade-Dangerous/commit/ac01fdddf8e5e3a24c485b3b5782b43cc99bacff))

* Added &#39;modified&#39; column to ShipVendor table ([`4475660`](https://github.com/eyeonus/Trade-Dangerous/commit/4475660fe31ac264cc7f336f4380c936bc1355a3))

* Data update ([`d55a6ad`](https://github.com/eyeonus/Trade-Dangerous/commit/d55a6ad033d85d7c64eb56da7d62d3c09242d4e9))

* Merged kfsone/tradedangerous into master ([`8cbbb8c`](https://github.com/eyeonus/Trade-Dangerous/commit/8cbbb8c35ad8e7e913a5c51fe1572939f2e7c3fc))

* Merged kfsone/tradedangerous into master ([`e7190f7`](https://github.com/eyeonus/Trade-Dangerous/commit/e7190f75ad8c417c9d68e468a482630797212288))

* CHANGE log ([`19ec53b`](https://github.com/eyeonus/Trade-Dangerous/commit/19ec53b0d047ee8886bae98d3213795caf7d700c))

* Fixed #193 run ignoring --ls-max ([`7a7c269`](https://github.com/eyeonus/Trade-Dangerous/commit/7a7c269e71b346a0ebaa98f3b2d10bccd0a131fb))

* Added 175 new systems ([`20c4bc4`](https://github.com/eyeonus/Trade-Dangerous/commit/20c4bc42ebd38aa4357741a7bb263cdacc821abf))

* Bad system ([`6baadf1`](https://github.com/eyeonus/Trade-Dangerous/commit/6baadf10db88c212ccc7a7435ed258178f629728))

* Added --add to edscupdate.py to add systems to local db automatically ([`84d823a`](https://github.com/eyeonus/Trade-Dangerous/commit/84d823acda1ce8f111ac63d53c05e11803b0aa0a))

* Merged in DRy411S/tradedangerous (pull request #110)

Additional shipyard data, including ALIGNAK data previously submitted via the issue tracker ([`514d5bf`](https://github.com/eyeonus/Trade-Dangerous/commit/514d5bf4b8d9fcb0e1effa2faf792365be20cb88))

* Merged kfsone/tradedangerous into master ([`9c51998`](https://github.com/eyeonus/Trade-Dangerous/commit/9c519988ddf80ee980be462f71ee951e320454a7))

* Merged kfsone/tradedangerous into master ([`da390f2`](https://github.com/eyeonus/Trade-Dangerous/commit/da390f2e2eeb52f0ae974ead2713029799f3920e))

* Additional shipyard data, including ALIGNAK data previously submitted via the issue tracker


Signed-off-by: rcthelp &lt;dsryalls@gmail.com&gt; ([`f29ec2b`](https://github.com/eyeonus/Trade-Dangerous/commit/f29ec2b6f1d0fe77adbbfde8ec76c199875925f5))

* Fixed typo in README ([`f0024cb`](https://github.com/eyeonus/Trade-Dangerous/commit/f0024cb8b8464427b18bc6c3ba7a4b6e592b3436))

* Merged kfsone/tradedangerous into master ([`a7d6cfc`](https://github.com/eyeonus/Trade-Dangerous/commit/a7d6cfcc45d948ec5e6aec90e3f7af150888f06d))

* Maddavo plugin now supports system and station deletes ([`76fc3b8`](https://github.com/eyeonus/Trade-Dangerous/commit/76fc3b828afd420b04830af564d8afb28436c9b9))

* Added removeLocalSystem and removeLocalStation to TradeDB ([`bceffb6`](https://github.com/eyeonus/Trade-Dangerous/commit/bceffb600aef2a63fd19d02eadb1f6a9f21e462f))

* Added support for file:/// urls to CSVStream ([`2805428`](https://github.com/eyeonus/Trade-Dangerous/commit/28054285f7575031b2cfd12949117dfe14d1098b))

* Fixes #191 &#39;set&#39; does not support indexing ([`d0f3036`](https://github.com/eyeonus/Trade-Dangerous/commit/d0f30363248dd90f33e1621ac675a00c47670f27))

* Merged kfsone/tradedangerous into master ([`5c6dca8`](https://github.com/eyeonus/Trade-Dangerous/commit/5c6dca856c04aa8c9b37e6a8d0024f87d994b36b))

* Merged kfsone/tradedangerous into master ([`075b39d`](https://github.com/eyeonus/Trade-Dangerous/commit/075b39d92d573c91878a513b414531cfb25506d7))

* ShipVendors from Dry411s ([`cf43255`](https://github.com/eyeonus/Trade-Dangerous/commit/cf43255ee797d4bfce5e84807c0668cc0c434399))

* local output cleanup ([`bb207e0`](https://github.com/eyeonus/Trade-Dangerous/commit/bb207e08302a8a3894739d27dbc48ed421a0bafa))

* Compact the local output when showing stations ([`6ba49a4`](https://github.com/eyeonus/Trade-Dangerous/commit/6ba49a43f2c043422977fc4bd55747f97d0e3e84))

* Fixes #190 station -r wasn&#39;t refreshing the station.csv file ([`6463527`](https://github.com/eyeonus/Trade-Dangerous/commit/646352756edc9b2e340a0af1132c6527a8910fe7))

* Fixes #188 Allow multiple ships per &#39;shipvendor&#39; command ([`8897893`](https://github.com/eyeonus/Trade-Dangerous/commit/88978930ed6dc3b2b28df49c79256324b9db4535))

* Fixes #185 Clean up of presentation of some common &#39;run&#39; command errors ([`9a5831c`](https://github.com/eyeonus/Trade-Dangerous/commit/9a5831cd82a526004e094ab1d9876ccf988f5cf0))

* Merged kfsone/tradedangerous into master ([`212adfd`](https://github.com/eyeonus/Trade-Dangerous/commit/212adfdfb5d792c83a1e99f25e43cd5e9cb747a3))

* Fix for updateLocalSystem using x, y, z instead of pos_x, pos_y, pos_z for coordinates ([`0ba7b17`](https://github.com/eyeonus/Trade-Dangerous/commit/0ba7b170441ab69840348cc2668ca3b15bff51c7))

* Merge branch &#39;master&#39; into updates

Conflicts:
	data/ShipVendor.csv ([`77b6d63`](https://github.com/eyeonus/Trade-Dangerous/commit/77b6d6378f866561ceb87f30fdbcc053867be21e))

* Merged kfsone/tradedangerous into master ([`ebe80f0`](https://github.com/eyeonus/Trade-Dangerous/commit/ebe80f06d4e54fa7b59ce2716e35528eda1b03c5))

* Ship vendor info. ([`3ad280d`](https://github.com/eyeonus/Trade-Dangerous/commit/3ad280d8016d5181457ecda94aa12fb3cbfa59d9))

* Merged kfsone/tradedangerous into master ([`581c01c`](https://github.com/eyeonus/Trade-Dangerous/commit/581c01cc3e54e104048dc8f065ba5f2ba266596d))

* Merged kfsone/tradedangerous into master ([`4840c15`](https://github.com/eyeonus/Trade-Dangerous/commit/4840c15cf86af41f610b4e3798c47490b795d058))

* Fixes #184 duplicate rows in buy command ([`bdb1ba8`](https://github.com/eyeonus/Trade-Dangerous/commit/bdb1ba8efb1170beb99aebec22737f09be4af61d))

* Merged kfsone/tradedangerous into master ([`615d071`](https://github.com/eyeonus/Trade-Dangerous/commit/615d071e6c171f1f28544b5d1a288f20f2847c6c))

* Remove problem system ([`2e08047`](https://github.com/eyeonus/Trade-Dangerous/commit/2e08047580d9a2b5e3a179614c88918718794c0e))

* Fixed run command/via ([`96032be`](https://github.com/eyeonus/Trade-Dangerous/commit/96032befd6ad40cd4d1ef366f8444a5cb76e4718))

* Merged kfsone/tradedangerous into master ([`e074787`](https://github.com/eyeonus/Trade-Dangerous/commit/e0747874ac7a450adefa765877eba289f2cc7ca3))

* Merged kfsone/tradedangerous into master ([`7a51ddc`](https://github.com/eyeonus/Trade-Dangerous/commit/7a51ddc3add0b147f3f0f0b4e53fc42b7e50ad7b))

* Removed Wh Ieelock ([`9d7004b`](https://github.com/eyeonus/Trade-Dangerous/commit/9d7004b1cb3c4661f007c4529468ef2068898095))

* Merged in maddavo/tradedangerous (pull request #109)

Fixed DITIBI coords ([`8346f58`](https://github.com/eyeonus/Trade-Dangerous/commit/8346f58616a18476df633fc0476d65b691d06e75))

* Fixed sorted in many/one-shot mode ([`5060617`](https://github.com/eyeonus/Trade-Dangerous/commit/50606175d75feaf13ac006478afe035d24d4d491))

* Fixed DITIBI coords ([`a8991d8`](https://github.com/eyeonus/Trade-Dangerous/commit/a8991d8d41ac19c2f3d489b54a8523e7d1b0f89d))

* Merged kfsone/tradedangerous into master ([`6a256ff`](https://github.com/eyeonus/Trade-Dangerous/commit/6a256ff7cbb6b8de403b98b712aa81b15350c511))

* Merged kfsone/tradedangerous into master ([`ce2a258`](https://github.com/eyeonus/Trade-Dangerous/commit/ce2a25893e117490c87fa6dd814d652278a90492))

* Merged in maddavo/tradedangerous (pull request #108)

System addition - DITIBI ([`09c5df8`](https://github.com/eyeonus/Trade-Dangerous/commit/09c5df8eb873e58d82cf8466667e2de5e48605ce))

* Data ([`50f3747`](https://github.com/eyeonus/Trade-Dangerous/commit/50f3747ddfb392eb0a1df7e4b3ec5ad9afb8f228))

* Fixues #104 v6.12.2 Added &#34;--direct&#34; to &#34;run&#34; command ([`5cb062b`](https://github.com/eyeonus/Trade-Dangerous/commit/5cb062b4dd9c9b163937b8308bcdd2069a525357))

* Fixed README/CHANGES ([`42f9f45`](https://github.com/eyeonus/Trade-Dangerous/commit/42f9f45ec17ce2fda9a931ef6e872cfd59dd1992))

* Merged kfsone/tradedangerous into master ([`b7ff8d0`](https://github.com/eyeonus/Trade-Dangerous/commit/b7ff8d055b112c53f5472ebd93ad93bc36c41703))

* Fixed CHANGES.txt ([`545120b`](https://github.com/eyeonus/Trade-Dangerous/commit/545120ba1483b6f9eeda0306af1b8e9068e3e5a4))

* &#39;buy&#39; command now accepts multiple item names ([`d14c55e`](https://github.com/eyeonus/Trade-Dangerous/commit/d14c55e5983d092a088b2edd869d3f791e2d7ed5))

* Missing 0 in cutoff for switching to ly for stnls ([`017698b`](https://github.com/eyeonus/Trade-Dangerous/commit/017698b163642131b96813c9d4d9bfc464c79df4))

* Re-inserting DITIBI - it was deleted somewhere along the line. ([`73ac4a9`](https://github.com/eyeonus/Trade-Dangerous/commit/73ac4a9878a5a72e42506654f214ddc2421ac287))

* Merged kfsone/tradedangerous into master ([`cda872d`](https://github.com/eyeonus/Trade-Dangerous/commit/cda872d775ab7458c45ca0579846b4fc450d1bf7))

* Code cleanup ([`70f6cae`](https://github.com/eyeonus/Trade-Dangerous/commit/70f6cae7ad05de85dd6ab417282b0237e83262ca))

* More decimal places for the low-Ks ([`33d77f5`](https://github.com/eyeonus/Trade-Dangerous/commit/33d77f52c49237c3ff074f9e48e29dc536e17a94))

* Vary the representation of distanceToLs ([`c39f389`](https://github.com/eyeonus/Trade-Dangerous/commit/c39f38994981b7105d6290f2c14b073b46801e84))

* Less aggressive jump to lightspeed ([`3598391`](https://github.com/eyeonus/Trade-Dangerous/commit/3598391030a7dc68226f08ce31b363505fca69a1))

* Fixes #183 PluginError not defined (its PluginException) ([`e145cd2`](https://github.com/eyeonus/Trade-Dangerous/commit/e145cd278ddb6378b358a4115a7fd13ed65dd1c6))

* Display of data age in update command ([`2a213ea`](https://github.com/eyeonus/Trade-Dangerous/commit/2a213ea3281dd03f55bf98839f5e2d08c7602ffb))

* Merged kfsone/tradedangerous into master ([`5d387f8`](https://github.com/eyeonus/Trade-Dangerous/commit/5d387f8cdbe358faefe53a28857dcd061b219d6e))

* Improvements to the update ui ([`fd635ae`](https://github.com/eyeonus/Trade-Dangerous/commit/fd635ae96eab40f4f6fc91e0b0804236d0fb572a))

* Better feedback from local station adjustments during import ([`c733e19`](https://github.com/eyeonus/Trade-Dangerous/commit/c733e199e20bf8e3afe8c86ac88b77678d179720))

* Updated station data ([`dd01ab5`](https://github.com/eyeonus/Trade-Dangerous/commit/dd01ab545d386ab0ec357a704c8eb7b13ae1de03))

* Merged kfsone/tradedangerous into master ([`b2cea65`](https://github.com/eyeonus/Trade-Dangerous/commit/b2cea65b0ac45242024d2242ec92cad172fcc649))

* Fix for --towards ([`88fd4d5`](https://github.com/eyeonus/Trade-Dangerous/commit/88fd4d520d215bfdb47f33d52a6e0980218b2917))

* Data glut ([`bd01d09`](https://github.com/eyeonus/Trade-Dangerous/commit/bd01d09628a15f33c1b4df13bcbbaf64bb49ba3f))

* Fixed a typo ([`702f0d9`](https://github.com/eyeonus/Trade-Dangerous/commit/702f0d94d783692138d4afb35044c79f2afc4beb))

* Merged kfsone/tradedangerous into master ([`78096c4`](https://github.com/eyeonus/Trade-Dangerous/commit/78096c4ea76a0bc01bfa332d73c60218095d1e1b))

* Big glut of systems ([`5f5b45e`](https://github.com/eyeonus/Trade-Dangerous/commit/5f5b45e615b3f0e5fb584474ee6f24dc38d2b088))

* Removed environ shenanigans ([`6c60659`](https://github.com/eyeonus/Trade-Dangerous/commit/6c60659d0b208a21365d3c2c0afaacb2a2795674))

* New standard candles ([`ae6d3c6`](https://github.com/eyeonus/Trade-Dangerous/commit/ae6d3c6ec6ba77eadfe3953efa2df09489bfb81b))

* Merged kfsone/tradedangerous into master ([`5f15fcc`](https://github.com/eyeonus/Trade-Dangerous/commit/5f15fccf0d4b097f355ce746332f0a22b2beb16c))

* Finessed submit-distances.py ([`e88b7c5`](https://github.com/eyeonus/Trade-Dangerous/commit/e88b7c52ade6eaf1cba14f91c8b4a2b69348d5ad))

* Bumped date on edscupdate ([`8e265f9`](https://github.com/eyeonus/Trade-Dangerous/commit/8e265f90aabffc110b846d318d59b52a2b1478af))

* Data ([`bbd79fa`](https://github.com/eyeonus/Trade-Dangerous/commit/bbd79fa9f2d63e37203b16f8332f2f7d7ad6479c))

* Submit distances now has proper argv parsing ([`7d96c1b`](https://github.com/eyeonus/Trade-Dangerous/commit/7d96c1bbc3bb2d2c78f7274ba442073d693760d1))

* Submit distances after each section ([`166285e`](https://github.com/eyeonus/Trade-Dangerous/commit/166285e5cb1b37a9bd8d18220acc19e4aa9fdd9e))

* Expose added_id on System object ([`4f05f45`](https://github.com/eyeonus/Trade-Dangerous/commit/4f05f45285eb8067b13084e846904e2a6005bcf4))

* Make extra-stars support ; and # comments ([`6e775ad`](https://github.com/eyeonus/Trade-Dangerous/commit/6e775ad201d3f2e76f0d9216bba58e2862ec0f00))

* Merged kfsone/tradedangerous into master ([`c7f6ac1`](https://github.com/eyeonus/Trade-Dangerous/commit/c7f6ac1a3a76c1a1a3bde73b8cc8cbf0e936bf95))

* Added max-gain-per-ton to the Run command ([`2589560`](https://github.com/eyeonus/Trade-Dangerous/commit/258956025a12bc5b60f7e3fa9e3f7cc21df1802e))

* Fixes #178 sql error importing stations ([`21a789f`](https://github.com/eyeonus/Trade-Dangerous/commit/21a789fa3dc8a25dc75e764675f86a2b4c5fd8be))

* Fixes #178 sql error importing stations ([`2fe7507`](https://github.com/eyeonus/Trade-Dangerous/commit/2fe7507d74e086639bd01242d3680f3a1d825195))

* Merged kfsone/tradedangerous into master ([`aeeb8d5`](https://github.com/eyeonus/Trade-Dangerous/commit/aeeb8d56012352a8a4526d214f46432180741b77))

* Reduce the clutter of market command ([`f2245f0`](https://github.com/eyeonus/Trade-Dangerous/commit/f2245f0b5a7bcd00d139693b7e4c7119551e35c1))

* Added predicate to Column rendering ([`f3237eb`](https://github.com/eyeonus/Trade-Dangerous/commit/f3237ebb4360655954d8f7f39f5593f06840dddc))

* Fix bug in market command ([`3df1364`](https://github.com/eyeonus/Trade-Dangerous/commit/3df136487f37e271e214bd719aeff8b50db58707))

* Typo fix ([`90374a7`](https://github.com/eyeonus/Trade-Dangerous/commit/90374a70e3571f4c6d60b5214d45f1b534bca825))

* Merge branch &#39;market-and-shipyard&#39;

Conflicts:
	data/Station.csv ([`9191112`](https://github.com/eyeonus/Trade-Dangerous/commit/9191112e57256ca26bc1417cbc7e0ff3bac78160))

* Merged kfsone/tradedangerous into master ([`3516de6`](https://github.com/eyeonus/Trade-Dangerous/commit/3516de602d6f79ab5f0434ba1f2b098e1f6ae166))

* Stations ([`725f310`](https://github.com/eyeonus/Trade-Dangerous/commit/725f310347240c984836a845d2d61fa0a3876149))

* More star systems ([`3ec28f0`](https://github.com/eyeonus/Trade-Dangerous/commit/3ec28f0fc6c44a470e5cbf03643733a728e2c6be))

* Value for code 203 ([`cf80889`](https://github.com/eyeonus/Trade-Dangerous/commit/cf80889104b180d953a82f8ccda0559073db2926))

* case sensitivity ([`831671c`](https://github.com/eyeonus/Trade-Dangerous/commit/831671c3db545004e71e014c2a27cba538f2fe14))

* Merged kfsone/tradedangerous into master ([`cc50311`](https://github.com/eyeonus/Trade-Dangerous/commit/cc50311d849162462bb210cb4b75e8c5dbef30f7))

* We need to request stars with known positions, for now ([`f8e301a`](https://github.com/eyeonus/Trade-Dangerous/commit/f8e301a84548eeccbbea438d25ab16ebc27d9f79))

* Enable logging in the edsc module so I can tell what certain edge cases are doing ([`6c25c40`](https://github.com/eyeonus/Trade-Dangerous/commit/6c25c402cd8ac06907b33c79e29acfb8952cad3b))

* Indicate whether adding live or test more clearly ([`adc3c35`](https://github.com/eyeonus/Trade-Dangerous/commit/adc3c35515d0ccf779de33d9bd6305564e626c8e))

* Fix only adding one star and adding blank lines ([`6bf504e`](https://github.com/eyeonus/Trade-Dangerous/commit/6bf504e8d61fdbccee4dd74bf2ca3c8e440a715f))

* Remove (FIXED) and (FIX) from names when pasting ([`6cbfdf7`](https://github.com/eyeonus/Trade-Dangerous/commit/6cbfdf7b5c97a1eae87e92030ceace12e805dd3e))

* Merged kfsone/tradedangerous into master ([`40e8565`](https://github.com/eyeonus/Trade-Dangerous/commit/40e85656a6fbb6a1788c70b074f97d5e09ac653b))

* If TEST=1 is set, use data/test-stars.txt for submit-distances.py ([`bed80eb`](https://github.com/eyeonus/Trade-Dangerous/commit/bed80ebe683309a06f63a7f5ceec9bd13444f2bb))

* Lots more new stars ([`e4687d5`](https://github.com/eyeonus/Trade-Dangerous/commit/e4687d58186ee401caab73db19b6315e1a2af27d))

* Corrections ([`0da8761`](https://github.com/eyeonus/Trade-Dangerous/commit/0da87615acd2bb56612aab84f67c3ee7cc3d24d9))

* EDSC tweaks ([`662a426`](https://github.com/eyeonus/Trade-Dangerous/commit/662a426204de28adae7985c32113085990d80543))

* Fixes #146 Added &#39;MARKET&#39; command ([`1ac061b`](https://github.com/eyeonus/Trade-Dangerous/commit/1ac061bbd2befab163a8911d2821f5737b9cf5c9))

* Merged kfsone/tradedangerous into master ([`c51a8f9`](https://github.com/eyeonus/Trade-Dangerous/commit/c51a8f96c3bd43db41b9aae80fe894ea91a5a733))

* BULGARIN should be spelled without an F and two Is. ([`f9b7614`](https://github.com/eyeonus/Trade-Dangerous/commit/f9b7614c7c8f76fecada7144852482ce2d88fe87))

* Possibly the derpiest spelling of &#39;DOCK&#39; Ive see so far ([`a738de0`](https://github.com/eyeonus/Trade-Dangerous/commit/a738de0e60cf10f3ee0428148cede82ce0ae7eb8))

* Colony only has one C in it, and two &#39;o&#39;s ([`eee6cdd`](https://github.com/eyeonus/Trade-Dangerous/commit/eee6cdd68f17f8f0afe2e81143e40e856bcf823b))

* H U B is not a HUB ([`772e5cd`](https://github.com/eyeonus/Trade-Dangerous/commit/772e5cd005e33793ec9a815f39867fd9d3c16a02))

* More systems ([`d6e0bea`](https://github.com/eyeonus/Trade-Dangerous/commit/d6e0beaf765bd2a4d0f6783c6e1388d719b44eeb))

* Fixed my misuse of random.sample ([`8eb6b77`](https://github.com/eyeonus/Trade-Dangerous/commit/8eb6b77583c3f62c8c6878a79f2f31ae906f120d))

* wording changes for submit-distances ([`ccb0989`](https://github.com/eyeonus/Trade-Dangerous/commit/ccb09895ae169eb8d7f082b9cef372b0bfd6cc31))

* Merged kfsone/tradedangerous into master ([`a7c5f67`](https://github.com/eyeonus/Trade-Dangerous/commit/a7c5f6776d9fca15779125de88b62670f4322028))

* Lots more systems; added stations and ships ([`43f5279`](https://github.com/eyeonus/Trade-Dangerous/commit/43f527985c00a695f1f8e04b3eebddd17bde48ca))

* Turn off noise ([`cea97c5`](https://github.com/eyeonus/Trade-Dangerous/commit/cea97c56268a9c0535a3f904cda77a1516271b1d))

* Added DistanceQuery to the EDSC toolset ([`8e2994e`](https://github.com/eyeonus/Trade-Dangerous/commit/8e2994e85dafb4762fa3e764f71c0695771c86d4))

* Ouch, fixed edsc module not sending commander name correctly. ([`17c6e9d`](https://github.com/eyeonus/Trade-Dangerous/commit/17c6e9d6336bdd16f32bd78f83874251b139701d))

* Station update ([`6f6371e`](https://github.com/eyeonus/Trade-Dangerous/commit/6f6371e67e5d7c5b1b46a45f9835a72c3a106d7e))

* Reduced corrections list ([`4a30ca5`](https://github.com/eyeonus/Trade-Dangerous/commit/4a30ca50a349317154249e0d522e6a9351097e94))

* More systems ([`76183a5`](https://github.com/eyeonus/Trade-Dangerous/commit/76183a55469c2956da24c18a5203b290fcd2817f))

* EDSCUpdate fix for --random ([`8ebaa82`](https://github.com/eyeonus/Trade-Dangerous/commit/8ebaa8262a3b7e026105112bd7846789d343b50f))

* Limit --random to 10 systems at a time ([`f0fc383`](https://github.com/eyeonus/Trade-Dangerous/commit/f0fc38360566ec1336c13acb3d443dd3287de8d4))

* Stations and Systems ([`ae38c38`](https://github.com/eyeonus/Trade-Dangerous/commit/ae38c381322eeb79a9a761be9542b74ef997f39d))

* Skip systems ([`401dfd2`](https://github.com/eyeonus/Trade-Dangerous/commit/401dfd2912b3afc117c4afa2df6218403fb3d6f2))

* More tweaks to edscupdate ([`ca4fc78`](https://github.com/eyeonus/Trade-Dangerous/commit/ca4fc78e0f8ed70320ff9e2b330168353089bf6a))

* Wording of --debug ([`249b423`](https://github.com/eyeonus/Trade-Dangerous/commit/249b423ebce3702e36194643770a4b5689db0ed3))

* Remove posMultiplier from prices json, it saves some bytes at a cost of excess complexity ([`a051ea8`](https://github.com/eyeonus/Trade-Dangerous/commit/a051ea89be94a118a265abfe49e518f5f66d9d0c))

* Merged kfsone/tradedangerous into master ([`51f81a9`](https://github.com/eyeonus/Trade-Dangerous/commit/51f81a934812cf50267f539b6311183138ec47c7))

* Tweaks to submit-distances.py ([`9f22fb9`](https://github.com/eyeonus/Trade-Dangerous/commit/9f22fb9a2ee6fadc00d972e8437435cbec6cf7f1))

* Stations ([`6e22892`](https://github.com/eyeonus/Trade-Dangerous/commit/6e22892ae3bbc1ebc261f87ec7fd688834099b56))

* Stations ([`62ab6cc`](https://github.com/eyeonus/Trade-Dangerous/commit/62ab6cc060cb4b4cf12e1eeaa83a373b088a943e))

* Mrkos ([`c73ac32`](https://github.com/eyeonus/Trade-Dangerous/commit/c73ac32fe25cadf6d9d9c3b8cbbe661dc33d7c40))

* splash for edscupdate ([`891fe1b`](https://github.com/eyeonus/Trade-Dangerous/commit/891fe1ba31000b055639b99117ee01ab6ced11a8))

* minor changes to edscupdate.py ([`527b278`](https://github.com/eyeonus/Trade-Dangerous/commit/527b278ea8c493da299dd21698cb3d635b201ba2))

* Correction for BODB DJEDI (1.1.05) ([`f728279`](https://github.com/eyeonus/Trade-Dangerous/commit/f72827970bf73f96389424826302f205ca1a2b24))

* BODB DJEDI -&gt; BODEDI per 1.1.05 notes ([`8f9fc3f`](https://github.com/eyeonus/Trade-Dangerous/commit/8f9fc3f730afdaa9bc8c00d1cfb405c807b3ba3f))

* Changed default outliers, support comments in extra-stars.txt ([`130b575`](https://github.com/eyeonus/Trade-Dangerous/commit/130b575c2a179aa71ca29566dc3069f3d8b7d4bb))

* Merge branch &#39;master&#39; into updates ([`9defed2`](https://github.com/eyeonus/Trade-Dangerous/commit/9defed2c6b009339037090afb198a10947124e6b))

* Merged kfsone/tradedangerous into master ([`af86349`](https://github.com/eyeonus/Trade-Dangerous/commit/af86349511a633d92b7573d0b086c1542e65f6f3))

* Adds a couple vendors. ([`6e04cbf`](https://github.com/eyeonus/Trade-Dangerous/commit/6e04cbfcfe05a973868dd7bbe90b7162b9577c67))

* Mariang Stations ([`33eb7aa`](https://github.com/eyeonus/Trade-Dangerous/commit/33eb7aabb5d8eaea5b0279572239fc0b8cc3fd5a))

* Merged kfsone/tradedangerous into master ([`8a00f21`](https://github.com/eyeonus/Trade-Dangerous/commit/8a00f21d17dbf879ced9e0a78bb6af908addf9a3))

* Data ([`c1fbc15`](https://github.com/eyeonus/Trade-Dangerous/commit/c1fbc159e66e50d130d1bc4ae97e319175acd554))

* ShipVendors ([`68de350`](https://github.com/eyeonus/Trade-Dangerous/commit/68de35006610c346707e9a2b3328f0c9f442e455))

* Station data ([`946abae`](https://github.com/eyeonus/Trade-Dangerous/commit/946abaeb9777875e5174cc49b0a6800416e748a6))

* madupload usage text ([`2ed4c1f`](https://github.com/eyeonus/Trade-Dangerous/commit/2ed4c1f3cf63157fc1c20054935c4f3455f56ae1))

* Data ([`c833412`](https://github.com/eyeonus/Trade-Dangerous/commit/c8334127090c0125fc7d9712412fff82ff771671))

* Maddavo --opt=stations now honors &#39;corrections&#39; ([`b826710`](https://github.com/eyeonus/Trade-Dangerous/commit/b826710d53055153c8397c2b83f7d55a2fdf9d18))

* Gliese 868 ([`6e4df71`](https://github.com/eyeonus/Trade-Dangerous/commit/6e4df719a152b118b6779beb69d2a0440ad8f331))

* More data ([`0446ea4`](https://github.com/eyeonus/Trade-Dangerous/commit/0446ea4d32fe4c496a53916abdca13b4721558e3))

* Data additions ([`aa8475f`](https://github.com/eyeonus/Trade-Dangerous/commit/aa8475fd66bad2aece6f4598a3c83b902eba3a99))

* Merged kfsone/tradedangerous into master ([`e669f41`](https://github.com/eyeonus/Trade-Dangerous/commit/e669f411a2e30d96ec2c83d63b35bf6cf01b79f8))

* Improvements to edscupdate.py ([`a8dcb5e`](https://github.com/eyeonus/Trade-Dangerous/commit/a8dcb5e88ea959995187f22e2a21e0dad45c075f))

* Only match I pattern at start of line ([`547c091`](https://github.com/eyeonus/Trade-Dangerous/commit/547c091a924b6308b7443b2f7b5419e9856e9074))

* More derp defense ([`ba55bd6`](https://github.com/eyeonus/Trade-Dangerous/commit/ba55bd60f1942d2df7d08c57c8db9c8638522d70))

* More cleanup, and added a way to check existing db for derp ([`71b24a8`](https://github.com/eyeonus/Trade-Dangerous/commit/71b24a823c9c34a9d7daaaafb7a677e8101b484d))

* Cleaned up some station crap ([`092b246`](https://github.com/eyeonus/Trade-Dangerous/commit/092b24696d332f90d257f2c2cb5e0a25575615b3))

* Minor fix ([`db4052d`](https://github.com/eyeonus/Trade-Dangerous/commit/db4052dfe29a0170f6733f9274e94b90ac784fc8))

* Tweak to eddb.py ([`684ef07`](https://github.com/eyeonus/Trade-Dangerous/commit/684ef07899c0ad54070be3059b49071da910bd1d))

* edscupdate.py now uses argparse instead of being quite so sloppy ([`7d97e17`](https://github.com/eyeonus/Trade-Dangerous/commit/7d97e17b0e994d2a7ca47e6ed5123d7862fd5b51))

* Adding &#34;market&#34; and &#34;shipyard&#34; flags to Stations ([`7712afd`](https://github.com/eyeonus/Trade-Dangerous/commit/7712afd20ac7047d01dd3a42164d6f722ea92f7d))

* Removed commit that prevented import being non-destructive ([`e5b8315`](https://github.com/eyeonus/Trade-Dangerous/commit/e5b8315824db6dd3abcddd0c839a4ccb086f0df2))

* Typo in corrections ([`14f3d78`](https://github.com/eyeonus/Trade-Dangerous/commit/14f3d787171a69aff92b26e9f8323f20f9040960))

* Lets not worry about &#39;PORT&#39; so aggressively ([`7f4633d`](https://github.com/eyeonus/Trade-Dangerous/commit/7f4633d1c607f86ea9f1c275f6ed659116e3d694))

* Cleanup in Brani ([`2f6764f`](https://github.com/eyeonus/Trade-Dangerous/commit/2f6764f18561b65b6379dd5cead6fe56f8afca25))

* Bad derp defender ([`6713854`](https://github.com/eyeonus/Trade-Dangerous/commit/6713854e0280dd8d0c79d1dc327cceff81433848))

* Fix for import not working when you have no data ([`702f63f`](https://github.com/eyeonus/Trade-Dangerous/commit/702f63f4de9a58b3e4f78b3afb1c825563c385ca))

* Fix for import not working when you have no data ([`f05500a`](https://github.com/eyeonus/Trade-Dangerous/commit/f05500a04a8b2cc9c3cbf25c54d4ec9362c7712c))

* Merged kfsone/tradedangerous into master ([`e17f0f2`](https://github.com/eyeonus/Trade-Dangerous/commit/e17f0f2dabfc9e654714e57788ecc53d39391a14))

* Warn people about syscsv and stncsv ([`6bdd3ce`](https://github.com/eyeonus/Trade-Dangerous/commit/6bdd3ce7359a2f85d005583d24e699ffdd1b0faa))

* maddavo plugin now supports systems/stations merging

removed --opt=stncsv and --opt=syscsv and --opt=buildcache
added --opt=systems and --opt=stations and --opt=exportcsv ([`8ba5dfe`](https://github.com/eyeonus/Trade-Dangerous/commit/8ba5dfe0080eec0df13272c54fcfb262838053d9))

* updateLocalStation fixes and name-change support ([`d619e13`](https://github.com/eyeonus/Trade-Dangerous/commit/d619e13362a455eac4a702d2e1cfbecec4a53c60))

* TradeDB.addLocalSystem  accepts &#39;added&#39; and &#39;modified&#39; columns. ([`ecd3e35`](https://github.com/eyeonus/Trade-Dangerous/commit/ecd3e356ec963dde0fb6b9e2cc04d3a3491df249))

* Added System.getStation ([`4f4177b`](https://github.com/eyeonus/Trade-Dangerous/commit/4f4177be0dbbce7020efb2010c9a9ac612974d59))

* Added CSVStream object ([`12d4d75`](https://github.com/eyeonus/Trade-Dangerous/commit/12d4d755dc3af772070548c5d950993b138d7ee5))

* Don&#39;t print &#34;No Changes&#34; from inside updateLocalStation ([`3f62d79`](https://github.com/eyeonus/Trade-Dangerous/commit/3f62d7938b198e1ba816db038d59a31ca4910731))

* Normalizing ([`2bd6d43`](https://github.com/eyeonus/Trade-Dangerous/commit/2bd6d435a94be110c58314c78b562ec0ad7236ca))

* I must have been tired when I wrote that function ([`9ba4c76`](https://github.com/eyeonus/Trade-Dangerous/commit/9ba4c76c994072c389ede5783c896d18dd77652e))

* Improvements to progress bar ([`eeb2e54`](https://github.com/eyeonus/Trade-Dangerous/commit/eeb2e5427fd17e34aaa27f48e36188939dd2b795))

* Merge branch &#39;master&#39; into updates ([`7efe73d`](https://github.com/eyeonus/Trade-Dangerous/commit/7efe73d49627cf9f269980c5f5e67d36ff4d9736))

* Merged kfsone/tradedangerous into master ([`675bdf5`](https://github.com/eyeonus/Trade-Dangerous/commit/675bdf5828c250f9f16fdb1f31a57c1c2791cf28))

* Use progress bar for uncompressed json downloads ([`7ea7c30`](https://github.com/eyeonus/Trade-Dangerous/commit/7ea7c3007bf52d1bce54b7ec9c4858b0f0372747))

* Use the progress bar in run command ([`3589a22`](https://github.com/eyeonus/Trade-Dangerous/commit/3589a229bc2a645584f270477e26765d750f6523))

* Helper for rendering progress bars ([`0daf65c`](https://github.com/eyeonus/Trade-Dangerous/commit/0daf65cb33a0128aff910ffd29d887fd85cee1fe))

* Change log ([`52706ef`](https://github.com/eyeonus/Trade-Dangerous/commit/52706ef08ed5b36a85e35e747cde9a6bdee4ec50))

* Added --gain-per-ton (--gpt) to run command ([`a75311e`](https://github.com/eyeonus/Trade-Dangerous/commit/a75311e08c0872b12e0f5b0ff02cf59c7db4cea0))

* Systems and Stations ([`e90503c`](https://github.com/eyeonus/Trade-Dangerous/commit/e90503cca58984f82a8548ba88d83f334e086836))

* We&#39;re not using avoidItems in getBestHops any more ([`49fcd62`](https://github.com/eyeonus/Trade-Dangerous/commit/49fcd6295207c867b26cebb965c5a2c99c2d1037))

* Ships ([`3442437`](https://github.com/eyeonus/Trade-Dangerous/commit/344243722b433382864b6fba345adab41017c4de))

* Wu Indt Indeednt ([`86e4c60`](https://github.com/eyeonus/Trade-Dangerous/commit/86e4c60354f4e9f2cf44a159e8e2cd1036317013))

* Quick cleanup of edscupdate.py ([`aee5cfc`](https://github.com/eyeonus/Trade-Dangerous/commit/aee5cfc5aea52a4b05728c980dcf9dd0061bfc0f))

* Data ([`b845e8a`](https://github.com/eyeonus/Trade-Dangerous/commit/b845e8ab14098e7b2dbe7ea3e7b78534e092a81d))

* 98 new EDSC systems ([`ba1cb1d`](https://github.com/eyeonus/Trade-Dangerous/commit/ba1cb1db05b1de7f4eac9acc1d6635bdffe471da))

* Minor improvements to edscupdate ([`d6a2f95`](https://github.com/eyeonus/Trade-Dangerous/commit/d6a2f95e175c4742dddd0b0d6debf6db0085be08))

* Merged kfsone/tradedangerous into master ([`371a0be`](https://github.com/eyeonus/Trade-Dangerous/commit/371a0be1673992e7ea984e6d3aa7e5095f42e931))

* Improvements to tradecalc api ([`ad14af3`](https://github.com/eyeonus/Trade-Dangerous/commit/ad14af3d171b5c1a6be3579baf860c75649a87bc))

* getattr doesn&#39;t support default ([`65033de`](https://github.com/eyeonus/Trade-Dangerous/commit/65033de57783df1bc61463ac7b45e353662ecc3b))

* Improvements to the TradeCalc API ([`ff24d08`](https://github.com/eyeonus/Trade-Dangerous/commit/ff24d08885b4ad1a98456fafad323896ef6961d8))

* Better feedback in some data-starved scenarios ([`e37df32`](https://github.com/eyeonus/Trade-Dangerous/commit/e37df32fecfb3cc1bb9b8bfa6e46c01dd562b9ad))

* Ooops ([`c961604`](https://github.com/eyeonus/Trade-Dangerous/commit/c961604c9615b182750cb2491e9596fb89853d31))

* Fix for trying to get a --pad=L route from a station with a non-L station ([`68f2b8b`](https://github.com/eyeonus/Trade-Dangerous/commit/68f2b8b3d6161f24f788afcb8e2513c0d8f856a8))

* Fix really slow nav ([`970e7c2`](https://github.com/eyeonus/Trade-Dangerous/commit/970e7c23e183e18416f94f5ae23c829effbdb2f3))

* Some stations ([`0b7d0f5`](https://github.com/eyeonus/Trade-Dangerous/commit/0b7d0f546381b950c1c51f634cb9e408ec4b7156))

* Merged kfsone/tradedangerous into master ([`ae4d8ec`](https://github.com/eyeonus/Trade-Dangerous/commit/ae4d8ec21dc4d5012df045e58a652dd1584fb90f))

* Unbroke maddavo plugin ([`eefcd53`](https://github.com/eyeonus/Trade-Dangerous/commit/eefcd53860f1493fc200e5971f119c5a32efa9ef))

* Removed debug spam ([`b1befb9`](https://github.com/eyeonus/Trade-Dangerous/commit/b1befb9df1fb3f246e7d5e8f43cc9e68de83eedd))

* HUB is not spelled with an 8 ([`471d032`](https://github.com/eyeonus/Trade-Dangerous/commit/471d032da66b654bbf10e7c5a44404e5fa30f496))

* friendly error when specifying a system instead of a station ([`71192ac`](https://github.com/eyeonus/Trade-Dangerous/commit/71192ac800bd918a3ba883a61222186d6e9ef321))

* More corrections stuff ([`41d215e`](https://github.com/eyeonus/Trade-Dangerous/commit/41d215e6b96a0069b4592a46bc22f897de2fd0d0))

* Merged in RavenDT/tradedangerous (pull request #105)

After merge with v6.9.2 ([`4697be3`](https://github.com/eyeonus/Trade-Dangerous/commit/4697be3dc9a1102ce48185c9867289ad9c22f35e))

* More derp defense ([`c38b66d`](https://github.com/eyeonus/Trade-Dangerous/commit/c38b66d6a66e177a9c4010b283134d1260caf058))

* Fixes #167 unreproduced issue with not using --from or --to ([`6828aa4`](https://github.com/eyeonus/Trade-Dangerous/commit/6828aa41b48baf91b4d1c30099eeec55d33d656f))

* More manual verifications. ([`796249d`](https://github.com/eyeonus/Trade-Dangerous/commit/796249d2c35ed4cf12b44e10c93ca880d8884134))

* After today&#39;s import of EDDN data. ([`508c5d1`](https://github.com/eyeonus/Trade-Dangerous/commit/508c5d160ab7ddb997e4a513e705d885842a554d))

* I actually had time to play last night and manually verified a bunch of stations! ([`e1466d8`](https://github.com/eyeonus/Trade-Dangerous/commit/e1466d8110fe569252eeacae8d2437be562fc82e))

* Merge branch &#39;master&#39; of https://bitbucket.org/kfsone/tradedangerous ([`11616ea`](https://github.com/eyeonus/Trade-Dangerous/commit/11616ea216e1f2028e704a7cba7ef53882883675))

* More derp defense ([`91d3f49`](https://github.com/eyeonus/Trade-Dangerous/commit/91d3f49986efc2338f8de90709aa78d595c986ad))

* Station corrections ([`dbdf74c`](https://github.com/eyeonus/Trade-Dangerous/commit/dbdf74cdf3caf5f52a01cf71716d6f4d8cc00121))

* Fixes #168 buildcache failing on adding new stations ([`9a8988d`](https://github.com/eyeonus/Trade-Dangerous/commit/9a8988d3bf5d5cd861513291d44feb9949ab7889))

* Forgot to delete this one station. ([`51b6aa8`](https://github.com/eyeonus/Trade-Dangerous/commit/51b6aa8a491c718426aefcc4c76367d06ac3fce0))

* BAD STUFF KEEPS POPPING UP! ARGH! ([`b95cdaa`](https://github.com/eyeonus/Trade-Dangerous/commit/b95cdaa9a1c655f766dc11514004c694d2d6d512))

* More edits to corrections.py ([`1105dd3`](https://github.com/eyeonus/Trade-Dangerous/commit/1105dd38711ee6b30ffb093417cc93d0317b228d))

* Accidently deleted two lines in corrections.py ([`3e71d7c`](https://github.com/eyeonus/Trade-Dangerous/commit/3e71d7cdb4b7f2f18057db0a5f67844f98c6dad4))

* After successful merge with v6.9.2 ([`4ab4981`](https://github.com/eyeonus/Trade-Dangerous/commit/4ab4981e2c22fe8004eed6e33a2180fb34f52b51))

* After fixing conflicts with v6.9.2 ([`94d96e4`](https://github.com/eyeonus/Trade-Dangerous/commit/94d96e49e198a0d65a7078f20263c26a16c99c30))

* After manual merge from working directory ([`3b88d8a`](https://github.com/eyeonus/Trade-Dangerous/commit/3b88d8add1d0b7b61d7875fe7a7628454f9b05ad))

* Fixes #166 Set changed size error during run ([`4eadc4c`](https://github.com/eyeonus/Trade-Dangerous/commit/4eadc4cbc000c8466ab1f6129dd7dd87fdd996cd))

* v6.9.2 ([`7416ef3`](https://github.com/eyeonus/Trade-Dangerous/commit/7416ef3b439aae42fe43525c0e06123cbc4827f8))

* Implements #153 min/max values for sell/buy

Also fixes the issue with returning too many rows in some cases ([`8a99eed`](https://github.com/eyeonus/Trade-Dangerous/commit/8a99eed9767c570b25b5138a98bf4b7b8dec6409))

* Implements #153 min/max values for sell/buy

Also fixes the issue with returning too many rows in some cases ([`13be351`](https://github.com/eyeonus/Trade-Dangerous/commit/13be3515e516a81312db9b9e0d6624434fb64ec3))

* Change log ([`e52b50b`](https://github.com/eyeonus/Trade-Dangerous/commit/e52b50bd1cb24b762b802d372061e66a751caadb))

* Merged in dl4ner/tradedangerous/README-maddavo (pull request #103)

added maddavo options to README ([`e07c8b5`](https://github.com/eyeonus/Trade-Dangerous/commit/e07c8b5707bf22f660b03d242cf1a25230c0494f))

* Implements #161 Enhance nav command to avoid systems without stations ([`074b566`](https://github.com/eyeonus/Trade-Dangerous/commit/074b566a23c0524e3a441fa597df25031d38c3cc))

* Fixes #165 run with --to that has no stations ([`72db9d9`](https://github.com/eyeonus/Trade-Dangerous/commit/72db9d96dcaa9e7c6d1c36d83c91192c8f00376f))

* Fix debug error in tradecalc.py ([`badfb0f`](https://github.com/eyeonus/Trade-Dangerous/commit/badfb0fc71abd4f743fd65e9409a39f3d7e8463e))

* Fixes #158 find rares based on distance from multiple systems ([`5174631`](https://github.com/eyeonus/Trade-Dangerous/commit/517463109518f8118edec5cbcbdc70d1aca0f72c))

* Fixes #158 find rares based on distance from multiple systems ([`e904981`](https://github.com/eyeonus/Trade-Dangerous/commit/e90498179d972642a4a375d34ece8df65a843945))

* added maddavo options to README ([`944599a`](https://github.com/eyeonus/Trade-Dangerous/commit/944599a5ffecdb56eaf951e77f96e6aee029c70d))

* Tweaks to route calculation and presentation. Use -vvv for totals ([`8a31764`](https://github.com/eyeonus/Trade-Dangerous/commit/8a317642c4977fb1112e8e9ce871f7f2f8b6d287))

* Fix for tradecalc ([`7b22d2e`](https://github.com/eyeonus/Trade-Dangerous/commit/7b22d2e5c93f0ba541d1d1a47174e3eb564be4d9))

* make tradecalc a little less yieldy ([`a3ea4c5`](https://github.com/eyeonus/Trade-Dangerous/commit/a3ea4c55c320a7e8e2e8de57b550afe15b3825ce))

* Change log for 6.9.1 ([`33d0f60`](https://github.com/eyeonus/Trade-Dangerous/commit/33d0f60569d9bcc04271799365af9adc9ffa9c75))

* Fixes #163 Allow user to override logic for which maddavo file to use ([`4ada4c1`](https://github.com/eyeonus/Trade-Dangerous/commit/4ada4c199eea965d2c327719a8a57dddd438c3b5))

* Fixes ([`98abe51`](https://github.com/eyeonus/Trade-Dangerous/commit/98abe51e5ac1fdaad1f25fa9f13709ab628638da))

* Lots more stations ([`793d04d`](https://github.com/eyeonus/Trade-Dangerous/commit/793d04d04bd8878f97583261eb962a49d0f55d91))

* More edsc systems ([`2591ca1`](https://github.com/eyeonus/Trade-Dangerous/commit/2591ca13c19647281517de434d2a58c6b50d13f4))

* Fix for station command ([`eccaf1a`](https://github.com/eyeonus/Trade-Dangerous/commit/eccaf1a0c9e35a84a8dda9870154c594569dcf7e))

* Derp defense ([`4deb17a`](https://github.com/eyeonus/Trade-Dangerous/commit/4deb17a2f55eaaacc44cf3b67dc23f39a2b2cbb6))

* Sort goal routes to the top of the list before claiming &#39;destination reached&#39; ([`a3c3581`](https://github.com/eyeonus/Trade-Dangerous/commit/a3c3581016da5ea590ffd4683b1af3cdd2824bbe))

* Fixes #162 issue with towards ([`1a35555`](https://github.com/eyeonus/Trade-Dangerous/commit/1a355550d7ffd509c1c4e8cd8fb838be3cef9a2d))

* Lots more EDSC Systems ([`10b7f07`](https://github.com/eyeonus/Trade-Dangerous/commit/10b7f071c0cbcd011367b34e1e095f647864e7d5))

* Added &#34;--towards&#34; option to &#34;run&#34; command for building a route that requires every hop be at least as close to the goal system as the previous hop. Hops that reduce the distance are significantly favored in scoring. ([`ec592b2`](https://github.com/eyeonus/Trade-Dangerous/commit/ec592b224d7406ae70581c5c19c964e53e5f5214))

* Black hole fun. ([`3a1aa4e`](https://github.com/eyeonus/Trade-Dangerous/commit/3a1aa4e799109cec2d02f601cccb8904ce806cfb))

* Added a &#34;system&#34; property to System objects to make it easier to interchange Systems/Stations in some cases. ([`91113a6`](https://github.com/eyeonus/Trade-Dangerous/commit/91113a66e2e77a87075c1609d5f3b85369e54e18))

* And on the other side... ([`d5dcb35`](https://github.com/eyeonus/Trade-Dangerous/commit/d5dcb3533fe6309d3b53530887a69bbb624b801f))

* Sqrt is not the enemy, math.sqrt() is the enemy.

I realized that it&#39;s the function call part of math.sqrt not the actual root that makes it so expensive. Timing suggests that calling &#34;math.sqrt&#34; costs ~300ns on a 1st gen i7 vs 29ns to do &#34;** 0.5&#34;, so I introduced a &#34;Station.distanceTo&#34; call and eliminated all calls to math.sqrt in favor of ** 0.5. ([`b81e6b0`](https://github.com/eyeonus/Trade-Dangerous/commit/b81e6b01e354fd8e852c9a91698092f5646a8054))

* Merged kfsone/tradedangerous into master ([`2e0544d`](https://github.com/eyeonus/Trade-Dangerous/commit/2e0544dfaf0f01bb7fc396543f37b830903837d3))

* Fixed some badness in the profit calculator ([`d756b9e`](https://github.com/eyeonus/Trade-Dangerous/commit/d756b9ef5e71863857466a4e74cee757fcfced57))

* Fix cache load warnings ([`6ee0ec5`](https://github.com/eyeonus/Trade-Dangerous/commit/6ee0ec5babb388883cbef3b55fa56ea4c72c0b49))

* Naraka stations ([`c3aead7`](https://github.com/eyeonus/Trade-Dangerous/commit/c3aead72007de254cfd50266a061eca601cd5dbe))

* Merged kfsone/tradedangerous into master ([`354071b`](https://github.com/eyeonus/Trade-Dangerous/commit/354071b452f0f6ced00b1af8f63e265e6d03f347))

* Fixed default behavior of prices.py ([`d8ce9bb`](https://github.com/eyeonus/Trade-Dangerous/commit/d8ce9bb6d041722a369e2957e10ac95d4d11aa81))

* Added &#34;trade&#34; command for listing direct trades from station1 -&gt; station2 ([`effd7c5`](https://github.com/eyeonus/Trade-Dangerous/commit/effd7c5b1ce4ac9ec2a5355c33da1e9333536331))

* Minor cleanup ([`f261bea`](https://github.com/eyeonus/Trade-Dangerous/commit/f261bea4b62e6a16a099eb9008b35c7b4628cb2c))

* Slight change to how we get a list of trades between two stations ([`2583c1d`](https://github.com/eyeonus/Trade-Dangerous/commit/2583c1d9fdaf0516a06d56b8403cc8262fbad717))

* Fixed how we calculate best trades, more accurate and performance is changed.

Some performance will be improved, some will be worse. ([`6c53b8b`](https://github.com/eyeonus/Trade-Dangerous/commit/6c53b8ba7af69c8fb72ff07d2de28051b0760730))

* Added TradeDB.queryColumn() ([`750e051`](https://github.com/eyeonus/Trade-Dangerous/commit/750e0514ccb25585074ad4ad29a22838ca1b513a))

* Speed/memory improvement for prices parsing ([`f79a7e1`](https://github.com/eyeonus/Trade-Dangerous/commit/f79a7e14d2066106b13d9bca138e80fe74a3c7ba))

* Perf boost for csv processing ([`fc30fc0`](https://github.com/eyeonus/Trade-Dangerous/commit/fc30fc06e735754563fa45291aa539abe34ab942))

* Derp defense ([`296cd45`](https://github.com/eyeonus/Trade-Dangerous/commit/296cd45c28911cf2f51277051757de0b3485bfc7))

* Cleaned up the main of edsc ([`77a19f4`](https://github.com/eyeonus/Trade-Dangerous/commit/77a19f493c3ea4e50fbf32328252ab16e81eb386))

* Streamlined corrections list ([`e7d96ae`](https://github.com/eyeonus/Trade-Dangerous/commit/e7d96ae6924273eb0c077e5101b9446c80219fd3))

* madupload now requires a filename ([`77d9ddf`](https://github.com/eyeonus/Trade-Dangerous/commit/77d9ddf41b288652bb675a3538bb54689294e24d))

* better feedback on maddavo unicode errors ([`3c0bd88`](https://github.com/eyeonus/Trade-Dangerous/commit/3c0bd884011c14ecaf893831588d3044a2c44514))

* Better unicode handling in mad plugin ([`8010904`](https://github.com/eyeonus/Trade-Dangerous/commit/80109042a2824e0dd380e32ecc9b8d6f7d661f0c))

* ls from star is an int ([`46d0f11`](https://github.com/eyeonus/Trade-Dangerous/commit/46d0f11a3b527c5d1df79e6a1114714987844611))

* Changes to transfers.py required by the eddb thing I just wrote ([`6482a3a`](https://github.com/eyeonus/Trade-Dangerous/commit/6482a3ae6120127b793fb6a1d5f171ed43c7dde2))

* MANY HERPS: HANDLE IT ([`a67ef0c`](https://github.com/eyeonus/Trade-Dangerous/commit/a67ef0c106fdc932c4782849038480da3463db24))

* Experimental &#39;EDDB&#39; script, v0.0.0a ([`5a796c7`](https://github.com/eyeonus/Trade-Dangerous/commit/5a796c780d2d042d5c22f0a2ebabdaa9a43aa63d))

* Merged kfsone/tradedangerous into master ([`8690fa5`](https://github.com/eyeonus/Trade-Dangerous/commit/8690fa5b59388b9cba55a3d151dcace99bc7ca16))

* Captain Kirt of the starship Enterprisf... ([`aa9a06f`](https://github.com/eyeonus/Trade-Dangerous/commit/aa9a06f5244fbbba2e7b6c9795d7abb5cb9141fa))

* Removed add-station finally ([`d1caf00`](https://github.com/eyeonus/Trade-Dangerous/commit/d1caf0094d6d52d0f6c1563427511d5043383fa8))

* Systems from EDSC ([`2b62963`](https://github.com/eyeonus/Trade-Dangerous/commit/2b629633be064b2acf387485136ad8148c00f9dd))

* &#39;station&#39; command should not be taking ls-from-star as a float ([`6aecdf6`](https://github.com/eyeonus/Trade-Dangerous/commit/6aecdf6e8226c18d1fc8ddda2bae5136e698a488))

* Data fixes ([`4139d14`](https://github.com/eyeonus/Trade-Dangerous/commit/4139d14d7a3f720263533c2bed7ed12754968764))

* Change log ([`89c2cce`](https://github.com/eyeonus/Trade-Dangerous/commit/89c2cce739f9b6c44bb159fe365a2fd90da1f18a))

* Merged in RavenDT/tradedangerous (pull request #102)

After spending 7 hours reconciling station data. X_X (fixed) ([`6a024ee`](https://github.com/eyeonus/Trade-Dangerous/commit/6a024ee34cdda76e26f100aeb7bc033906b512c7))

* Improvements to titleFixup ([`0796b67`](https://github.com/eyeonus/Trade-Dangerous/commit/0796b675f6d0f7e33d20d5c0f847e0cb43ace7ee))

* Fixed errors that kfsone found from my last pull request ([`9015e60`](https://github.com/eyeonus/Trade-Dangerous/commit/9015e60caf593bfdc3ec880d9830273580c213bb))

* Merged in OpenSS/tradedangerous (pull request #99)

Add &#34;Run To&#34; option to specify end point of trade run to trade.bat ([`b9fed9f`](https://github.com/eyeonus/Trade-Dangerous/commit/b9fed9f63e294e1d74c446e13ae57b7a00a24c24))

* Merged in chmarr/tradedangerous/mine (pull request #100)

Use the argv that is passed in rather than sys.argv ([`b0caa57`](https://github.com/eyeonus/Trade-Dangerous/commit/b0caa57c5a9f62989aa6a8dab3c1ec945dfc16a3))

* Merged kfsone/tradedangerous into master ([`29e3d25`](https://github.com/eyeonus/Trade-Dangerous/commit/29e3d258efd26fb6b983c10f3a08ba64d1dee917))

* Locking in some good changes to Stations.csv ([`8413967`](https://github.com/eyeonus/Trade-Dangerous/commit/841396793e08cbe0d1cc2eb6d57b77d60010f7a3))

* Clear the end point for if this is not a &#34;to&#34; run ([`920f35b`](https://github.com/eyeonus/Trade-Dangerous/commit/920f35b56dec4e334a3d036f033a48e6318c2b02))

* Oops.  A couple of minor errors. ([`f51ca0b`](https://github.com/eyeonus/Trade-Dangerous/commit/f51ca0be13c73bcb5d753f032ef923372ab471b1))

* After 7 hours today spent reconciling Station data... X_X ([`b592b5e`](https://github.com/eyeonus/Trade-Dangerous/commit/b592b5e923c5f36d79e0f09609a30da8ea8ca51c))

* Use the argv that is passed in rather than sys.argv ([`d7cfd53`](https://github.com/eyeonus/Trade-Dangerous/commit/d7cfd53ce08a6f766b3eac6378c1e7c4a34187f7))

* Merged kfsone/tradedangerous into master (v6.8.4) ([`16faf09`](https://github.com/eyeonus/Trade-Dangerous/commit/16faf0949735bc7f396d680e3dfb1dd81104d7bc))

* Add &#34;Run To&#34; option to specify end point of trade run to trade.bat ([`66b9157`](https://github.com/eyeonus/Trade-Dangerous/commit/66b91570289020563f321ff36b59d0606e0c2a82))

* Lots of data cleanup ([`24ab971`](https://github.com/eyeonus/Trade-Dangerous/commit/24ab97191bb15fda2b316798b80c8735acbbf62e))

* Create a tmp directory ([`ba30954`](https://github.com/eyeonus/Trade-Dangerous/commit/ba309541bd7e555a32a38de5f042e96db9b0e891))

* Data fixes ([`6a8135d`](https://github.com/eyeonus/Trade-Dangerous/commit/6a8135d717a191ead75f96cf4a4b58cbc021104e))

* Merged kfsone/tradedangerous into master ([`fe7c107`](https://github.com/eyeonus/Trade-Dangerous/commit/fe7c1076c0f4c5f1830c7a3bf4e3f400d478ae8e))

* Improvements to Station command ([`a289c79`](https://github.com/eyeonus/Trade-Dangerous/commit/a289c7997315e8f3017ee9ee544571118f768804))

* Derp defense ([`df02f17`](https://github.com/eyeonus/Trade-Dangerous/commit/df02f17f79e41bfb8cdd2859a5a5c9457cec49a9))

* Tool for turning OCR Derp messages into something useful ([`e6eb06a`](https://github.com/eyeonus/Trade-Dangerous/commit/e6eb06a7bfaae4f056e73767eb00aa4a8089cc10))

* Instalqtion, you say? ([`ebcac06`](https://github.com/eyeonus/Trade-Dangerous/commit/ebcac06d68eba1c04a1e9840e5b4040ee9f10b9e))

* Merge commit &#39;63b4859b6667c0bef7b7124c5eb4063d74e9f8c4&#39; ([`5df47c6`](https://github.com/eyeonus/Trade-Dangerous/commit/5df47c6e275287ba5fce78ad84d7f7959d209e9f))

* Data ([`1bb313f`](https://github.com/eyeonus/Trade-Dangerous/commit/1bb313fb9dbd8c3000e1b8cff97b4438fb64b6e3))

* Station removed ([`825f19a`](https://github.com/eyeonus/Trade-Dangerous/commit/825f19aed6340eb7bbe1990680b4723f040d1a75))

* Fixed nasty bug in trade calculator ([`cccd00c`](https://github.com/eyeonus/Trade-Dangerous/commit/cccd00c969f86ecae50da02132c71e75fe2cc5a2))

* Fixed nasty bug in trade calculator ([`63b4859`](https://github.com/eyeonus/Trade-Dangerous/commit/63b4859b6667c0bef7b7124c5eb4063d74e9f8c4))

* Case mattErs ([`e3b91d3`](https://github.com/eyeonus/Trade-Dangerous/commit/e3b91d34e6b6e7bea07a7cf78df9309283361557))

* Systems and system tools ([`ada3c93`](https://github.com/eyeonus/Trade-Dangerous/commit/ada3c9322ee64228964e5477ef672dcd1cede58a))

* v6.8.3 CHANGES ([`44f9df0`](https://github.com/eyeonus/Trade-Dangerous/commit/44f9df0e4eaa754d4d711e75fd2a179f570cd737))

* Merged kfsone/tradedangerous into master ([`eb74ef6`](https://github.com/eyeonus/Trade-Dangerous/commit/eb74ef6f4f624c298767012ec02dee432f2b82d1))

* Derp double quotes ([`f1e0e11`](https://github.com/eyeonus/Trade-Dangerous/commit/f1e0e11dec1b918db4852442416a649e83d06b3b))

* Removed stations ([`3a12825`](https://github.com/eyeonus/Trade-Dangerous/commit/3a128259504043a209823a826af863fa861ea252))

* deletions ([`57a3d7c`](https://github.com/eyeonus/Trade-Dangerous/commit/57a3d7c2622c423f6c87fd41f696ce39e0e64d39))

* derp checks ([`2c13759`](https://github.com/eyeonus/Trade-Dangerous/commit/2c13759f74aab87e1ec1218ffec26b9613615ed3))

* Merged kfsone/tradedangerous into master ([`f9dc28e`](https://github.com/eyeonus/Trade-Dangerous/commit/f9dc28e4a2a581c1b57916ca64c8a98b14c63356))

* Tiny bit of cleanup ([`7512fd8`](https://github.com/eyeonus/Trade-Dangerous/commit/7512fd865fa718685aa2923eabe53d0c661df3b2))

* more data ([`3bab4a5`](https://github.com/eyeonus/Trade-Dangerous/commit/3bab4a5126433abe86e86c1282338497aeff119d))

* Ships ([`42828d6`](https://github.com/eyeonus/Trade-Dangerous/commit/42828d6bc762ed5f5df5718020b0a850b1baf46a))

* Less noise in submit-distances ([`3160046`](https://github.com/eyeonus/Trade-Dangerous/commit/316004672164995a333a7caa07e4eb4d5634795c))

* Data ([`e416f90`](https://github.com/eyeonus/Trade-Dangerous/commit/e416f904f5c074c5950919aae0a4b432d82f94af))

* Merged kfsone/tradedangerous into master ([`a6f72a9`](https://github.com/eyeonus/Trade-Dangerous/commit/a6f72a93313f7f0544c76bd397ea848d876428fb))

* Data update ([`6adeaf5`](https://github.com/eyeonus/Trade-Dangerous/commit/6adeaf5a562ead42bd4e87fb1c28446dfc71a2d4))

* tweaks to eddn listener ([`0d9ad68`](https://github.com/eyeonus/Trade-Dangerous/commit/0d9ad68d0710100fdacc4c732c5d6627c3d83c41))

* Cache performance: Ignore the hell out of category lines in the .price file ([`e417bc2`](https://github.com/eyeonus/Trade-Dangerous/commit/e417bc28aef1b18a73b583c41f68f266b89249b2))

* Cleanup ([`671c65a`](https://github.com/eyeonus/Trade-Dangerous/commit/671c65a3458a5b1121d79f9ecd1d062b6dc8c5ef))

* Unbreak derp check ([`5d6720d`](https://github.com/eyeonus/Trade-Dangerous/commit/5d6720db0b54a6b6b90bae3025c23ff246572a8d))

* Cleanup ([`37cf1e3`](https://github.com/eyeonus/Trade-Dangerous/commit/37cf1e315449fafdc7a908b9ce1cd51ac4a47c23))

* An EDDN Listener ([`3b548aa`](https://github.com/eyeonus/Trade-Dangerous/commit/3b548aab336ba672709b6d425b7db7a53042febe))

* Derp defense ([`18abd03`](https://github.com/eyeonus/Trade-Dangerous/commit/18abd03442b937da741f8734ef5b6126cb7231ca))

* CHANGES Update ([`1e97cf4`](https://github.com/eyeonus/Trade-Dangerous/commit/1e97cf4a1b0a76ec7237f66e316e9cf0f8600a06))

* PEP 8 Cleanup cont ([`eff71eb`](https://github.com/eyeonus/Trade-Dangerous/commit/eff71eb34411dfd4d41f3479ec80f10037d41f81))

* PEP 8 Cleanup ([`2aed8bc`](https://github.com/eyeonus/Trade-Dangerous/commit/2aed8bcd001dc1e2077c59ea246d21c7f50480bf))

* Stations from Cmdr MacNetron ([`8a284d8`](https://github.com/eyeonus/Trade-Dangerous/commit/8a284d8390c34e9e1dcb495f2afeddeaea10cb9c))

* Merge branch &#39;master&#39; into updates ([`ca2eb3b`](https://github.com/eyeonus/Trade-Dangerous/commit/ca2eb3b9487c92a6c183efa4d46ce728c1089ab8))

* Merged kfsone/tradedangerous into master ([`7259526`](https://github.com/eyeonus/Trade-Dangerous/commit/7259526c1f28ba90a332f72192ce07ff021770d1))

* Stations from bitbucket, derp defense, credits ([`3c290ea`](https://github.com/eyeonus/Trade-Dangerous/commit/3c290eabf2170f95987f417f01ee15b5f5cd2af7))

* Merged kfsone/tradedangerous into master ([`8656a22`](https://github.com/eyeonus/Trade-Dangerous/commit/8656a223c0b021c45135e40f38154447d034c1ad))

* Don&#39;t need to report which platform we are ([`08302f2`](https://github.com/eyeonus/Trade-Dangerous/commit/08302f2481f2ee63496c25acbde20c2c0c952e1f))

* Make submit-distances executable ([`efbe29e`](https://github.com/eyeonus/Trade-Dangerous/commit/efbe29e36a55e5da1ea7dd71dbb8f099dda2917a))

* Fix station for unknown system and ocr derp ([`3bd8df6`](https://github.com/eyeonus/Trade-Dangerous/commit/3bd8df6b5d77f489dabb30d1051ad8e58c6d1efa))

* Merged in RavenDT/tradedangerous (pull request #97)

Stations update ([`fb8543e`](https://github.com/eyeonus/Trade-Dangerous/commit/fb8543ea43db61dc8031cbe4e02d893b8ae3c43b))

* Fixes #150 Broken misc.clipboard ([`f486b78`](https://github.com/eyeonus/Trade-Dangerous/commit/f486b787740362cbd95a75f639fa41d8c9b49960))

* After successful merge with v6.8.2 ([`43420cc`](https://github.com/eyeonus/Trade-Dangerous/commit/43420cc61fec7208cdeee4d50eab1dab0bb52623))

* Merged kfsone/tradedangerous into master ([`28b15ce`](https://github.com/eyeonus/Trade-Dangerous/commit/28b15ce3ae90f07552c2c5c535b668e6679611f3))

* v6.8.2 ([`f11334a`](https://github.com/eyeonus/Trade-Dangerous/commit/f11334a02de79ad2f58c92077f3d055430a92836))

* Fixes #148 make import of tkinter conditional ([`c99c135`](https://github.com/eyeonus/Trade-Dangerous/commit/c99c135f499578da48f223109119a7b1d759bcf7))

* Fixes #149 nav with --via broken. ([`2dc85bc`](https://github.com/eyeonus/Trade-Dangerous/commit/2dc85bc48c6857adc77d443ef4c07e10f4a6845e))

* Merged kfsone/tradedangerous into master ([`a05f28d`](https://github.com/eyeonus/Trade-Dangerous/commit/a05f28d87d77f67ef795c8c9ceeedb3d431f7776))

* Merge branch &#39;master&#39; into updates ([`4285477`](https://github.com/eyeonus/Trade-Dangerous/commit/4285477f5fbe18414a5c1f78380ec1eb1a4b59ee))

* Merged kfsone/tradedangerous into master ([`94b37f8`](https://github.com/eyeonus/Trade-Dangerous/commit/94b37f83b987eecde99f3f5431899ee5ad16d2db))

* Harvestport shipyard. ([`589ca09`](https://github.com/eyeonus/Trade-Dangerous/commit/589ca09705fb9402303a313d6bda993065f80c6d))

* Corrected Typo (thanks Stefan) ([`ef8353f`](https://github.com/eyeonus/Trade-Dangerous/commit/ef8353fe1fc30e00fa4eb674c1dca92bc2637eb3))

* Merged kfsone/tradedangerous into master ([`c6ee99c`](https://github.com/eyeonus/Trade-Dangerous/commit/c6ee99c5b40af700b556eb543987742b1687e5f5))

* v6.8.1 ([`5e316f6`](https://github.com/eyeonus/Trade-Dangerous/commit/5e316f6aebbdf224441d66b7ce53622642cd8d3e))

* Fanning Vision shipyard ([`851e1e4`](https://github.com/eyeonus/Trade-Dangerous/commit/851e1e4fe98ba344bc7c29d9739ffdd3557b2143))

* Because edsc likes to send me the same data multiple times ([`25fe8c4`](https://github.com/eyeonus/Trade-Dangerous/commit/25fe8c4a4964a8a588d76cd9eec9517277c90acd))

* Data ([`891651a`](https://github.com/eyeonus/Trade-Dangerous/commit/891651aebab1fec80039732507c5d1ca6cf518dd))

* Fixed station argument for shipvendor ([`3421624`](https://github.com/eyeonus/Trade-Dangerous/commit/3421624d99419e9087e334e2c1e7ba733a956b71))

* Fixed bug with months in age description ([`5102470`](https://github.com/eyeonus/Trade-Dangerous/commit/5102470fd7c100b4973399a9fc53aa794282bfb2))

* More derp rejection ([`ac7fe1e`](https://github.com/eyeonus/Trade-Dangerous/commit/ac7fe1eef7b21add5f67de012210bc7bb0d91e49))

* Give me my errors ([`2dba553`](https://github.com/eyeonus/Trade-Dangerous/commit/2dba553d51241057f75192d6a90cdd9821a253cd))

* Fix for sort bug in submit-distances ([`b466341`](https://github.com/eyeonus/Trade-Dangerous/commit/b466341962954943d0f217f19abadcc5bb1ea050))

* More systems ([`79a87cd`](https://github.com/eyeonus/Trade-Dangerous/commit/79a87cdff1668f4f4d6dd34b9e8513569e78f95e))

* Improved parsing of EDSC results ([`bb2a9d0`](https://github.com/eyeonus/Trade-Dangerous/commit/bb2a9d00aeb84f697af19e66fecfba0f42623f27))

* Merged kfsone/tradedangerous into master ([`f0f5341`](https://github.com/eyeonus/Trade-Dangerous/commit/f0f53415acc2a920a4f8596dcc15a7f275d54c2a))

* kfsone corrections.py ([`d2e0a2c`](https://github.com/eyeonus/Trade-Dangerous/commit/d2e0a2c20da8379f974d1b184d363f7e13e028da))

* kfsone corrections.py ([`fdc9475`](https://github.com/eyeonus/Trade-Dangerous/commit/fdc9475640a30b86196bd897c05e9fe303b82b29))

* Revert &#34;Stations and corrections&#34;

This reverts commit 88bf8e87c9b7ff66e48920d424877072e7c3f54b. ([`1199c6b`](https://github.com/eyeonus/Trade-Dangerous/commit/1199c6b7e79fda48e4af59c47370bbd700a1ef21))

* Extra sentinels ([`1149ae3`](https://github.com/eyeonus/Trade-Dangerous/commit/1149ae3296de4f38994af3972677b79b11a3e425))

* Added a clipboard helper ([`979ece2`](https://github.com/eyeonus/Trade-Dangerous/commit/979ece289f43f57e2f207f3cd45ecf0f0fc10d70))

* Typo ([`3d53bd8`](https://github.com/eyeonus/Trade-Dangerous/commit/3d53bd8dd1ce56663b381e744d4d599f8d2b1148))

* Support for maddavo&#39;s 3h file ([`294af9d`](https://github.com/eyeonus/Trade-Dangerous/commit/294af9dc18bbb9c0c1e939d3341957e5b15364b6))

* Less cruft in submit-distances ([`5471531`](https://github.com/eyeonus/Trade-Dangerous/commit/5471531114c9fad4cfc439a5eb7d1ec604dc3039))

* Improved derp defence ([`7800ddf`](https://github.com/eyeonus/Trade-Dangerous/commit/7800ddf5e0bb37ba37ece4ceb25755099b8cdf90))

* Merged in martin_griesbach/tradedangerous (pull request #94)

tiny trade.bat update ([`cb7f87a`](https://github.com/eyeonus/Trade-Dangerous/commit/cb7f87afe29b859859596c9014c8b03d54740e8a))

* Another big data update ([`df99b94`](https://github.com/eyeonus/Trade-Dangerous/commit/df99b9470437165ca62bf662b2d563eddf18143c))

* Station properties ([`2ae95e8`](https://github.com/eyeonus/Trade-Dangerous/commit/2ae95e8cb56e384a0f8b5ace0c48e21101c52a40))

* Data cleanup ([`6480288`](https://github.com/eyeonus/Trade-Dangerous/commit/6480288df88b76ad693cdc207c5729d26dec161f))

* Some tweaks to submit-distances.py ([`e5fbef9`](https://github.com/eyeonus/Trade-Dangerous/commit/e5fbef9cfb265631716c54e1b5684f4d8613f15b))

* First time use notification for maddavo plugin ([`913569a`](https://github.com/eyeonus/Trade-Dangerous/commit/913569a9af7fe6dcc71f494a1f4b8d7f8764f38b))

* Explain what placehodlers are ([`b9c566c`](https://github.com/eyeonus/Trade-Dangerous/commit/b9c566c07da67774db9e2ca69003c5fa9ee3b300))

* tdimad -q gives highest download speed ([`f948b9b`](https://github.com/eyeonus/Trade-Dangerous/commit/f948b9be552976dc2c4fdbdb985bf13d39f9036f))

* downloads will favor speed over frequency of progress updates ([`84575e0`](https://github.com/eyeonus/Trade-Dangerous/commit/84575e0e4ba308fa6c3a467a438454898986b981))

* derp defense ([`99c323c`](https://github.com/eyeonus/Trade-Dangerous/commit/99c323c623209b21d997bc0a5c633c0c07e8059c))

* Experimenting with a thrift definition for exchanging data ([`19278e2`](https://github.com/eyeonus/Trade-Dangerous/commit/19278e2de8e613465c4bf11a54d1d217a54f9bed))

* Stations and corrections ([`88bf8e8`](https://github.com/eyeonus/Trade-Dangerous/commit/88bf8e87c9b7ff66e48920d424877072e7c3f54b))

* Merged kfsone/tradedangerous into master ([`e1294fd`](https://github.com/eyeonus/Trade-Dangerous/commit/e1294fd821717d728723016f4479a95603d5bdaf))

* Updates ([`29d8557`](https://github.com/eyeonus/Trade-Dangerous/commit/29d855771815277909dea65b4a337ae85c1a159c))

* Updates ([`1a1fff2`](https://github.com/eyeonus/Trade-Dangerous/commit/1a1fff2b80e9daebdd67f64544fc79829a0d6cfc))

* Updates ([`608fc7a`](https://github.com/eyeonus/Trade-Dangerous/commit/608fc7a89373fee1265b14255b15316907c52854))

* Updates ([`867dfd7`](https://github.com/eyeonus/Trade-Dangerous/commit/867dfd736fbc286758f561b3f1a68ec87aa84f4c))

* Cleaned up the annotate_submission_response text ([`b67026b`](https://github.com/eyeonus/Trade-Dangerous/commit/b67026bfc0c2f9c47dbd0115c746336e3a8be8a0))

* Submit distances while validating in edscupdate ([`7fa76a3`](https://github.com/eyeonus/Trade-Dangerous/commit/7fa76a349ed0c2b4c561c678a5180a18bc3100ea))

* Try to show more meaningful output from submit-distances ([`19b6c43`](https://github.com/eyeonus/Trade-Dangerous/commit/19b6c43bee119b939d8d0cfe9210e81870e8f79d))

* Added a helper for annotating EDSC submissions ([`0fce6e9`](https://github.com/eyeonus/Trade-Dangerous/commit/0fce6e99435f48c3b7ac8156356b2450c1c176b1))

* Systems, Stars and corrections ([`1d896b7`](https://github.com/eyeonus/Trade-Dangerous/commit/1d896b721666a3adb71bae20002123a69357a3f3))

* Removed bad stations ([`8860a28`](https://github.com/eyeonus/Trade-Dangerous/commit/8860a28f6f808380bdb0301e0ff370e895154677))

* Couple more derp rules ([`c9a63d4`](https://github.com/eyeonus/Trade-Dangerous/commit/c9a63d4a01d9916a0c8f11fe20544145d78a6e2e))

* Corrections ([`b2ee796`](https://github.com/eyeonus/Trade-Dangerous/commit/b2ee796386df65209c3dbcb1dad2780c6494d38c))

* Even more derp defense ([`c03e652`](https://github.com/eyeonus/Trade-Dangerous/commit/c03e6524c0f0b86d2d7acec1fbba74ddd247bf3d))

* shipvendor doesn&#39;t need difflib ([`4d1209a`](https://github.com/eyeonus/Trade-Dangerous/commit/4d1209aa88b6ec0316459bc9891acb938ddeab8b))

* Improved derp sentinel ([`50d0b6f`](https://github.com/eyeonus/Trade-Dangerous/commit/50d0b6fcb2f3b95a7adf268a21b11f288dc2c432))

* More derp detecting ([`5af8c2b`](https://github.com/eyeonus/Trade-Dangerous/commit/5af8c2bd227b54c17a2b05ee09f23935c56a685f))

* Scrappy little script looking for ocr derp ([`ab4a12c`](https://github.com/eyeonus/Trade-Dangerous/commit/ab4a12c2ca2ea7f0f28dded24c9876dea40a1490))

* Fix for derp checks that don&#39;t match an entire word ([`3a234d9`](https://github.com/eyeonus/Trade-Dangerous/commit/3a234d9955081d292c577c442b3a18acaa015fc1))

* Additional derp filters ([`633d70a`](https://github.com/eyeonus/Trade-Dangerous/commit/633d70a0bd6cffe7b960db5afde83c3e63051241))

* Couple more stations ([`183c81c`](https://github.com/eyeonus/Trade-Dangerous/commit/183c81ca1f4abe2648f8b616b2005cda6a68377d))

* trade.bat: Always escape --from as a string, so spaces in station names don&#39;t require manual escaping. ([`618a97e`](https://github.com/eyeonus/Trade-Dangerous/commit/618a97e793856726be2a73d44bd7b0744798b47a))

* Added Corrections and Stations ([`3c75a05`](https://github.com/eyeonus/Trade-Dangerous/commit/3c75a05c3f1075af4cd211bf054c4c40136f08bf))

* Merged kfsone/tradedangerous into master ([`0461b25`](https://github.com/eyeonus/Trade-Dangerous/commit/0461b25db78eaa38c0463685e471c8463e20227f))

* Merged kfsone/tradedangerous into master ([`0289376`](https://github.com/eyeonus/Trade-Dangerous/commit/0289376d9ee4e98188bc520624673e6d8e9015ea))

* Fix for --unqiue ([`0b6c8d2`](https://github.com/eyeonus/Trade-Dangerous/commit/0b6c8d25cd09beb1e5b3d458623a62a939bd82e7))

* Merged kfsone/tradedangerous into master ([`9171c9b`](https://github.com/eyeonus/Trade-Dangerous/commit/9171c9b274c569a002a68d5c3565de607b81845a))

* Revert &#34;Corrections and Stations&#34;

This reverts commit e82f4d57e9b028660a5bc713bd20aa989db4e3b1. ([`c13a6fa`](https://github.com/eyeonus/Trade-Dangerous/commit/c13a6fad69604c375230c2c92a08fd4b68de5e45))

* Corrections and Stations ([`e82f4d5`](https://github.com/eyeonus/Trade-Dangerous/commit/e82f4d57e9b028660a5bc713bd20aa989db4e3b1))

* Stations ([`1f2481d`](https://github.com/eyeonus/Trade-Dangerous/commit/1f2481d167f5f909e79824abce5326f3b2487a24))

* v6.8.0 ([`426743b`](https://github.com/eyeonus/Trade-Dangerous/commit/426743b3fd1186e05ec83d1eaae5a4479e7c41a6))

* #135 Include data age in checklist and on x52 ([`7140fb4`](https://github.com/eyeonus/Trade-Dangerous/commit/7140fb461dfdc94c95ef31975ca23a61cfc57e92))

* Issue #130 Add ShipVendor command

Original code was by Dirk Wilhelm, I reduced it to a simpler base and added checks for whether or not the entry you were trying to add/remove was already present/absent. ([`9011d40`](https://github.com/eyeonus/Trade-Dangerous/commit/9011d404e9ea683477617525a2ff2dd3b6c1b238))

* Fixes #141 better explanation of why we want to install &#39;requests&#39; ([`82c3916`](https://github.com/eyeonus/Trade-Dangerous/commit/82c3916a2cc64770f8a81e04b4e4a61c677e5c46))

* Fixes #142: --stations with nav caused error ([`a62159a`](https://github.com/eyeonus/Trade-Dangerous/commit/a62159ab317c7284c5ed177bbb00e6257221256c))

* Continuing the fight against OCR Oerp ([`56629e7`](https://github.com/eyeonus/Trade-Dangerous/commit/56629e7352e4ec68e98b8c2b44778ee41b9754fb))

* New system ([`af01c51`](https://github.com/eyeonus/Trade-Dangerous/commit/af01c515a0ec725626d6c9525c6e2281d3654f0d))

* Ignore AN SEXSTANS ([`4240e25`](https://github.com/eyeonus/Trade-Dangerous/commit/4240e25ac08e0e026c9c9c6879e0108b04c96389))

* KAPTEYN ([`61dcc26`](https://github.com/eyeonus/Trade-Dangerous/commit/61dcc261143983cbefc0015f25f3a2a4c13a4ec7))

* Some additional ignores for EDSCUpdate ([`de71878`](https://github.com/eyeonus/Trade-Dangerous/commit/de7187879211955e9b2e553a423fafd21a655329))

* Systems ([`ebf46ee`](https://github.com/eyeonus/Trade-Dangerous/commit/ebf46ee9da4f0d5d354fd0a0ccc2475740ef41fd))

* Don&#39;t check for OCR Derp before looking up the name ([`db25b9d`](https://github.com/eyeonus/Trade-Dangerous/commit/db25b9d4d5a87616797813e269d07793290c74ed))

* More systems ([`ebc381e`](https://github.com/eyeonus/Trade-Dangerous/commit/ebc381e800bce802d48523ef1a272475afed4cbb))

* Fixed edscupdate ([`ae68610`](https://github.com/eyeonus/Trade-Dangerous/commit/ae6861070713bb4f33b41f0f52046aafd830d9ed))

* Nixing the bad OCR names (OOCK, etc) ([`1ffce17`](https://github.com/eyeonus/Trade-Dangerous/commit/1ffce17c3fcbf536ebced311047934feb4bbdc8f))

* Merged kfsone/tradedangerous into master ([`d0c976c`](https://github.com/eyeonus/Trade-Dangerous/commit/d0c976cc4a6227810236bcbf5db7ffea579f4778))

* Merged kfsone/tradedangerous into master ([`6912b3a`](https://github.com/eyeonus/Trade-Dangerous/commit/6912b3a65cda557e8dd971cfe8f3366ecc6e088d))

* More station data ([`5533274`](https://github.com/eyeonus/Trade-Dangerous/commit/5533274f8c752fe1e6d71c2df2d6bc99edbc7695))

* less edsc spam ([`32b0f44`](https://github.com/eyeonus/Trade-Dangerous/commit/32b0f44b521de2d6bb508bdc62e9f9b57869450e))

* Data ([`52722c0`](https://github.com/eyeonus/Trade-Dangerous/commit/52722c0ab9577d16714459c4fb4aae73b3afb739))

* Accept list and dict distances in StarSubmission constructor ([`d6e31ef`](https://github.com/eyeonus/Trade-Dangerous/commit/d6e31ef97f0d63f4b1a3667b9f4c1b0970a594d6))

* Tweaks to submit-distances ([`9ef85d5`](https://github.com/eyeonus/Trade-Dangerous/commit/9ef85d5f5f56a7c92325d542774169df0213107e))

* Station Data ([`5ec98c3`](https://github.com/eyeonus/Trade-Dangerous/commit/5ec98c3672d97db4bf2c3c60aeee14fc7003ef6d))

* Added a way to pass distances to StarSubmission ([`4080c5e`](https://github.com/eyeonus/Trade-Dangerous/commit/4080c5e31eeddd42737fbb759843ede58840171a))

* Ooops ([`8468747`](https://github.com/eyeonus/Trade-Dangerous/commit/84687478a437916d3d23b74c3cb17afa52a84bb8))

* EDSC cleanup ([`183b071`](https://github.com/eyeonus/Trade-Dangerous/commit/183b0717b63c9cc34d896b2577d2f62accc1b95e))

* Added &#34;--max-routes&#34; and made &#34;--ls-max&#34; ignore stations with unknown distances. ([`e42f56d`](https://github.com/eyeonus/Trade-Dangerous/commit/e42f56d78f36d4e608b9de96d3bbe02ccf756edd))

* Cleanup ([`2383c8d`](https://github.com/eyeonus/Trade-Dangerous/commit/2383c8db89a8c4298fd3f5f4652c5e48c9f82fe4))

* More submit-distances help ([`b10e1a6`](https://github.com/eyeonus/Trade-Dangerous/commit/b10e1a6374e13faa5538285c181ceba3c89cddf2))

* Cleanup ([`1b6172f`](https://github.com/eyeonus/Trade-Dangerous/commit/1b6172fda14227fe945df58b1537b89fc385c613))

* More systems ([`a1707e5`](https://github.com/eyeonus/Trade-Dangerous/commit/a1707e54e7f4fdce768151f4d3195158fb3f33fb))

* Added &#39;submit-distances.py&#39; tool for submitting systems to EDStarCoordinator ([`dbddb5a`](https://github.com/eyeonus/Trade-Dangerous/commit/dbddb5ae68c257a047faf6d4debe758d35434f71))

* Unused package ([`53d0353`](https://github.com/eyeonus/Trade-Dangerous/commit/53d0353bb99ab1b0b2c07ca1efa3f7a4a6ae30d9))

* Corrections ([`0c8ccea`](https://github.com/eyeonus/Trade-Dangerous/commit/0c8ccea9d26ffe083d04fe73a10106f77567f04d))

* Merged kfsone/tradedangerous into master ([`5d6633a`](https://github.com/eyeonus/Trade-Dangerous/commit/5d6633a42c4a8665f36cc614f50c831969c74a62))

* One last correction ([`007bcc7`](https://github.com/eyeonus/Trade-Dangerous/commit/007bcc709d6f44d3ccdead68c4af7649cd2e81a2))

* Updated corrections to handle bad OCR names ([`de1d74b`](https://github.com/eyeonus/Trade-Dangerous/commit/de1d74bbf2f0dcf55ee97dfa04fd3551e31de988))

* Merged kfsone/tradedangerous into master ([`44bf5ed`](https://github.com/eyeonus/Trade-Dangerous/commit/44bf5edaae7aef19d34b7d0c59e51dd317a4b80b))

* Merged kfsone/tradedangerous into master ([`176e8b1`](https://github.com/eyeonus/Trade-Dangerous/commit/176e8b1722ac342d102a70ff383a20af12bb0118))

* Jordan Stop ([`390e560`](https://github.com/eyeonus/Trade-Dangerous/commit/390e560e4a9c44c45a167df84e57199a73cd5a82))

* More systems ([`5b67c09`](https://github.com/eyeonus/Trade-Dangerous/commit/5b67c094e94266dea29570b0f1394d97079e1c0f))

* Fix for edscupdate ([`fac517e`](https://github.com/eyeonus/Trade-Dangerous/commit/fac517e55a5fa779e98a00cad60c87f820a83b54))

* Additional station data ([`34de6d1`](https://github.com/eyeonus/Trade-Dangerous/commit/34de6d1773236d4301047b00c505af87198ce9ef))

* Station data ([`15521e3`](https://github.com/eyeonus/Trade-Dangerous/commit/15521e311abffd31f5613a1d4421d01c01d694ce))

* Typo in tdrun ([`3b6be5c`](https://github.com/eyeonus/Trade-Dangerous/commit/3b6be5c78521421fb60e5161226c564be2369d63))

* Menezes ([`b6273d6`](https://github.com/eyeonus/Trade-Dangerous/commit/b6273d66a47c357a123da00917fee02ca18e1d7c))

* Merged in jared_buntain/tradedangerous-jared (pull request #92)

Station update Jan 18th 2015 ([`1a8c4bd`](https://github.com/eyeonus/Trade-Dangerous/commit/1a8c4bd0c7b1bbf987871425ec11984d6bc5c0a2))

* Station update Jan 18th 2015 with proper ordering ([`348d05b`](https://github.com/eyeonus/Trade-Dangerous/commit/348d05bb621717df88d2d6b9e0568b428f31dc24))

* Merge branch &#39;master&#39; of https://bitbucket.org/kfsone/tradedangerous ([`13f511b`](https://github.com/eyeonus/Trade-Dangerous/commit/13f511b1258a2031021a2d240e348400b038a54c))

* Station update, Jan 18th 2015 ([`414b77a`](https://github.com/eyeonus/Trade-Dangerous/commit/414b77af585fb835dec520231b732e7b73c8e38e))

* Fix for add-station ([`fd1669b`](https://github.com/eyeonus/Trade-Dangerous/commit/fd1669bc1253d4e13fde24e8b4265c4ff7584751))

* Merged kfsone/tradedangerous into master ([`d6a3d31`](https://github.com/eyeonus/Trade-Dangerous/commit/d6a3d3181b808989f520344346e9386e1f2a9671))

* Use filter options to eliminate TradeCalc candidates ([`9c17044`](https://github.com/eyeonus/Trade-Dangerous/commit/9c17044730ee223686980c9221fa7f35f02e8cf0))

* Added --prune-score and --prune-hops to RUN

These allow you to eliminate candidate routes early on in the
&#34;run&#34; command based on their performance compared to the current
leader.

For example

  --prune-score 22.5 --prune-hops 3

says that from the 3rd hop, begin eliminate routes which have
scored under 22.5% of the current best candidate. This can
significantly improve the time to calculate long runs.

But if the early hops are all poor performers it can keep you from
seeing a gold mine a few hops away that requires you to take a few
low-profit hits first.

E.g.

  -1-&gt; 50cr/ton -2-&gt; 90cr/ton -3-&gt; 50cr/ton -4-&gt; 50cr/ton
  -1-&gt; 10cr/ton -2-&gt; 50cr/ton -3-&gt; 20cr/ton -4-&gt; 900cr/ton

&#34;--prune-score 50 --prune-hops 4&#34;

would cause you to miss the second option. ([`b33b3f1`](https://github.com/eyeonus/Trade-Dangerous/commit/b33b3f186b3a49d8beebca5bf4c90962a29f702a))

* Install &#39;requests&#39; for the user if they want it ([`7b329a9`](https://github.com/eyeonus/Trade-Dangerous/commit/7b329a90b65ed49ef5b0774148a4cf24e436e247))

* Automatically add placeholders for stations

While parsing TradeDangerous.prices or a .prices import, if the
&#34;--ignore-unknown&#34; (-i) flag is specified, instead of just ignoring
unrecognized stations, we now add a placeholder for it to the cache.

Note that when you rebuild the cache, the placeholders will be lost,
so you will need to buildcache -i. ([`f01ae85`](https://github.com/eyeonus/Trade-Dangerous/commit/f01ae8576a81aecba49bda8fb074cfabcedd5774))

* Corrections ([`5b12ec6`](https://github.com/eyeonus/Trade-Dangerous/commit/5b12ec618160ecfd538852720a672be6e3c9539f))

* Merged kfsone/tradedangerous into master ([`1ceb285`](https://github.com/eyeonus/Trade-Dangerous/commit/1ceb285b47c47f92baaa8dd8c135a15ff0294791))

* *blush* ([`80ff9ee`](https://github.com/eyeonus/Trade-Dangerous/commit/80ff9eee289aa3479e12cc9d7d7821c2b09b604e))

* Added a --ls-max option to &#39;run&#39; command ([`c85bd31`](https://github.com/eyeonus/Trade-Dangerous/commit/c85bd31c8d80ab8c0e5d75adf32e33b260c4a2ec))

* Station updates ([`15f2300`](https://github.com/eyeonus/Trade-Dangerous/commit/15f23007ae97fe790d4ef14a6de0822cf39a18cd))

* Very basic script for updating and checking Systems ([`59ccab1`](https://github.com/eyeonus/Trade-Dangerous/commit/59ccab1e4a6e9831210934efdb57a174f0c2f319))

* Added 140+ systems from EDStarCoordinator ([`f2df876`](https://github.com/eyeonus/Trade-Dangerous/commit/f2df876edbc191c6b5bc4dfc587f1d102cbbf3ac))

* Wording ([`cf7d9c3`](https://github.com/eyeonus/Trade-Dangerous/commit/cf7d9c31397192e57b76cd191d5078b9e4875174))

* Normalized ship names ([`8be60e0`](https://github.com/eyeonus/Trade-Dangerous/commit/8be60e0fd3bf8af6bc4f2d07535139c1a2303524))

* Merged in orphu/tradedangerous/updates (pull request #91)

A few station and shipyard updates. ([`7c64729`](https://github.com/eyeonus/Trade-Dangerous/commit/7c64729011705fc2920fa308912e822da090f401))

* Merge branch &#39;master&#39; into updates ([`79b111e`](https://github.com/eyeonus/Trade-Dangerous/commit/79b111ee656f9e8e1bdb10909f21e307f22007a8))

* Merged kfsone/tradedangerous into master ([`e70f724`](https://github.com/eyeonus/Trade-Dangerous/commit/e70f724b1aad3df47b578ef28c17c74813278abb))

* Data for Kruger 60. ([`eee3e51`](https://github.com/eyeonus/Trade-Dangerous/commit/eee3e51e70804d79b93c08d495e9be8e7314136a))

* Merged kfsone/tradedangerous into master ([`8aadd6b`](https://github.com/eyeonus/Trade-Dangerous/commit/8aadd6b9392a435d20e5158bb478800ecbb4c37e))

* Additional plugin documentation ([`3201127`](https://github.com/eyeonus/Trade-Dangerous/commit/32011277d7db7526f130b5a07cbcfe629de422cb))

* Merge branch &#39;master&#39; into updates ([`88d880b`](https://github.com/eyeonus/Trade-Dangerous/commit/88d880bf18b040607eb7eb20395b71ee79db8f9f))

* Restore Thoreau Orbital ([`763f95b`](https://github.com/eyeonus/Trade-Dangerous/commit/763f95b4e1b62324a8a3b47438f5b27d4649b955))

* Station and Vendor updates. ([`2d1ca00`](https://github.com/eyeonus/Trade-Dangerous/commit/2d1ca002585d852a60ceb903f985dd6934b13191))

* Tradedangerous.new ([`42b0bc8`](https://github.com/eyeonus/Trade-Dangerous/commit/42b0bc8b8142c6601f39edace70670d46e73d15c))

* Merge branch &#39;master&#39; of https://bitbucket.org/maddavo/tradedangerous ([`2e2253d`](https://github.com/eyeonus/Trade-Dangerous/commit/2e2253db25cc0fe5aedbbbbda5ec9d3c5ce76420))

* Merged kfsone/tradedangerous into master ([`2ad6b3b`](https://github.com/eyeonus/Trade-Dangerous/commit/2ad6b3b2069942a7fdf1354121f7b083e9a0d60d))

* Changes update ([`253a8f2`](https://github.com/eyeonus/Trade-Dangerous/commit/253a8f2ea1f881a4f81c1273ac00737aa9e9225a))

* Code and documentation cleanup ([`f85cf62`](https://github.com/eyeonus/Trade-Dangerous/commit/f85cf62bbd4d087d8e79111e6651d42686fc584e))

* Merged in tKe/tradedangerous/buy-improvements (pull request #87)

Buy command: Ship support and fix large --ly distance bug ([`e90e59e`](https://github.com/eyeonus/Trade-Dangerous/commit/e90e59e216abf50ac1c509fb019c4545e401a65d))

* Added Bruteman&#39;s windows script (scritps\tradebrute.bat) ([`a2f29f0`](https://github.com/eyeonus/Trade-Dangerous/commit/a2f29f0b0b72e3f420af8b2f86027bfce4d8df57))

* Data update ([`ffb7d2e`](https://github.com/eyeonus/Trade-Dangerous/commit/ffb7d2e86d0314722573f71a013cf6b09144f904))

* Added station command to bash completion ([`e2818e5`](https://github.com/eyeonus/Trade-Dangerous/commit/e2818e5c51f31b0715a77a20fb761b1f37c42e66))

* Fix for origin system being doubled up in getDestinations sometimes. ([`fb6aa95`](https://github.com/eyeonus/Trade-Dangerous/commit/fb6aa95c4c75d5fc7e5d6f332cd768c75cd5baee))

* Allow getDestinations(trade=False) from a system rather than station ([`a7d33d5`](https://github.com/eyeonus/Trade-Dangerous/commit/a7d33d5aaa40cdf9f0f7e8899e35319048c393aa))

* Don&#39;t sort destinations, that&#39;s a terribad idea ([`4317753`](https://github.com/eyeonus/Trade-Dangerous/commit/4317753f735814a10efe24c73a75c15a2329b5a1))

* Return trade destinations by distance ([`a379a7b`](https://github.com/eyeonus/Trade-Dangerous/commit/a379a7bd519d59e82fe272133dca73cb34f118b0))

* Catch bad timestamp errors with an explanation in TradeCalc ([`e070e5b`](https://github.com/eyeonus/Trade-Dangerous/commit/e070e5b67b71d4187ab0a9abed7a73c8858d67a8))

* Merged in jared_buntain/tradedangerous-jared (pull request #90)

Station update Jan 14th 2015 ([`9bdd5da`](https://github.com/eyeonus/Trade-Dangerous/commit/9bdd5da56cb5acb2f0f088a793044d2ff6e8c813))

* Added getRoute to TradeDB ([`28e5dfb`](https://github.com/eyeonus/Trade-Dangerous/commit/28e5dfb47e995050967128cc106a006df1afc578))

* Merge branch &#39;master&#39; of https://bitbucket.org/kfsone/tradedangerous ([`db34b4d`](https://github.com/eyeonus/Trade-Dangerous/commit/db34b4d0d5deeabcb9707f870b9de64cb44d751b))

* Station update Jan 14 2015 ([`bf04054`](https://github.com/eyeonus/Trade-Dangerous/commit/bf04054711f6f6e80667d61956c05a7fbd8b6a8d))

* Merged kfsone/tradedangerous into master ([`44310d1`](https://github.com/eyeonus/Trade-Dangerous/commit/44310d169696d1a7eccfa1b00b5660f576495832))

* Stations from NeoTron ([`f75d46f`](https://github.com/eyeonus/Trade-Dangerous/commit/f75d46f615dd85d98cc528136aacebd00c050176))

* Additional stations. ([`158e2e4`](https://github.com/eyeonus/Trade-Dangerous/commit/158e2e4885fbf1f63345e26cfa2b452c5b7dd3d7))

* Station update Jan 12th 2015 ([`b57b081`](https://github.com/eyeonus/Trade-Dangerous/commit/b57b0816c70a7e56cdae3c329d488b3dca400a1a))

* Merged kfsone/tradedangerous into master ([`cbce234`](https://github.com/eyeonus/Trade-Dangerous/commit/cbce23420f2eac5cb1727ba4fd6a1aded62f73cb))

* Merged kfsone/tradedangerous into master ([`6e7d22a`](https://github.com/eyeonus/Trade-Dangerous/commit/6e7d22a412706d3899a311838a8bb59b3c826fdc))

* Merged in jared_buntain/tradedangerous-jared (pull request #88)

Station update Jan 11th 2015 ([`115a374`](https://github.com/eyeonus/Trade-Dangerous/commit/115a37492519f8611213c1650f110e71ee89da79))

* Merged in orphu/tradedangerous/updates (pull request #89)

Station and Vendor Updates. ([`caae51e`](https://github.com/eyeonus/Trade-Dangerous/commit/caae51e8a4a09062d02e19913688e09869beb02f))

* Merge branch &#39;master&#39; into updates

Conflicts:
	data/ShipVendor.csv ([`3ae8f02`](https://github.com/eyeonus/Trade-Dangerous/commit/3ae8f0237f57d8e6b5f9604803dcb05e56c2d8b5))

* Station and vendor updates. ([`94d0888`](https://github.com/eyeonus/Trade-Dangerous/commit/94d08889f14cd6a85ea059dda7e16abcc50cc1ba))

* Merged kfsone/tradedangerous into master ([`1377bd6`](https://github.com/eyeonus/Trade-Dangerous/commit/1377bd6ce34bded699dfd92ac0de3baab404415f))

* Station merge ([`de31e2e`](https://github.com/eyeonus/Trade-Dangerous/commit/de31e2ead17822dcf4e131287ce572240cfcabea))

* add ship support to buy command ([`2177bb0`](https://github.com/eyeonus/Trade-Dangerous/commit/2177bb017905916cd6563d8743fa13090eec1511))

* fix issue with large --ly distance returning too many systems to filter by ([`0233174`](https://github.com/eyeonus/Trade-Dangerous/commit/0233174fa66c5e884bdf29f5748abe1ff7d69a02))

* Merge branch &#39;master&#39; of https://bitbucket.org/jared_buntain/tradedangerous-jared ([`8be1f10`](https://github.com/eyeonus/Trade-Dangerous/commit/8be1f10faf27ec8edabf4a07fc34e9a95efd72e6))

* Merge branch &#39;master&#39; of https://bitbucket.org/kfsone/tradedangerous ([`b232852`](https://github.com/eyeonus/Trade-Dangerous/commit/b23285295cc734c7506c1678ef131b072e2017ec))

* weee have I messed something up or what ([`8cf6397`](https://github.com/eyeonus/Trade-Dangerous/commit/8cf6397211b35cb4e0ea7e129d08856d481869ba))

* Merge branch &#39;master&#39; of https://bitbucket.org/kfsone/tradedangerous

Conflicts:
	CHANGES.txt
	commands/run_cmd.py
	data/Station.csv ([`5bba75f`](https://github.com/eyeonus/Trade-Dangerous/commit/5bba75f7fe3c2c9df0dd40ea053793a22f2ab91c))

* Merge branch &#39;master&#39; of https://bitbucket.org/maddavo/tradedangerous ([`b37d3d5`](https://github.com/eyeonus/Trade-Dangerous/commit/b37d3d58c33d95fb8ceacee5e420f26cd15fc45a))

* Stations prior to a Maddavo import ([`5260450`](https://github.com/eyeonus/Trade-Dangerous/commit/526045065db1fa77cc221af5f78ef8a9de0e14ce))

* Merged kfsone/tradedangerous into master ([`174e376`](https://github.com/eyeonus/Trade-Dangerous/commit/174e3761e3e28e915dcbe0ed7e5f058398874030))

* corrections.py ([`20c0505`](https://github.com/eyeonus/Trade-Dangerous/commit/20c0505f0af40cc8ff50f1eb6a22573f486f2c0d))

* Fix for station-to-station route ([`555bc3e`](https://github.com/eyeonus/Trade-Dangerous/commit/555bc3ea93fc4bc3c8faeb3e0f2209ddfb8a06fc))

* Merged kfsone/tradedangerous into master ([`9708178`](https://github.com/eyeonus/Trade-Dangerous/commit/97081780e945c553947178bcb9c37e3ecfd18e61))

* Data ([`6096a4b`](https://github.com/eyeonus/Trade-Dangerous/commit/6096a4b2a247d836e91f15382839b1bbbdbd44b5))

* Fix for system restrictions (--to system) ([`e23f904`](https://github.com/eyeonus/Trade-Dangerous/commit/e23f9045c15da24e662a785dd7fb9fa97fe017be))

* &#39;and&#39; in date ranges misconstrued &#39;2days and 10hrs&#39; ([`157fa3b`](https://github.com/eyeonus/Trade-Dangerous/commit/157fa3b586d54f1b8e0c7cec2a5b7d6471976549))

* Minor changes ([`fccc557`](https://github.com/eyeonus/Trade-Dangerous/commit/fccc5570ecb6d2bc7f5aded417beba60fb5853c6))

* Human-readable error when rares doesn&#39;t find any items ([`d135928`](https://github.com/eyeonus/Trade-Dangerous/commit/d13592846f4a6c80cd3ac74615bb447e6d63f213))

* Fix for run command ([`b4880fa`](https://github.com/eyeonus/Trade-Dangerous/commit/b4880fa83906c2bd7d7ef0fa9eef0b6c30db0378))

* 200+ new Systems ([`3b5b18d`](https://github.com/eyeonus/Trade-Dangerous/commit/3b5b18d75ecddd6ef5db06fc0c19b7d4aa8cc858))

* Station updates in LUGH ([`210a9a8`](https://github.com/eyeonus/Trade-Dangerous/commit/210a9a8e78ce63a5041529e12761c8545e0e8815))

* Fix for --via ([`68e58e9`](https://github.com/eyeonus/Trade-Dangerous/commit/68e58e9891cfd64ad7ce0118339b158b190f21d3))

* Fix for errors with --via ([`8a627d0`](https://github.com/eyeonus/Trade-Dangerous/commit/8a627d0801fd02d947706bad67898313a28d72a4))

* Fresh data ([`627a57e`](https://github.com/eyeonus/Trade-Dangerous/commit/627a57ed206207b943f3309de8fd2a03432ea847))

* Merged kfsone/tradedangerous into master ([`a6eac88`](https://github.com/eyeonus/Trade-Dangerous/commit/a6eac88546043f25b32e386802226ef1507ac2d5))

* More station data ([`d5ef792`](https://github.com/eyeonus/Trade-Dangerous/commit/d5ef7921e9a9d48a7ea6e462bfaa75e3ce2bd550))

* Station data ([`ed64f84`](https://github.com/eyeonus/Trade-Dangerous/commit/ed64f841edf068704819013bda3110fa50b550a6))

* Merged kfsone/tradedangerous into master ([`b90ad81`](https://github.com/eyeonus/Trade-Dangerous/commit/b90ad812b1e209c4a46cdea5fe2c1e68bd74c7fc))

* Added &#34;--black-market&#34; (-bm) and &#34;--end-jumps&#34; (-e) to run

--black-market lets you restrict results to stations with a black market,
--end-jumps is like --start-jumps for the destination ([`6ec6e4e`](https://github.com/eyeonus/Trade-Dangerous/commit/6ec6e4e6c0da7c3496fc5a3ec70aa360a60c956c))

* Merged kfsone/tradedangerous into master ([`0616c05`](https://github.com/eyeonus/Trade-Dangerous/commit/0616c05db984e6a63e3701dac70a34221cd42dc0))

* Merged kfsone/tradedangerous into master ([`e38acf4`](https://github.com/eyeonus/Trade-Dangerous/commit/e38acf4a4e6070b1637e03dd057aa2049b5c8d98))

* Merge commit &#39;c52290ce3285dc2e1a39a8bf6b7554cf3c8d6c08&#39;

* commit &#39;c52290ce3285dc2e1a39a8bf6b7554cf3c8d6c08&#39;:
  Updates and corrections
  corrections.py edited online with Bitbucket
  Updates and corrections
  Updates and corrections

Conflicts:
	data/Station.csv ([`663726c`](https://github.com/eyeonus/Trade-Dangerous/commit/663726ccff9691123e022b3adf0831cb66b09d2c))

* Convert &#39;export&#39; to use NOTE where where relevant ([`1d11459`](https://github.com/eyeonus/Trade-Dangerous/commit/1d11459298d56cf946a44170b6f79165b9af67e7))

* Merged in jared_buntain/tradedangerous-jared (pull request #85)

Station update Jan 10 ([`aa88b9f`](https://github.com/eyeonus/Trade-Dangerous/commit/aa88b9fa5cb7bcf391c4eb0f51f5a0fea739a988))

* Updates and corrections ([`c52290c`](https://github.com/eyeonus/Trade-Dangerous/commit/c52290ce3285dc2e1a39a8bf6b7554cf3c8d6c08))

* Merged kfsone/tradedangerous into master ([`2d2092e`](https://github.com/eyeonus/Trade-Dangerous/commit/2d2092ef8fd5257425333e1d1f9c422342280739))

* corrections.py edited online with Bitbucket ([`5c50bc8`](https://github.com/eyeonus/Trade-Dangerous/commit/5c50bc8781891e2fd8eb76fd0fedb02e5eeb0a9e))

* Only taking the good stations from master ([`749ca60`](https://github.com/eyeonus/Trade-Dangerous/commit/749ca60c965ef2da55482cce2c56627db6fdb29f))

* Merge branch &#39;master&#39; of https://bitbucket.org/kfsone/tradedangerous ([`c3509e8`](https://github.com/eyeonus/Trade-Dangerous/commit/c3509e85a2f5777561303a286614a595c525aa46))

* Station merge ([`9af3c5f`](https://github.com/eyeonus/Trade-Dangerous/commit/9af3c5f07cfbb985da8fa2959bd56fd1aacfaa67))

* Updates and corrections ([`180bb79`](https://github.com/eyeonus/Trade-Dangerous/commit/180bb79eb88d74174ab7aa3a842c0c1c4bfa624a))

* Updates and corrections ([`4b9899d`](https://github.com/eyeonus/Trade-Dangerous/commit/4b9899d104cdccd76ab528ece8ec7cc483cd5290))

* Merged kfsone/tradedangerous into master ([`58d7c59`](https://github.com/eyeonus/Trade-Dangerous/commit/58d7c5967876d3fab7e899a414f05385a6788818))

* fixes #125 No such station: STEIN 2051/Trevithick port ([`cb60a75`](https://github.com/eyeonus/Trade-Dangerous/commit/cb60a75cf4ac30409181b1ffe12a2aa2adf01e65))

* specify pip3 ([`4611204`](https://github.com/eyeonus/Trade-Dangerous/commit/4611204fdd43bf7189c248bbf0f01ccda18c7748))

* Also ignore .venv ([`bb6ffc0`](https://github.com/eyeonus/Trade-Dangerous/commit/bb6ffc00355adcdf39c0d2c14159aa78250ad0df))

* Fix for --to breakage ([`79b5ec5`](https://github.com/eyeonus/Trade-Dangerous/commit/79b5ec586a42afced2dd55eb5134f83f74ee98bc))

* Fix -w and debug ([`479f8aa`](https://github.com/eyeonus/Trade-Dangerous/commit/479f8aa6ec8a597786f6cc764a955841c48e8bd8))

* Merged kfsone/tradedangerous into master ([`f5c2a63`](https://github.com/eyeonus/Trade-Dangerous/commit/f5c2a636dea5284e84196bb1a9e41c6637480cbc))

* Made &#39;rares&#39; command a shining beacon of How To ... ([`8301071`](https://github.com/eyeonus/Trade-Dangerous/commit/8301071d21d4678b9db5940cab3c1f8667decc1f))

* Catch the StopIteration error when a .csv file is empty ([`940f0d9`](https://github.com/eyeonus/Trade-Dangerous/commit/940f0d9a44c08e31ab9578b30e3b1c3b8eb03447))

* Additional change notes ([`7cb07e0`](https://github.com/eyeonus/Trade-Dangerous/commit/7cb07e0685cda53c58296f986b9f36bf5056d973))

* Clarification of &#39;local&#39; command arguments ([`cf813a7`](https://github.com/eyeonus/Trade-Dangerous/commit/cf813a7fdc91b8903eabcc357ecb43dd8da6bb1b))

* Merge branch &#39;trade-loading-refactor&#39;

Conflicts:
	tradecalc.py

v6.6.0 ([`6f38ad7`](https://github.com/eyeonus/Trade-Dangerous/commit/6f38ad78f039992ab08ecd43bb530e5f7f24178d))

* Stations from Path O&#39;Gen and a couple from kfsone ([`d0b3512`](https://github.com/eyeonus/Trade-Dangerous/commit/d0b35120aebeb58e9973aff3f26c3f82df0a6c7c))

* Merged kfsone/tradedangerous into master ([`af5c7c4`](https://github.com/eyeonus/Trade-Dangerous/commit/af5c7c4a6b63a72bf7749c8df7b814be41ff9244))

* Ordering fixes ([`d10c7d3`](https://github.com/eyeonus/Trade-Dangerous/commit/d10c7d3ec553f6aa27b1a787d4782904139c74aa))

* Merged in maddavo/tradedangerous (pull request #82)

System corrections, stations ([`248a408`](https://github.com/eyeonus/Trade-Dangerous/commit/248a408fea52d459a74e43a087ae3d15fa90a36d))

* Stellar Grid

Partition data into a map based on coordinates shifted 5 bits right (32 ly^3 cubes). This saves having to fetch system positions from the db and improves performance a whole bunch. ([`9c7bd60`](https://github.com/eyeonus/Trade-Dangerous/commit/9c7bd601394188d5bd6c570a18584f70c3e70b9f))

* Merged kfsone/tradedangerous into master ([`7fd7402`](https://github.com/eyeonus/Trade-Dangerous/commit/7fd740268fc942763485120f13047b14409d9e52))

* Station.csv edited online with Bitbucket ([`ce90680`](https://github.com/eyeonus/Trade-Dangerous/commit/ce906807af2a863a84d24b11b0cd18a813d29a86))

* Station.csv edited online with Bitbucket ([`af4dd80`](https://github.com/eyeonus/Trade-Dangerous/commit/af4dd80ac143bb86e05d395c863e90f342422bbd))

* Merged in jared_buntain/tradedangerous-jared (pull request #83)

Station update Jan 7th ([`83cf2a4`](https://github.com/eyeonus/Trade-Dangerous/commit/83cf2a4f1b6a83c124837dd2fec063549ac3668f))

* Merge branch &#39;master&#39; of https://bitbucket.org/kfsone/tradedangerous ([`7d9a889`](https://github.com/eyeonus/Trade-Dangerous/commit/7d9a8896261b8216eec5f8d7f6eed435cec2e9b5))

* Station update ([`ff04d60`](https://github.com/eyeonus/Trade-Dangerous/commit/ff04d600cacb973aca892028032ac0e110c1d8dd))

* Merged kfsone/tradedangerous into master ([`88f503b`](https://github.com/eyeonus/Trade-Dangerous/commit/88f503bbea31b3caf305f93e565c74c98b9be844))

* User station data ([`f452242`](https://github.com/eyeonus/Trade-Dangerous/commit/f452242150e9660ba966d662656640e1d208ee35))

* Fixes #120 &#39;K&#39; after stn/ls in units of 1000 ([`216b9fa`](https://github.com/eyeonus/Trade-Dangerous/commit/216b9faad11186929d207f9851995cd7ffdde147))

* Merged kfsone/tradedangerous into master ([`51a4313`](https://github.com/eyeonus/Trade-Dangerous/commit/51a43133c986f9ca48a0034117c3e4590f6cc8c2))

* System corrections + some station updates ([`b202d62`](https://github.com/eyeonus/Trade-Dangerous/commit/b202d62c913df0cfb29a89cd1b670692031e7581))

* Merged kfsone/tradedangerous into master ([`c8aa4ef`](https://github.com/eyeonus/Trade-Dangerous/commit/c8aa4ef5caa1b611592ed491827788e0ece71ac5))

* issue #112 use max_pad_size in run, buy, sell

Also added to rares and local

Based on code from Sarbian ([`4b5581e`](https://github.com/eyeonus/Trade-Dangerous/commit/4b5581e911261a872d627340c3e38e0f89175b8f))

* Merged kfsone/tradedangerous into master ([`4172d53`](https://github.com/eyeonus/Trade-Dangerous/commit/4172d53bddfe19ec0bbca0a59edd39c76a702113))

* Fix for handling of system name in station command ([`bb8d78b`](https://github.com/eyeonus/Trade-Dangerous/commit/bb8d78b0e3c593ebb5ea6d97473a6fd57ce97281))

* Fix using import without a filename ([`a1cd7bd`](https://github.com/eyeonus/Trade-Dangerous/commit/a1cd7bd43ad29800adb043e4b7bccd84c323ce41))

* Merge branch &#39;master&#39; of https://bitbucket.org/kfsone/tradedangerous ([`973e839`](https://github.com/eyeonus/Trade-Dangerous/commit/973e839eadddce36b10d23a96ad18a16a807380d))

* Initial performance refactor of trade loading. ([`da39f88`](https://github.com/eyeonus/Trade-Dangerous/commit/da39f88bcab3948adeafb05b525d3499aebbbf44))

* Fixing assorted cython obstacles ([`d48e376`](https://github.com/eyeonus/Trade-Dangerous/commit/d48e376aa91b4b5d5ad80fc4d7d9f2bfa65158d8))

* Ignore &#39;venv&#39; directory under trade for Python virtual environments ([`65a3fad`](https://github.com/eyeonus/Trade-Dangerous/commit/65a3fadede3ff8ddd16b0c6b6202f897815440aa))

* Merge branch &#39;master&#39; of https://bitbucket.org/kfsone/tradedangerous ([`58aaa0c`](https://github.com/eyeonus/Trade-Dangerous/commit/58aaa0cda53cea1f409549a1bdcbc112484f12d9))

* End of the night station update. Just a little one. ([`c73af31`](https://github.com/eyeonus/Trade-Dangerous/commit/c73af31f7c3be4c05b761089b7a7717ca1f9a4f9))

* Merged kfsone/tradedangerous into master ([`1fe4212`](https://github.com/eyeonus/Trade-Dangerous/commit/1fe4212dfa4723e32a7f8343ad4bfcee830f3f3a))

* Stabilized Station.csv using trade.py export ([`9f5c266`](https://github.com/eyeonus/Trade-Dangerous/commit/9f5c266f5661d233ca2c64e1c235d727cf79dc40))

* Better handling of --system and STN/SYS in station subcommand ([`30c6cbf`](https://github.com/eyeonus/Trade-Dangerous/commit/30c6cbf028f9ffe562af0c345893017846bc7b05))

* Merged in maddavo/tradedangerous (pull request #81)

Updates and correction additions ([`4785787`](https://github.com/eyeonus/Trade-Dangerous/commit/47857870e04efac0a4a99afaf6325fbd7b86d928))

* import_cmd.py edited online with Bitbucket ([`c06c570`](https://github.com/eyeonus/Trade-Dangerous/commit/c06c570bb1d4798d1a9902e204b8fd5406c66f2e))

* local_cmd.py edited online with Bitbucket ([`ffb1942`](https://github.com/eyeonus/Trade-Dangerous/commit/ffb194258acd27ade11a6d318ce198ace68f5563))

* import_cmd.py edited online with Bitbucket ([`0af4f63`](https://github.com/eyeonus/Trade-Dangerous/commit/0af4f633fca6179a2243c7b9063a64d911a61b16))

* export_cmd.py edited online with Bitbucket ([`0bfc02b`](https://github.com/eyeonus/Trade-Dangerous/commit/0bfc02b3b4f3b2bb39f1a10550ef4ab36c7fe15f))

* Updates and corrections ([`93678d3`](https://github.com/eyeonus/Trade-Dangerous/commit/93678d38d17b93780a72d0a9e6ba26c16ca05019))

* Loaded up station corrections table ([`a906826`](https://github.com/eyeonus/Trade-Dangerous/commit/a90682635ec8e49e8bbf5840821842585f2e6bd8))

* Merged kfsone/tradedangerous into master ([`b9c003c`](https://github.com/eyeonus/Trade-Dangerous/commit/b9c003c5df97cd60a5bdae2b86d76b48fd2e0546))

* CHANGES.txt edited online with Bitbucket ([`4099eda`](https://github.com/eyeonus/Trade-Dangerous/commit/4099eda7abb4f3ee435335e8fe749c30afe39249))

* Quick add of several new stations ([`fdebe2b`](https://github.com/eyeonus/Trade-Dangerous/commit/fdebe2bad613c10de4c061d7d8bba74234932365))

* There&#39;s a space in George Lucas ([`6764c9e`](https://github.com/eyeonus/Trade-Dangerous/commit/6764c9ea52781bdecdeb0ae40b5175f0c3a174cc))

* madupload now takes an argument (filename) ([`a2240fc`](https://github.com/eyeonus/Trade-Dangerous/commit/a2240fce00d4029a824d65ccc8791b5649a299ea))

* Data changes ([`12a7b15`](https://github.com/eyeonus/Trade-Dangerous/commit/12a7b15945cba042a3998dc99940c5502d2d6373))

* Merged in sebarkh/tradedangerousstations (pull request #79)

Added stations in LAZDONES system ([`004668f`](https://github.com/eyeonus/Trade-Dangerous/commit/004668f3a4dc34539b065e8b6245f9eeb4012786))

* Merged in jared_buntain/tradedangerous-jared (pull request #78)

Adding stations from Jared: Jan 4th 2015 ([`21b597c`](https://github.com/eyeonus/Trade-Dangerous/commit/21b597c6eb4f53c6a16f95bc1b84d925549ee02a))

* Added stations in LAZDONES system ([`798e2bc`](https://github.com/eyeonus/Trade-Dangerous/commit/798e2bc0be01c2dab0ac08fc5663b7856c77f6ce))

* Merge branch &#39;master&#39; of https://bitbucket.org/kfsone/tradedangerous

Conflicts:
	data/Station.csv ([`07308b2`](https://github.com/eyeonus/Trade-Dangerous/commit/07308b29d10ba6c2863ff402b79303d42af47e88))

* Station updates from master ([`4279bf2`](https://github.com/eyeonus/Trade-Dangerous/commit/4279bf2cd173d88931d915be9344912743092d65))

* Merged kfsone/tradedangerous into master ([`0a15838`](https://github.com/eyeonus/Trade-Dangerous/commit/0a158388f60ce80bab178774c96b347788cdb804))

* Data ([`5f1928c`](https://github.com/eyeonus/Trade-Dangerous/commit/5f1928c4f431fac8d7ad6fbaa00af3f9b6e21675))

* Fix error reporting unknown system during add station ([`3225053`](https://github.com/eyeonus/Trade-Dangerous/commit/3225053c5b77b92c49fdd91847166550bb2e4323))

* Station data ([`576c5ab`](https://github.com/eyeonus/Trade-Dangerous/commit/576c5ab75bd628f63a07fc5c387d8a8b0555a752))

* Merged kfsone/tradedangerous into master ([`abb7840`](https://github.com/eyeonus/Trade-Dangerous/commit/abb7840202b6e4c3ecc46dc62861debb71b8efcf))

* Station.csv edited online with Bitbucket ([`560895d`](https://github.com/eyeonus/Trade-Dangerous/commit/560895d8ffda44beaab28fcecca4adcf8e9900a0))

* Station.csv created online with Bitbucket ([`b4f4cec`](https://github.com/eyeonus/Trade-Dangerous/commit/b4f4ceccff1b8c95692f01c941025285845e3568))

* Station.csv deleted online with Bitbucket ([`bc81b59`](https://github.com/eyeonus/Trade-Dangerous/commit/bc81b592bafea224ea3ea4098f4cdf53f6ac24b2))

* Station.csv edited online with Bitbucket ([`1c7448a`](https://github.com/eyeonus/Trade-Dangerous/commit/1c7448a60c2b52e4dd4334e7791f503882029119))

* Data import ([`84ad331`](https://github.com/eyeonus/Trade-Dangerous/commit/84ad3316124aabb30523121b8ab80126e61f11d8))

* Fix for addLocalStation with lowercase arguments ([`9cf2a1f`](https://github.com/eyeonus/Trade-Dangerous/commit/9cf2a1f1bf97f0658fbf06b60c66f842286bc9ae))

* Merged kfsone/tradedangerous into master ([`c4a7dd6`](https://github.com/eyeonus/Trade-Dangerous/commit/c4a7dd62b1bfb7e8c14a2913b497f67132235aec))

* Big station import ([`ff8900b`](https://github.com/eyeonus/Trade-Dangerous/commit/ff8900b4ceccece671e40f884238500dac9cc91a))

* Backed off similarity matching ([`53f93fd`](https://github.com/eyeonus/Trade-Dangerous/commit/53f93fdaae21a254159967a8714cdf3edbf77a47))

* Fix for --no-export ([`c527707`](https://github.com/eyeonus/Trade-Dangerous/commit/c527707d0b25c7c388cb3c3af1aad8d91d5f8810))

* Adding stations from Jared: Jan 4th 2015 ([`4809eae`](https://github.com/eyeonus/Trade-Dangerous/commit/4809eaee57ac757ebeb9ee01f4de40e63070a363))

* Revert &#34;Station updates&#34;

This reverts commit 1e86b92f36c0e3952b670e4d00ef06caff213727. ([`f678cd4`](https://github.com/eyeonus/Trade-Dangerous/commit/f678cd4da3f01044b9989ffa51539a5ce9444a16))

* Merge remote-tracking branch &#39;origin/master&#39;

Conflicts:
	data/Station.csv ([`9fc4740`](https://github.com/eyeonus/Trade-Dangerous/commit/9fc47408dc228aec2f3cb8814763ce1aea98d0bd))

* Station updates ([`1e86b92`](https://github.com/eyeonus/Trade-Dangerous/commit/1e86b92f36c0e3952b670e4d00ef06caff213727))

* Merged kfsone/tradedangerous into master ([`b66efc6`](https://github.com/eyeonus/Trade-Dangerous/commit/b66efc6bf1a61401a4962e0f8213caa5808fb986))

* Fixes for the station command ([`efc0c0c`](https://github.com/eyeonus/Trade-Dangerous/commit/efc0c0cfb03cf64f52135fd7f319aba5e6ac3dd1))

* Data fixes ([`69d14df`](https://github.com/eyeonus/Trade-Dangerous/commit/69d14df27062c5760831563a5f64b357b13f5972))

* fix for station command ([`e0a9db0`](https://github.com/eyeonus/Trade-Dangerous/commit/e0a9db0a32d1c74c821252a7a2ae60d598fb9d05))

* Added &#34;station&#34; sub-command ([`962ad00`](https://github.com/eyeonus/Trade-Dangerous/commit/962ad0054e79babd29b9fad6aa940545dc63a057))

* Cleanup ([`f5fedb9`](https://github.com/eyeonus/Trade-Dangerous/commit/f5fedb978f6dfc6f8d370f9b003c1adc8262abc0))

* Functions to get average station trading prices ([`4fb503b`](https://github.com/eyeonus/Trade-Dangerous/commit/4fb503bdf56bf169d9bef8dc4c9e364de76eb004))

* Fixes for addLocalStation and updateLocalStation ([`0d1acf0`](https://github.com/eyeonus/Trade-Dangerous/commit/0d1acf0db0444f377920053dc5999c95ab715787))

* If you export csv files, you don&#39;t force a cache rebuild. ([`fc603e0`](https://github.com/eyeonus/Trade-Dangerous/commit/fc603e01475a2468a5f87502820d43c4bcf6f6ae))

* Merged kfsone/tradedangerous into master ([`89953d8`](https://github.com/eyeonus/Trade-Dangerous/commit/89953d8e929dc4204e4351986478a5faa100bcda))

* Merged in milindur/tradedangerous (pull request #76)

updates to ship vendors ([`564d67c`](https://github.com/eyeonus/Trade-Dangerous/commit/564d67c998c1f04dea5bef735c49edc608ff9fc2))

* Merged in maddavo/tradedangerous (pull request #77)

Shipvendor updates ([`69dac57`](https://github.com/eyeonus/Trade-Dangerous/commit/69dac572a223f7574ce2bc58f3498ecb2a937244))

* Fixed clipper ([`0d2892d`](https://github.com/eyeonus/Trade-Dangerous/commit/0d2892d0bbf573c1df8ac2d10af56f87f6074b99))

* Merged kfsone/tradedangerous into master ([`a0a7ef2`](https://github.com/eyeonus/Trade-Dangerous/commit/a0a7ef29d477fecffab767fb7d9e88cfd70cd9f6))

* updates to ship vendors ([`f10128f`](https://github.com/eyeonus/Trade-Dangerous/commit/f10128f1e554905bd664c074ffa67d251aed6c2e))

* Export won&#39;t force a cache-rebuild again ([`81205bd`](https://github.com/eyeonus/Trade-Dangerous/commit/81205bdc01b2a3712cfb7bc994bac44db1d02856))

* Presentation ([`2e82d3b`](https://github.com/eyeonus/Trade-Dangerous/commit/2e82d3bff8061ce6edd5f8b36e6dbdb4a1f51c4f))

* Added Imperial Clipper ([`eea4b45`](https://github.com/eyeonus/Trade-Dangerous/commit/eea4b457c3e1d8a488911beb2b1c8a26a9099d6d))

* Merged kfsone/tradedangerous into master ([`fe31566`](https://github.com/eyeonus/Trade-Dangerous/commit/fe31566f3044d8e4d731aacaf4d64a48ddc5ecbb))

* Load a 1:1 station trade list ([`415d163`](https://github.com/eyeonus/Trade-Dangerous/commit/415d163f420c2f4ed6e78d76194ccc07e08974f2))

* Sharon Lee has a distance ([`723880f`](https://github.com/eyeonus/Trade-Dangerous/commit/723880ffafabe90edf14b2e8eb80ad353b261b06))

* Less noisy import stats ([`f9b53a0`](https://github.com/eyeonus/Trade-Dangerous/commit/f9b53a09dfd0179e02aa5cdec5ec38b27ec8684a))

* Handle absence of credits/insurance values in tdcalc ([`19488f3`](https://github.com/eyeonus/Trade-Dangerous/commit/19488f3b1d05ad1a3018c246988ba976c9ad9133))

* Another 137 stations ([`1941493`](https://github.com/eyeonus/Trade-Dangerous/commit/194149371df64ae29fc5cb3a9910ce6fb0937ee7))

* Another 138 stations ([`c42494c`](https://github.com/eyeonus/Trade-Dangerous/commit/c42494c2aa8547d4a64dfa6992e8fa7424a8c619))

* 132 new stations ([`a980fe5`](https://github.com/eyeonus/Trade-Dangerous/commit/a980fe5fb062a93f6b7ca89ce80b2e119b8f00d7))

* Data credit ([`2b267b7`](https://github.com/eyeonus/Trade-Dangerous/commit/2b267b7d77efb70230f829161e6ee5559d7a5c94))

* Station updates from Path O&#39;Gen ([`56dbf88`](https://github.com/eyeonus/Trade-Dangerous/commit/56dbf88f3eb7a829c75b3624a9372c30905d1df1))

* Removed &#39;Menoel mines&#39; ([`145c3a9`](https://github.com/eyeonus/Trade-Dangerous/commit/145c3a9ee8df42e2110a7be1441c29d385ead284))

* Merged in maddavo/tradedangerous (pull request #74)

Stations ([`e3aff52`](https://github.com/eyeonus/Trade-Dangerous/commit/e3aff521f270862e8e3d126ae3fe45d0b20b80b6))

* Station updates ([`dd15ff1`](https://github.com/eyeonus/Trade-Dangerous/commit/dd15ff144cc178363be1aca62bcc888466907fae))

* Merged kfsone/tradedangerous into master ([`6f48757`](https://github.com/eyeonus/Trade-Dangerous/commit/6f48757ddf034d6e5c20b451b6177e87391c3a1c))

* Revert &#34;Updates&#34;

This reverts commit b0bbb7db82a0d86a46f7f040be12bb730159a57e. ([`0eeb809`](https://github.com/eyeonus/Trade-Dangerous/commit/0eeb8090969bcbc01c5866834425fa59f7bf8d7a))

* Updates ([`b0bbb7d`](https://github.com/eyeonus/Trade-Dangerous/commit/b0bbb7db82a0d86a46f7f040be12bb730159a57e))

* Additional Data ([`b8d6c2a`](https://github.com/eyeonus/Trade-Dangerous/commit/b8d6c2a8a21212806d30db1bf488da1d8c0cda6e))

* Bast to Zaonce data ([`0402a25`](https://github.com/eyeonus/Trade-Dangerous/commit/0402a2534f852fc5359fe2c5176114bdd1823482))

* Additional data ([`268077c`](https://github.com/eyeonus/Trade-Dangerous/commit/268077cf3fef4416f043a9c56c29279a5b6b2a1e))

* Additional data ([`3510015`](https://github.com/eyeonus/Trade-Dangerous/commit/3510015a84fad8286c1c2184802e3007bde8d2d8))

* Data ([`8ae0096`](https://github.com/eyeonus/Trade-Dangerous/commit/8ae0096c4b27a677d19026987448758343b1d6e9))

* Merged kfsone/tradedangerous into master ([`af5c5f9`](https://github.com/eyeonus/Trade-Dangerous/commit/af5c5f90c8392d44c791562ee427367ab386290c))

* Fix for age/days display in nav command ([`5efcbf4`](https://github.com/eyeonus/Trade-Dangerous/commit/5efcbf44c0971fc48f533043620737bc90bc68a2))

* Merged in bgol/tradedangerous/devel (pull request #73)

updated argument lists to current version (removed short versions) ([`63d3fc3`](https://github.com/eyeonus/Trade-Dangerous/commit/63d3fc32ae0307f7a8995931b7079ab258245a57))

* README updates and rares -r fix ([`f5fe2d3`](https://github.com/eyeonus/Trade-Dangerous/commit/f5fe2d39a4d77623cd3d9911df25ffaa12e0f948))

* updated argument lists to current version (removed short versions) ([`4ba559b`](https://github.com/eyeonus/Trade-Dangerous/commit/4ba559b5f483d4b9ff49d6b69388712af27e3080))

* Fix for system/station matching ... system ([`c68f52b`](https://github.com/eyeonus/Trade-Dangerous/commit/c68f52b638598715325388a9b85bb111ec5e1ea1))

* Merged in bgol/tradedangerous/data (pull request #72)

data update ([`ec4f5f8`](https://github.com/eyeonus/Trade-Dangerous/commit/ec4f5f82cee3fe1692913cea00b466118563743c))

* Import ([`3f6c0b6`](https://github.com/eyeonus/Trade-Dangerous/commit/3f6c0b64809f1a30a42e93eb65d684783957439b))

* Bast bm ([`1f07d95`](https://github.com/eyeonus/Trade-Dangerous/commit/1f07d958f1986a3d437b6c1e6af6b637e2376947))

* Bast ([`26625f6`](https://github.com/eyeonus/Trade-Dangerous/commit/26625f628f55a163006b76e63c085c5d5d893fea))

* data update ([`b948ff2`](https://github.com/eyeonus/Trade-Dangerous/commit/b948ff2a6df73fd585670acff557f76da43c6a83))

* Merged kfsone/tradedangerous into master ([`64452df`](https://github.com/eyeonus/Trade-Dangerous/commit/64452df0550bd353680e3a284c687b6cc2414788))

* LFT 1421 data ([`ed2789a`](https://github.com/eyeonus/Trade-Dangerous/commit/ed2789a6cdf28e3f888e745fd163736ff46809c9))

* Added --reverse option to rares command ([`d40ac56`](https://github.com/eyeonus/Trade-Dangerous/commit/d40ac5647ebe0f9a554d9e182580f033e2de2238))

* Data ([`8ecb5df`](https://github.com/eyeonus/Trade-Dangerous/commit/8ecb5df2c76f40f597ec8bdc4deee6d204d13687))

* Added --stations option to nav command ([`ef652a0`](https://github.com/eyeonus/Trade-Dangerous/commit/ef652a0e99ab5d5614e481b3a7176e3da71822a0))

* Show stnLS and pad size for rares ([`09c01c6`](https://github.com/eyeonus/Trade-Dangerous/commit/09c01c603bedc835d4d645fcb75ee0f2810d4296))

* Support partial command name lookup

e.g.
  trade.py rares
  trade.py rare
  trade.py rar
  trade.py ra
  trade.py r       # ambiguous: &#39;run&#39; or &#39;rares&#39; ([`594ee37`](https://github.com/eyeonus/Trade-Dangerous/commit/594ee37845e926509e78d352ed4caad8f03db4af))

* More stations ([`fe038c7`](https://github.com/eyeonus/Trade-Dangerous/commit/fe038c7e392a686bb55a258343b93edab5736d5b))

* Warnings are warnings ([`bc52485`](https://github.com/eyeonus/Trade-Dangerous/commit/bc52485f5162b2b4fb018e3b95d21173d716a77d))

* CHANGES ([`fac587a`](https://github.com/eyeonus/Trade-Dangerous/commit/fac587a4b4375ee8e7421af18081a99cbaf53d47))

* Station updates ([`afc4ffc`](https://github.com/eyeonus/Trade-Dangerous/commit/afc4ffcab1e4b061acd4b7a4eae3bd9767b42eb7))

* Deprecated and Deleted key checks no-longer abort .csv parsing when --ignore-unknown (-i) is set ([`44b8f74`](https://github.com/eyeonus/Trade-Dangerous/commit/44b8f74ff7a2200d436b1bf1e5e2bfa2273ccad8))

* Maddavo plugin improvements:

Switched to NOTE for quiescable output,
--opt=skipdl will force a parse,
Added some DEBUG lines ([`e7b41c0`](https://github.com/eyeonus/Trade-Dangerous/commit/e7b41c09aa9a2a0ddea3ea5d8169dacd2f71cbbd))

* Added TradeEnv.NOTE ([`68b6767`](https://github.com/eyeonus/Trade-Dangerous/commit/68b67674bbc0f0ff82978c3db332865a8609ecf0))

* Local --ages was deprecated; removed ([`de42271`](https://github.com/eyeonus/Trade-Dangerous/commit/de4227122a2c395b9012d70fcbdd03123e682428))

* Stats on import ([`46686cb`](https://github.com/eyeonus/Trade-Dangerous/commit/46686cb08f0d39c95b433e0dcf1e170ce6ee2190))

* Data from maddavos ([`7575f41`](https://github.com/eyeonus/Trade-Dangerous/commit/7575f41020b03bd91dba6c25c8c23cc6098d1a08))

* Station/Rare data ([`13de5ef`](https://github.com/eyeonus/Trade-Dangerous/commit/13de5ef97f9540822e33d633cc015c5dab9332f7))

* Data ([`bee541e`](https://github.com/eyeonus/Trade-Dangerous/commit/bee541edc4342a0e49ce93b45756bb66335e505f))

* Merged in bgol/tradedangerous/data (pull request #71)

data update ([`d6e103f`](https://github.com/eyeonus/Trade-Dangerous/commit/d6e103f3a96a39eb34ff0b5447f254b558bfb844))

* data update ([`1c67026`](https://github.com/eyeonus/Trade-Dangerous/commit/1c67026d330364d1d688d2bd93db389509335ed4))

* Merged kfsone/tradedangerous into master ([`0b0514a`](https://github.com/eyeonus/Trade-Dangerous/commit/0b0514a980e25826ef2368581f051ecf1c55827c))

* Added &#39;rare&#39; sub-command ([`97046dc`](https://github.com/eyeonus/Trade-Dangerous/commit/97046dc4565b512a769617e0abcc7a9424ca04bc))

* Fix RareItem name function ([`cc6caf1`](https://github.com/eyeonus/Trade-Dangerous/commit/cc6caf1326ec11d597d2c99eb9d5adb1d70c3b54))

* Fix RareItem name function ([`5623481`](https://github.com/eyeonus/Trade-Dangerous/commit/5623481ba6fedc3ecf91c85b6ab3f4b80468d3fd))

* RareItems should have a station, not a source ([`3d169e3`](https://github.com/eyeonus/Trade-Dangerous/commit/3d169e3a4cba6e5a1661d25ce59d2ec7f852e152))

* Load RareItems on startup ([`2a9cf3a`](https://github.com/eyeonus/Trade-Dangerous/commit/2a9cf3aaec7fe776ed236d6ddc201db180ebc7a6))

* Added RareItem table ([`a8ea9fc`](https://github.com/eyeonus/Trade-Dangerous/commit/a8ea9fcadf149743cf64c145b7eb05fb9a9b6b3b))

* Capitalized SYSTEM names

- tdb.systemByName is now upper case,
- System names are now coerced into upper case,
- Imported lots of stars from EDStarCoordinator,
- Manually added lots of stations, ([`6b3ad86`](https://github.com/eyeonus/Trade-Dangerous/commit/6b3ad8621fce0aadb7f49888d14d16c35db23f05))

* Maddavo data ([`b521578`](https://github.com/eyeonus/Trade-Dangerous/commit/b52157844fbe4c1755374dfa0836abce9ac844b0))

* Data from Jared Buntain ([`314a383`](https://github.com/eyeonus/Trade-Dangerous/commit/314a383e32f20c4c23305a740615e6ea03c8f7a1))

* Fixes #115 removed speculative recovery of stock levels ([`ccf4066`](https://github.com/eyeonus/Trade-Dangerous/commit/ccf4066b2b2c697f98ff72bf4038559c116f001c))

* Merged in bgol/tradedangerous/devel (pull request #70)

data update ([`83e9d60`](https://github.com/eyeonus/Trade-Dangerous/commit/83e9d60408a3b7bc71a0e37f6a8e1d930ed8f47c))

* data update ([`4ed5f13`](https://github.com/eyeonus/Trade-Dangerous/commit/4ed5f130c403699a3538f56a63dcee69dac2bb49))

* Merged kfsone/tradedangerous into master ([`f865874`](https://github.com/eyeonus/Trade-Dangerous/commit/f865874576b1608d236e0a378ed321d9919af623))

* Data ([`8b770ff`](https://github.com/eyeonus/Trade-Dangerous/commit/8b770ff0d29ac2d81b4e7f170337bc3354c204e8))

* Minor station changes ([`ea186db`](https://github.com/eyeonus/Trade-Dangerous/commit/ea186db5b26da20dd2debf3a30eb8842f2e97cf5))

* Made madupload script executable ([`6db1c3f`](https://github.com/eyeonus/Trade-Dangerous/commit/6db1c3f724f78b1e227dd09c39c2a26db8a2690b))

* Added experimental &#39;upload to mad&#39; (misc/madupload.py) ([`a9de85a`](https://github.com/eyeonus/Trade-Dangerous/commit/a9de85af2bafb2c09dacb8d4799fe899079e4671))

* wording ([`cee6a1b`](https://github.com/eyeonus/Trade-Dangerous/commit/cee6a1b3503cae29f3e0c744c942912664635957))

* Better explanation of run errors ([`b2228b7`](https://github.com/eyeonus/Trade-Dangerous/commit/b2228b761b51e3ee4e520bdabf949b915c116c01))

* Make import accept &#39;-&#39; as an alias for &#39;stdin&#39; ([`881a967`](https://github.com/eyeonus/Trade-Dangerous/commit/881a967e313047dd7cfc954624d24e3bd99a3069))

* Merged kfsone/tradedangerous into master ([`3bb9f2b`](https://github.com/eyeonus/Trade-Dangerous/commit/3bb9f2bfe868e2985b6751562a1c55325b0fb923))

* Change log ([`8a21ed0`](https://github.com/eyeonus/Trade-Dangerous/commit/8a21ed055b2b68865228351e76dc2a51e9fce56a))

* fixed #114 link-ly wasn&#39;t typed as float ([`436b8af`](https://github.com/eyeonus/Trade-Dangerous/commit/436b8afa051f46ac3b1d01680fccbf16350b578a))

* &#34;nav&#34; now supports --via ([`79160af`](https://github.com/eyeonus/Trade-Dangerous/commit/79160affe2bf5699dbb8bc7cbeb7dba58eea759c))

* Station updates ([`0edd380`](https://github.com/eyeonus/Trade-Dangerous/commit/0edd380ab5407011132f10a6326d8bf6c7737143))

* bash script tweaks ([`d404247`](https://github.com/eyeonus/Trade-Dangerous/commit/d404247fbc907cd39f01f01710505128e54fd1cb))

* Presentation of unrecognized entities ([`c6399d3`](https://github.com/eyeonus/Trade-Dangerous/commit/c6399d36f28ab829419eaa715f9dee0fb169dcc4))

* Stations ([`a1adea9`](https://github.com/eyeonus/Trade-Dangerous/commit/a1adea99081a84f62effd522e7c86759aa98ed70))

* Changes ([`e627379`](https://github.com/eyeonus/Trade-Dangerous/commit/e6273792ea11acbe358b72691dd90b4e0f8a8587))

* Merged in bgol/tradedangerous/devel (pull request #69)

data update ([`cdc667e`](https://github.com/eyeonus/Trade-Dangerous/commit/cdc667e4f48864d4430870e5683b6c4ea7120f31))

* Merged in OpenSS/tradedangerous (pull request #68)

Add &#34;Quick Update&#34; to windows bat file now that the maddavo plugin supports timestamps ([`cf6e554`](https://github.com/eyeonus/Trade-Dangerous/commit/cf6e55429f3ff7253be1664c8d946ff6e0ba854e))

* data update ([`9e0d943`](https://github.com/eyeonus/Trade-Dangerous/commit/9e0d9432d9a31e305d458e441dfa10a780258c78))

* Merged kfsone/tradedangerous into master ([`51754df`](https://github.com/eyeonus/Trade-Dangerous/commit/51754dfb9f2603069ddc3b649aebc94e242ad87b))

* Add &#34;Quick Update&#34; to windows bat file now that the maddavo plugin supports timestamps ([`e6e2392`](https://github.com/eyeonus/Trade-Dangerous/commit/e6e23929b225ba12c9aac8a8e48ca6d24015f6e8))

* Fixes for Windows&#39; trade.bat ([`19b053a`](https://github.com/eyeonus/Trade-Dangerous/commit/19b053aca57886f16cb86bdf0be262cc3cc9cb13))

* More stations ([`34cc389`](https://github.com/eyeonus/Trade-Dangerous/commit/34cc3897d8a078660181bd9387db6de724de5265))

* presentation of data age in run ([`10f3297`](https://github.com/eyeonus/Trade-Dangerous/commit/10f329748d1c8f4434728017910ae9b44d550393))

* Station distances ([`90087f8`](https://github.com/eyeonus/Trade-Dangerous/commit/90087f8db0a3c2372f3e820d44e8627f67a08b2c))

* buy, sell, nav and local now have consistent presentation of each station&#39;s distance from the star, labelled &#34;StnLs&#34;, while interstellar distances are labelled &#34;DistLy&#34;. ([`4aecb85`](https://github.com/eyeonus/Trade-Dangerous/commit/4aecb852dee89cfc642729b3924fdddef1d961cb))

* Change log ([`8bacbdc`](https://github.com/eyeonus/Trade-Dangerous/commit/8bacbdc1752ab270741a9148597eecac40eb52ec))

* Future work ([`b547052`](https://github.com/eyeonus/Trade-Dangerous/commit/b547052c8481862056e83c37ae7420b2d5135a84))

* Removed legacy --supply, cleaned up update_cmd code ([`a6f2929`](https://github.com/eyeonus/Trade-Dangerous/commit/a6f29296a41e3a2ceafb33a0e3beeadc6d31cbf8))

* Station updates ([`7f8eef3`](https://github.com/eyeonus/Trade-Dangerous/commit/7f8eef352e5b2c81699c27988546e08d1fb96155))

* Better lsp penalty curves ([`11da8e0`](https://github.com/eyeonus/Trade-Dangerous/commit/11da8e0be2015fa3342c6c27a22d8c5d16219665))

* misc/add-station no-csv and -u

misc/add-station no-longer writes to or reads from the .csv file,
misc/add-station now has a -u option for updating entries ([`339b41b`](https://github.com/eyeonus/Trade-Dangerous/commit/339b41b37c5a772b708f302c0629348e0b0348b5))

* Stations ([`f87dfa4`](https://github.com/eyeonus/Trade-Dangerous/commit/f87dfa45ecbd13a94917cf39e9d5c2a3c24a4439))

* Tiny cleanup of maddavo plugin ([`c0052d2`](https://github.com/eyeonus/Trade-Dangerous/commit/c0052d253e41eef4921d148cb668f70bf7cb15ae))

* Merged kfsone/tradedangerous into master ([`14d8257`](https://github.com/eyeonus/Trade-Dangerous/commit/14d8257917c3dea929d321b18668894854df2783))

* Adjusted stations ([`4980ee5`](https://github.com/eyeonus/Trade-Dangerous/commit/4980ee5f482baaa8f829ed672f44ffd3d837f78c))

* Merged in maddavo/tradedangerous (pull request #67)

Station Updates ([`5ccb633`](https://github.com/eyeonus/Trade-Dangerous/commit/5ccb63301afb2ddeeaffae5353ed263686a3258f))

* Updates ([`09ffa78`](https://github.com/eyeonus/Trade-Dangerous/commit/09ffa783b9119bed3265e96dac01d2d2de8fd9c3))

* Merged kfsone/tradedangerous into master ([`14319ae`](https://github.com/eyeonus/Trade-Dangerous/commit/14319ae70b7a73e92269a616963272a21cf53eac))

* Merged kfsone/tradedangerous into master ([`e81c0a8`](https://github.com/eyeonus/Trade-Dangerous/commit/e81c0a886f94542bd849814dbf312b21560bc270))

* Data ([`bd3c6c5`](https://github.com/eyeonus/Trade-Dangerous/commit/bd3c6c500083a210be4803305aaedb5ca482a74a))

* fixes #111 import not rebuilding cache

This applies primarily to the non-plugin default behavior. ([`56de87b`](https://github.com/eyeonus/Trade-Dangerous/commit/56de87b8bd6fb822d0e5a485c31f696c1a35e5de))

* Penalize really long ls distances more heavily, change default lsp to 0.6 ([`bcbab76`](https://github.com/eyeonus/Trade-Dangerous/commit/bcbab76db6ed540cd2dd1e5193ce056a59c10f87))

* Data ([`9d9f5c4`](https://github.com/eyeonus/Trade-Dangerous/commit/9d9f5c48df381a1306ed462314ce95df59825ff3))

* CHANGES text for previous update ([`fe65601`](https://github.com/eyeonus/Trade-Dangerous/commit/fe65601da07f68d4699a0610c0c20589cbae5819))

* Added prices-2 support to maddavo plugin

Also made the maddavo plugin generally more temporarly aware so it can avoid large downloads frequently. ([`016ca39`](https://github.com/eyeonus/Trade-Dangerous/commit/016ca3931461c35a541ad2479905d513b0e5760e))

* Added a &#39;shebang&#39; option to download()

This lets you check the first line of the data received (the shebang) ([`f7c0385`](https://github.com/eyeonus/Trade-Dangerous/commit/f7c0385cc1a58cd12ac3ebb9b2736212e5a73521))

* Merged in orphu/tradedangerous/updates (pull request #66)

Some shipyard info. ([`744126c`](https://github.com/eyeonus/Trade-Dangerous/commit/744126c3e726321fe120d100b3463c2feea73404))

* Meredith City shipyards. ([`c57efbf`](https://github.com/eyeonus/Trade-Dangerous/commit/c57efbf9b3695aaa9a71e77191fa03cbd7e76c69))

* Merge branch &#39;master&#39; into updates ([`2f061c8`](https://github.com/eyeonus/Trade-Dangerous/commit/2f061c88572798367289930faf9341006a588bbd))

* Jameson Memorial shipyard. ([`0f46546`](https://github.com/eyeonus/Trade-Dangerous/commit/0f465467147f30d88c8815df1d45b135d28807ec))

* Merged kfsone/tradedangerous into master ([`f6cf721`](https://github.com/eyeonus/Trade-Dangerous/commit/f6cf72167b88066e7a29b2ca845c1394df1735ef))

* Merged in bgol/tradedangerous/devel (pull request #65)

more stations and shipyards ([`335d024`](https://github.com/eyeonus/Trade-Dangerous/commit/335d02453031c1ecdfe0fe014dcc42cbe83db17e))

* Merged in orphu/tradedangerous/station_updates (pull request #64)

Add a few stations, and round distances to int. ([`025bf70`](https://github.com/eyeonus/Trade-Dangerous/commit/025bf70ad54d275a2b0b306f573e2a1e1aa5ee4d))

* Station info for Fong Wang. ([`e516ff1`](https://github.com/eyeonus/Trade-Dangerous/commit/e516ff1d6c1ae7f1d8905ce481f5eb3e6c2c99bf))

* Station data for Eravarenth. ([`0aab9d7`](https://github.com/eyeonus/Trade-Dangerous/commit/0aab9d71570addcb444ac764496c777da4d92e83))

* Stataion info for Bunda. ([`14c2065`](https://github.com/eyeonus/Trade-Dangerous/commit/14c2065af0a292f11467fde3dbc87132f73d5bda))

* Station data for Skeggiko O. ([`bd623dd`](https://github.com/eyeonus/Trade-Dangerous/commit/bd623dd50452b117ca9858b314e28a09f5704041))

* Station info for V886 Centauri. ([`6a38e66`](https://github.com/eyeonus/Trade-Dangerous/commit/6a38e66081def9ac42780f54cc3816b79808a204))

* Station data for LFT 926. ([`80ed088`](https://github.com/eyeonus/Trade-Dangerous/commit/80ed08864658235b735cbbd46f6664621b3a3ccb))

* more stations and shipyards ([`0fb254a`](https://github.com/eyeonus/Trade-Dangerous/commit/0fb254af214f1dda0915d736dacee203b68f57ac))

* Additional station data for Nuenets. ([`519e22a`](https://github.com/eyeonus/Trade-Dangerous/commit/519e22a9e6bcaf3e0cd9123439f5c2f6e39ba518))

* Add a few stations, and round distances to int. ([`82ae533`](https://github.com/eyeonus/Trade-Dangerous/commit/82ae533e752ef58fed84dafee3fd237683d75cf9))

* Merge branch &#39;master&#39; into station_updates

Conflicts:
	data/Station.csv ([`67fbc22`](https://github.com/eyeonus/Trade-Dangerous/commit/67fbc22924667d6a86c0667571ba5a42048ebb03))

* A few stations ([`e8f05f8`](https://github.com/eyeonus/Trade-Dangerous/commit/e8f05f8864b976857e3b6634ed258c1a46cbfea5))

* Merged kfsone/tradedangerous into master ([`f7da999`](https://github.com/eyeonus/Trade-Dangerous/commit/f7da99974c07f1ee93128fc4e16308d939507adc))

* More data ([`3edd1df`](https://github.com/eyeonus/Trade-Dangerous/commit/3edd1df3d6be32570667e053b605fa37a5d1f2ad))

* Sol Data ([`8a9fd71`](https://github.com/eyeonus/Trade-Dangerous/commit/8a9fd71786c70c739f32debee4dea8225013c875))

* Another stack of stations ([`49c1792`](https://github.com/eyeonus/Trade-Dangerous/commit/49c17923819171edddb99f587d231cc872122453))

* Data ([`a438f16`](https://github.com/eyeonus/Trade-Dangerous/commit/a438f16aebc2c86beb46869fa930ded1f4321286))

* Additional debug ([`6bf828a`](https://github.com/eyeonus/Trade-Dangerous/commit/6bf828a8947383a8eab2245380f902ed143c6e9d))

* Merged kfsone/tradedangerous into master ([`f8ae4be`](https://github.com/eyeonus/Trade-Dangerous/commit/f8ae4beef41b8dc902f7b20d6b953cefbb46b2c9))

* Merged in bgol/tradedangerous/devel (pull request #63)

more stations and shipyards ([`54b0c33`](https://github.com/eyeonus/Trade-Dangerous/commit/54b0c330c55e4c33a6e032a441231d6d5d426bf2))

* more stations and shipyards ([`0321eea`](https://github.com/eyeonus/Trade-Dangerous/commit/0321eea5237adf731ea093ad01d460b6a166756c))

* Added --opt=help for plugins ([`3ca4717`](https://github.com/eyeonus/Trade-Dangerous/commit/3ca47176c7ce4668859f43159262e17c008d3f4f))

* Made it more obvious that warnings are warnings during import ([`9e7d483`](https://github.com/eyeonus/Trade-Dangerous/commit/9e7d48346b75dcd5330b0abefbc430270f444cd8))

* Fixup for maddavo data ([`1ad582d`](https://github.com/eyeonus/Trade-Dangerous/commit/1ad582d6f99ad267dcdbc02e7072b834810b639f))

* Fixed over zealous CHECK on station.csv ([`34bd2c5`](https://github.com/eyeonus/Trade-Dangerous/commit/34bd2c5ed5e75201ab779e538a5bc49086949b91))

* Work towards on-the-fly station addition ([`96d6e87`](https://github.com/eyeonus/Trade-Dangerous/commit/96d6e8747aa17ff43f0bd764dacd1cefa3c9827b))

* Direct -L to the right variable ([`56693bd`](https://github.com/eyeonus/Trade-Dangerous/commit/56693bd91ff6c29c4a006e4ea788b5b5ddffa796))

* Fixes for addLocalStation ([`0d92913`](https://github.com/eyeonus/Trade-Dangerous/commit/0d92913f17786c3a9cb74edf86667de0afb56bef))

* Merged in maddavo/tradedangerous (pull request #62)

Station updates ([`2e81ef9`](https://github.com/eyeonus/Trade-Dangerous/commit/2e81ef9c80a5ed75b80e7268ec51fc7dcdcbdad6))

* Station Updates ([`85b7a89`](https://github.com/eyeonus/Trade-Dangerous/commit/85b7a8962d6d68e94b9d584265416007a49e9fa8))

* Merged kfsone/tradedangerous into master ([`c4ca5d9`](https://github.com/eyeonus/Trade-Dangerous/commit/c4ca5d97cff74ebc7578f72a5384f48b4791d6ec))

* Minor oops in misc/add-station ([`d4ae79c`](https://github.com/eyeonus/Trade-Dangerous/commit/d4ae79cd33806a07f4e1efb2a3c87aaa08bb9994))

* Credit for Carsten Wiengarten&#39;s stations ([`e4b513e`](https://github.com/eyeonus/Trade-Dangerous/commit/e4b513e9685c2a5e06e83ac7ec5f84ced363e5b0))

* Stations from Carsten Wiengarten ([`15d189a`](https://github.com/eyeonus/Trade-Dangerous/commit/15d189ab2a5c8f71cbce8114370150ea326a5d18))

* Merged in bgol/tradedangerous/devel (pull request #61)

data and bash completion update ([`41d5dcf`](https://github.com/eyeonus/Trade-Dangerous/commit/41d5dcf12614137dc2705149c2b1a957a6549384))

* data ([`4773974`](https://github.com/eyeonus/Trade-Dangerous/commit/4773974a1bb781f6e861fbf79d1235aa88b3f2a2))

* data update ([`0a16c8e`](https://github.com/eyeonus/Trade-Dangerous/commit/0a16c8e4fc1398048e40da271cfe11863cb3323b))

* new argument for run ([`d255417`](https://github.com/eyeonus/Trade-Dangerous/commit/d2554176bd45c19319659d9cd3058ca21363ab75))

* One last station for the night ([`52436a7`](https://github.com/eyeonus/Trade-Dangerous/commit/52436a7e5ce570e409140044445d0787745d0c33))

* Station and Ship data ([`96888b0`](https://github.com/eyeonus/Trade-Dangerous/commit/96888b06181ca0387643526ad2567ff9ae240664))

* Merge branch &#39;master&#39; into devel ([`abf6e04`](https://github.com/eyeonus/Trade-Dangerous/commit/abf6e04b88b28ce2ee4d65adbe4afe3313c51abc))

* Stations ([`2721000`](https://github.com/eyeonus/Trade-Dangerous/commit/27210006a1026de3c407dccaa49c6be7e1b15362))

* Sync&#39;d up systems with Maddavo ([`2b9bcc7`](https://github.com/eyeonus/Trade-Dangerous/commit/2b9bcc71487c7448f3c655a5ad4d8b54dcace8eb))

* Removed some non-existent Beta 3 systems ([`7835017`](https://github.com/eyeonus/Trade-Dangerous/commit/78350170b670183389bfcb9a3114f4a00693fd68))

* Merged in maddavo/tradedangerous (pull request #60)

station updates ([`248bfb3`](https://github.com/eyeonus/Trade-Dangerous/commit/248bfb30395332b0538146577cb844835a094352))

* Removed dead stations

Systems from Beta - don&#39;t exist anymore ([`220095f`](https://github.com/eyeonus/Trade-Dangerous/commit/220095f23a68855a4bd43c630638c3aedfcd66ad))

* Merged kfsone/tradedangerous into master ([`9683a98`](https://github.com/eyeonus/Trade-Dangerous/commit/9683a9864429316f7362f9d072405677afa2d0f2))

* Station Data ([`a6aca43`](https://github.com/eyeonus/Trade-Dangerous/commit/a6aca4365ddfc15dbd1331909512865006070398))

* Additional station data. ([`e604a21`](https://github.com/eyeonus/Trade-Dangerous/commit/e604a217b9eea67b8a005ebd4943472ed8d2b688))

* Merged kfsone/tradedangerous into master ([`e4f1924`](https://github.com/eyeonus/Trade-Dangerous/commit/e4f1924b4e2f15a3d241285e646fadd3d3830ec0))

* Merged kfsone/tradedangerous into master ([`925aaed`](https://github.com/eyeonus/Trade-Dangerous/commit/925aaed04de05355fd2b557b34f135ab52c36b5f))

* Merge branch &#39;master&#39; into devel ([`ff88f63`](https://github.com/eyeonus/Trade-Dangerous/commit/ff88f63e0012de3667a8deea4a2d792cc76cc6d2))

* McKee Ring ([`20fa573`](https://github.com/eyeonus/Trade-Dangerous/commit/20fa573861f0828f8a515961181adc910b914a13))

* Fix for error 46 when editing stations ([`8af13a7`](https://github.com/eyeonus/Trade-Dangerous/commit/8af13a748fa269e20f532b14c0297c4be156438f))

* Better presentation of run -vv ([`da5067e`](https://github.com/eyeonus/Trade-Dangerous/commit/da5067e489d89bc89a4640a557e06ebad16323c5))

* Stations ([`ed83b7c`](https://github.com/eyeonus/Trade-Dangerous/commit/ed83b7c7f504eb940c08a55bf385fd56e1a495d1))

* *Always* display ls to station in dockFmt ([`84aed06`](https://github.com/eyeonus/Trade-Dangerous/commit/84aed068a543d4116b40608b3bd43e15868e7824))

* Don&#39;t use both stations in lspenalty scoring ([`ab7715e`](https://github.com/eyeonus/Trade-Dangerous/commit/ab7715e71228ee8d3743957b538fefc8c275c7bb))

* Typo fix ([`b829fe5`](https://github.com/eyeonus/Trade-Dangerous/commit/b829fe5b96ab9c8d2502ee5247e6604102e6e4d6))

* Added &#34;--ls-penalty&#34; for supercruise biasing ([`7094362`](https://github.com/eyeonus/Trade-Dangerous/commit/7094362cf90c26081e9c840dcec2681682129ec3))

* Credit for OpenSS&#39;s new windows script ([`235325f`](https://github.com/eyeonus/Trade-Dangerous/commit/235325f314dadb04ea08c6808dd3e6831c5e3df9))

* Merged kfsone/tradedangerous into master ([`1ff3404`](https://github.com/eyeonus/Trade-Dangerous/commit/1ff3404368d148a4f5e4c25177221deb8d14409c))

* Merged in OpenSS/tradedangerous (pull request #59)

Create initial windows script ([`8892786`](https://github.com/eyeonus/Trade-Dangerous/commit/889278620dc5363bc72c312728a617b0b3c8cd19))

* pad size support to misc/add-station ([`63d2c5d`](https://github.com/eyeonus/Trade-Dangerous/commit/63d2c5db35ba96aa9b28a2764ec34366176d94e4))

* v6.3.0 Added maxPadSize to stations

Also cleaned up the formatting of local, buy, sell and olddata commands. ([`71db46c`](https://github.com/eyeonus/Trade-Dangerous/commit/71db46cc15e6a32dcbc4df29792a1f0ab0a4eb1a))

* Better presentation of update failure / save ([`58a27f2`](https://github.com/eyeonus/Trade-Dangerous/commit/58a27f2c1dd7eab1e340ade4ed85f19e2b50b823))

* Merged kfsone/tradedangerous into master ([`f8f9b51`](https://github.com/eyeonus/Trade-Dangerous/commit/f8f9b51284d4afde87f7af324865b84e306031f2))

* Merged kfsone/tradedangerous into master ([`0d76409`](https://github.com/eyeonus/Trade-Dangerous/commit/0d764096e834effac1bcfcb86326a64446147860))

* Merge branch &#39;master&#39; into devel ([`38ae4be`](https://github.com/eyeonus/Trade-Dangerous/commit/38ae4be9d7a6265eb4cd620ff82e7c49a26e1a3d))

* Revert &#34;check the sphere, not the cube&#34;

This reverts commit 096fb22412029e34ef5fd907c34166cb39ffccde. ([`bc3f956`](https://github.com/eyeonus/Trade-Dangerous/commit/bc3f9562091a5a1cc1f7f1f13a9dd08025d0ed4e))

* Revert &#34;calculate the real ly value&#34;

This reverts commit 3122bc9873bed7ccc133831d0194cb4ade343544. ([`bb73a88`](https://github.com/eyeonus/Trade-Dangerous/commit/bb73a883b717852748a396a5a18900942e8a9399))

* Cosmetic code change ([`b2255bf`](https://github.com/eyeonus/Trade-Dangerous/commit/b2255bfb54ddfd06bce3467bf5dae47675f22ed0))

* Minor station tweaks ([`0a499de`](https://github.com/eyeonus/Trade-Dangerous/commit/0a499ded09185d26e9fa591db5d424d60b68e4f0))

* Widen the update UI ([`1d3680e`](https://github.com/eyeonus/Trade-Dangerous/commit/1d3680e8e13275d1ada5fdea391c4a403fb72dd6))

* 18 stations ([`a94ba76`](https://github.com/eyeonus/Trade-Dangerous/commit/a94ba7667429341913b4f325425f70c5ab86b797))

* Excess noise from add-station ([`5893225`](https://github.com/eyeonus/Trade-Dangerous/commit/589322505ea3b399cbd0605a1fd7d889700e12bc))

* Update script readme to include trade.bat documentation ([`9e8f3cf`](https://github.com/eyeonus/Trade-Dangerous/commit/9e8f3cfa4e2c55ffb7a3eab254e1673bf7ac5afb))

* Lots of stations ([`e93acf8`](https://github.com/eyeonus/Trade-Dangerous/commit/e93acf8df58efe582b003fbc3f883e209d2a2fe9))

* slight tweak to the validation tolerances ([`e07d27a`](https://github.com/eyeonus/Trade-Dangerous/commit/e07d27a8fe46c5c327f7bc1dd41f631657b8bdb1))

* Additional validation when using the UI to input prices ([`0462d15`](https://github.com/eyeonus/Trade-Dangerous/commit/0462d15e7cf5870a14ab70af002503cee4e3bc57))

* Fix for range calculations and accuracy of nav

This allows us to be more rigorous in finding the shortest path without using a ton more cpu; it may decreases performance of some short routes but it should amortize (average performance will be improved).

It also now reports the correct numbers for jump, total and direct.

Thanks to bgol for catching that the outputs were wrong in the first place. ([`397de17`](https://github.com/eyeonus/Trade-Dangerous/commit/397de1717a7f05a732a56a4dd26143192e85b982))

* Bug in rangeCache caught by bgol ([`6def4fc`](https://github.com/eyeonus/Trade-Dangerous/commit/6def4fcd14fcd56eff11c64034aa64352d588c07))

* Create initial windows script ([`d46d5f0`](https://github.com/eyeonus/Trade-Dangerous/commit/d46d5f0f605c4141e3e9086376103dea545cb149))

* calculate the real ly value ([`3122bc9`](https://github.com/eyeonus/Trade-Dangerous/commit/3122bc9873bed7ccc133831d0194cb4ade343544))

* check the sphere, not the cube ([`096fb22`](https://github.com/eyeonus/Trade-Dangerous/commit/096fb22412029e34ef5fd907c34166cb39ffccde))

* Merged kfsone/tradedangerous into master ([`e5d1f3f`](https://github.com/eyeonus/Trade-Dangerous/commit/e5d1f3f4fd10c4d7f5f732c18e0535ba27e10a35))

* Additional station data ([`8acfe9e`](https://github.com/eyeonus/Trade-Dangerous/commit/8acfe9e38ff592dec2afe136c04441571909ca11))

* More stations ([`8bc1d76`](https://github.com/eyeonus/Trade-Dangerous/commit/8bc1d7651819f74924f9edc0d02fe60d71072cfc))

* ShipVendor ([`17304f6`](https://github.com/eyeonus/Trade-Dangerous/commit/17304f6c3a1d0001dfca8047fb5f368a1d2bb4bf))

* Littlewood Terminal has black market ([`594bf5f`](https://github.com/eyeonus/Trade-Dangerous/commit/594bf5f78a59ef2ddf863286e9360fe30e63315a))

* Littlewood Terminal ([`bfb6d04`](https://github.com/eyeonus/Trade-Dangerous/commit/bfb6d048a887e5ea4c690c36d888f979051ddb33))

* Stations ([`7221d20`](https://github.com/eyeonus/Trade-Dangerous/commit/7221d20eb31c9fbe2118d181df00e85a7ad5acde))

* Zeta Aquilae ([`bbce8c6`](https://github.com/eyeonus/Trade-Dangerous/commit/bbce8c65842aa7ac69650a229c036c7d0e7261c3))

* Unavailable means unavailable ([`f8a75dd`](https://github.com/eyeonus/Trade-Dangerous/commit/f8a75dd5b0c29d43236ef6a7a94d5c6080eab8be))

* Stations ([`e76d242`](https://github.com/eyeonus/Trade-Dangerous/commit/e76d24282473c027298cae2776a3a56cb29d273a))

* Tidy up ([`f09878c`](https://github.com/eyeonus/Trade-Dangerous/commit/f09878cfb227c87621649e2ea19ba5b503b395ac))

* Removed debug line ([`829eec2`](https://github.com/eyeonus/Trade-Dangerous/commit/829eec205bff7376be28af007b2e95fd1c024f4c))

* Merged kfsone/tradedangerous into master ([`736388f`](https://github.com/eyeonus/Trade-Dangerous/commit/736388f49aa732f1659788557774afc629801adb))

* Black market indicator in local command ([`5bf131f`](https://github.com/eyeonus/Trade-Dangerous/commit/5bf131f29462342730b98d540d36f1c8aabc8e30))

* Better support for blackmarket ([`19dae79`](https://github.com/eyeonus/Trade-Dangerous/commit/19dae799a0eeab2093f55cc5635aa6d1d2676b72))

* Merged kfsone/tradedangerous into master ([`4f16d64`](https://github.com/eyeonus/Trade-Dangerous/commit/4f16d646cef944c2f15f25bb4b5d604659a97edd))

* Added --near and --ly options to olddata command ([`a262e25`](https://github.com/eyeonus/Trade-Dangerous/commit/a262e25a0948711c91faaf79cdc04d2f647b3e8b))

* Fixed duplicates ([`ce7ca72`](https://github.com/eyeonus/Trade-Dangerous/commit/ce7ca724008c73aaf3d2c1a3a6924561c61149c4))

* Merged in maddavo/tradedangerous (pull request #57)

Station updates ([`c58d7d6`](https://github.com/eyeonus/Trade-Dangerous/commit/c58d7d626ee9cf0a94f78d2b60a540b9911c1407))

* Station updates

Apalai/Gubarev Base crept back in. ([`250df72`](https://github.com/eyeonus/Trade-Dangerous/commit/250df723ca34ba8d9ea91fa9739900b0bc249e36))

* Fix Station.csv download URL

td/Station.csv is not for downloading ([`022e2c7`](https://github.com/eyeonus/Trade-Dangerous/commit/022e2c7c11c9906c45e8366cc7a992af1a75ffa1))

* Merged kfsone/tradedangerous into master ([`202a2fb`](https://github.com/eyeonus/Trade-Dangerous/commit/202a2fb2d8dd66523f8fb557e00d7c5657cf5edd))

* Removed some noise ([`76623b4`](https://github.com/eyeonus/Trade-Dangerous/commit/76623b4936fdc97f2e65f210970c224df8f35bc3))

* Refactored genSystemsInRange to be concurrency safe

Because we populate the cache as we go, we have to finish populating before we start yielding. ([`2b68f38`](https://github.com/eyeonus/Trade-Dangerous/commit/2b68f3866a6602cbcdbd21cd7b483a188d259f5d))

* Deal with the Scotts ([`50c4744`](https://github.com/eyeonus/Trade-Dangerous/commit/50c4744d06028e9e3539bd3298aee85d86cf13f7))

* Cleanup of add-station ([`6564954`](https://github.com/eyeonus/Trade-Dangerous/commit/65649541b61b5d5e08e44ce377a75f64da808470))

* Binet Port ships ([`bf39ab8`](https://github.com/eyeonus/Trade-Dangerous/commit/bf39ab8c98296a3c44f60cff3602bd0eb842c1f2))

* Merged in bgol/tradedangerous/devel (pull request #56)

Blackmarket data for my stations ([`c8ff766`](https://github.com/eyeonus/Trade-Dangerous/commit/c8ff766f93dc0e2d91efe5ea274992f66f4f2b66))

* Blackmarket data for my stations ([`52f4592`](https://github.com/eyeonus/Trade-Dangerous/commit/52f4592cb65aa44bb3f7cefa62443dbe0ecccb2d))

* LTT 15449/Binet Port Ships ([`fb333f9`](https://github.com/eyeonus/Trade-Dangerous/commit/fb333f97b652160caadac2677c2108105248edeb))

* LTT 15449 distances ([`a1c88c8`](https://github.com/eyeonus/Trade-Dangerous/commit/a1c88c84bc49f80cfee79e723eb85489d36dcd54))

* Minor station data ([`ec602ba`](https://github.com/eyeonus/Trade-Dangerous/commit/ec602ba2260b45e0535d72ae539b5f1d1faeb082))

* Killing the :xxx stations I added ([`3171a2d`](https://github.com/eyeonus/Trade-Dangerous/commit/3171a2dfa83a95fd4b255a4752cb603bc4ce29b9))

* Blackmarket flag added to Station.csv ([`8370b49`](https://github.com/eyeonus/Trade-Dangerous/commit/8370b490716148803902ecaa99f72a7021ad8abf))

* Unbreak ship changes ([`d331d49`](https://github.com/eyeonus/Trade-Dangerous/commit/d331d495715ff0216f3c41a7b1202fce8ece7bb3))

* Patterson station ships ([`1d6974f`](https://github.com/eyeonus/Trade-Dangerous/commit/1d6974f2195950cd508b8f1782a45c5217a3d443))

* Try to avoid including the :ls in station names ([`8bbdf19`](https://github.com/eyeonus/Trade-Dangerous/commit/8bbdf1950cd0ef6b959aa293effe13463b457aaf))

* Reorganized ship data ([`d4f13f4`](https://github.com/eyeonus/Trade-Dangerous/commit/d4f13f404b001fc5d70e23f03af999c8fac9dd9a))

* Close the DB connection before rendering commands ([`afa7686`](https://github.com/eyeonus/Trade-Dangerous/commit/afa7686d70ff32bfd4914b369292bcf692fcc424))

* Stations discovered ([`6f4b004`](https://github.com/eyeonus/Trade-Dangerous/commit/6f4b004527dbf8cc411440114e680c6da5b5da1c))

* Corrections ([`2e0dce0`](https://github.com/eyeonus/Trade-Dangerous/commit/2e0dce0b4aab70597007c4c1b4c4e73c9617c2a7))

* Another dozen stations ([`cc6b849`](https://github.com/eyeonus/Trade-Dangerous/commit/cc6b849d1d9b92dd03eaf7cf86c37c117abf6a4f))

* Merged in bgol/tradedangerous/devel (pull request #55) ([`520dd0f`](https://github.com/eyeonus/Trade-Dangerous/commit/520dd0f969130c6178554ffea3385057d3c245ca))

* Lots more stations ([`f84be3d`](https://github.com/eyeonus/Trade-Dangerous/commit/f84be3d389b764756d7c35f32808eddd292f70d1))

* Make :ls option for add-station ([`5245c6a`](https://github.com/eyeonus/Trade-Dangerous/commit/5245c6a6e6add50c622277684c9ab5bddfc0b7eb))

* Make :ls option for add-station ([`4b6bbe8`](https://github.com/eyeonus/Trade-Dangerous/commit/4b6bbe8eaa8de8848ec36435abe46c34dc9c856b))

* Make :ls option for add-station ([`6acafc9`](https://github.com/eyeonus/Trade-Dangerous/commit/6acafc9ed0d11f3226de9ac16f01333412d3b100))

* Functions for adding local system/station data ([`7787594`](https://github.com/eyeonus/Trade-Dangerous/commit/778759443198a23c8ab94495de2c901f55144cb1))

* Initial version of jsonprices.py ([`8c06e9d`](https://github.com/eyeonus/Trade-Dangerous/commit/8c06e9d548c65da75e2d023491a3e75d8d36afbc))

* Corrected some station names ([`efcf9d4`](https://github.com/eyeonus/Trade-Dangerous/commit/efcf9d49fbeb805cbea3fc2d3bf15199caca7853))

* Anomalies ([`591c8c0`](https://github.com/eyeonus/Trade-Dangerous/commit/591c8c05410c4c795d6d85d51ff6921675f776df))

* Added value of &#39;Local&#39; ([`c4e151a`](https://github.com/eyeonus/Trade-Dangerous/commit/c4e151a66514fa60120d6f5d85f04632e0b00287))

* Merged kfsone/tradedangerous into master ([`87587e3`](https://github.com/eyeonus/Trade-Dangerous/commit/87587e332f6f15afc1bb29579dd3afb06c9c1c60))

* more stations and shipyards ([`36c647e`](https://github.com/eyeonus/Trade-Dangerous/commit/36c647e2685087a6ccdebb8f311618ad83ea83df))

* Some oddly capitalized names ([`b6bdd53`](https://github.com/eyeonus/Trade-Dangerous/commit/b6bdd53d2dd6d8247d0e133e963f7afb87ad337f))

* Merged kfsone/tradedangerous into master ([`1567d0e`](https://github.com/eyeonus/Trade-Dangerous/commit/1567d0e9b6d5613b356e41de96e7a8287adec713))

* Many stations ([`2625eb3`](https://github.com/eyeonus/Trade-Dangerous/commit/2625eb33661b546843654d440d2ddffd39c2df7d))

* Eyharts Hub ([`cf30404`](https://github.com/eyeonus/Trade-Dangerous/commit/cf30404a44fcca78ef147f8492bb1580bd250f1b))

* Updated station.csv ([`4b3cbb7`](https://github.com/eyeonus/Trade-Dangerous/commit/4b3cbb752e81a22d1f387f5b61a975e519ae9c0e))

* Changed ls-from-star to be an int instead of double ([`4bf8d90`](https://github.com/eyeonus/Trade-Dangerous/commit/4bf8d90e4b864996baa621ebf70f606f269ea3b8))

* Half-assed add-station script. ([`1e949d8`](https://github.com/eyeonus/Trade-Dangerous/commit/1e949d803843a481a8721e58e05dc79196c23c89))

* Change notes ([`412806c`](https://github.com/eyeonus/Trade-Dangerous/commit/412806cd87fa3f64d74a36645f158146419a951d))

* Merged in bgol/tradedangerous/csvexport (pull request #52)

Split up the actual export routine from the export sub-command ([`abb2340`](https://github.com/eyeonus/Trade-Dangerous/commit/abb23406b2fa4674a84fc166fcd4cd26bbcbab36))

* Merged in bgol/tradedangerous/devel (pull request #53)

Bash auto-complete for trade.py command. ([`3a636ce`](https://github.com/eyeonus/Trade-Dangerous/commit/3a636ce580cf64d4879afdd743d2e88a05f702fd))

* Merged in maddavo/tradedangerous (pull request #54)

Station updates ([`38d29c3`](https://github.com/eyeonus/Trade-Dangerous/commit/38d29c3048bad27a99d8692825e21360c7fdb9b7))

* Merged stations from prices database

Additions for stations that exist in the prices database.  Also Janifer
Port doesn&#39;t exist ([`7a8d8c0`](https://github.com/eyeonus/Trade-Dangerous/commit/7a8d8c07c650c8831c915c239448bfa3988f9a85))

* Merged kfsone/tradedangerous into master ([`9fcc861`](https://github.com/eyeonus/Trade-Dangerous/commit/9fcc861052ad8693b1e5f3d5603b0a0453340409))

* added the scripts to the auto-complete ([`a468d3c`](https://github.com/eyeonus/Trade-Dangerous/commit/a468d3c374c2f2bfb5a789892b8d07a78a096e73))

* ups, no checkprices for the common user ([`97bac0c`](https://github.com/eyeonus/Trade-Dangerous/commit/97bac0cebcb3821d35a5d4495b49f508617f416f))

* Bash auto-complete for trade.py command. ([`cfeed7d`](https://github.com/eyeonus/Trade-Dangerous/commit/cfeed7dc72b9ae626d9961b59116ca3bbd63c552))

* Merged in bgol/tradedangerous/devel (pull request #51)

new stations and shipyards ([`659aee5`](https://github.com/eyeonus/Trade-Dangerous/commit/659aee5acd414874347ef7d45b0343461e9e24f5))

* Split up the actual export routine from the export sub-command ([`5c1f403`](https://github.com/eyeonus/Trade-Dangerous/commit/5c1f403bcbf3b9bbcf7c2680bb6bdb5035102b2d))

* export order ([`f310585`](https://github.com/eyeonus/Trade-Dangerous/commit/f310585dbdb3148f16692289d39f161c07841896))

* Merged kfsone/tradedangerous into master ([`7771c11`](https://github.com/eyeonus/Trade-Dangerous/commit/7771c11b125fad9012915ba596277b0081bedb88))

* more stations and shipyards ([`69c185f`](https://github.com/eyeonus/Trade-Dangerous/commit/69c185f171fdd625d7d98150bf730bf2c5df0064))

* new stations and shipyards ([`f5adb9a`](https://github.com/eyeonus/Trade-Dangerous/commit/f5adb9abc6adbf0150ceb050fa9a4c27a44ea703))

* maddavo plugin tweaks and fixes ([`fa562eb`](https://github.com/eyeonus/Trade-Dangerous/commit/fa562eb7ee0d911ef07c422c543adcf6529a723f))

* Catch 404s in transfers ([`13ab513`](https://github.com/eyeonus/Trade-Dangerous/commit/13ab513474b8c74b6972fe1768566fdabd0b56c7))

* Incorrect placement of cacheNeedsRebuild ([`0b6b1f1`](https://github.com/eyeonus/Trade-Dangerous/commit/0b6b1f1ab5e6f4a0dc2e4fe5a7fb9fa26ebdbc35))

* Change summary ([`ae77cfe`](https://github.com/eyeonus/Trade-Dangerous/commit/ae77cfed79b4a3a24178937f7acb26017ff20d52))

* Now we&#39;re rebuilding the cache after DLs, we shouldn&#39;t do it before we update (otherwise you can get stuck in a loop where you can&#39;t download files because of an update you want) ([`061e95b`](https://github.com/eyeonus/Trade-Dangerous/commit/061e95b08e4a4fa6f233fac30ff430701d3ceb8a))

* Corrected URL for maddavos station.csv ([`5a38491`](https://github.com/eyeonus/Trade-Dangerous/commit/5a38491878dc8219dcf3d8276c5ae33b569e9164))

* fixes #91 utf-8 decoding error in downloaded files ([`8f97514`](https://github.com/eyeonus/Trade-Dangerous/commit/8f97514de1fc873371673e33cbaa434fc906ef25))

* Merged in maddavo/tradedangerous (pull request #50)

Combat Stabilisers exist ([`4e9f2bc`](https://github.com/eyeonus/Trade-Dangerous/commit/4e9f2bcdb4b14557a7302b79f280541ff9ade114))

* Merged kfsone/tradedangerous into master ([`19bdd77`](https://github.com/eyeonus/Trade-Dangerous/commit/19bdd7739dcd23e9c17585311799bf472fd82b59))

* Rebuild the cache after downloading .csv files, before trying to parse .prices files ([`4cb8ab6`](https://github.com/eyeonus/Trade-Dangerous/commit/4cb8ab656ecac9282db98ccc96d42ae671598a1d))

* utf-8 file is utf-8 ([`01e4662`](https://github.com/eyeonus/Trade-Dangerous/commit/01e46621e81a423d4618fd05dc9c1b019e3e770d))

* Code cleanup ([`2ebd752`](https://github.com/eyeonus/Trade-Dangerous/commit/2ebd7522f744741cfa3ba932198caccb25901870))

* 0 means zero, for now ([`b994198`](https://github.com/eyeonus/Trade-Dangerous/commit/b994198e22dbc7fa5316b702afb16a0ca71afe9a))

* import cleanup ([`fc02865`](https://github.com/eyeonus/Trade-Dangerous/commit/fc02865f34fb10fe6146b3eed64d8ccdd6cbe715))

* Merged in bgol/tradedangerous/devel (pull request #49)

Ignore price tables for standard export. ([`d9b62a2`](https://github.com/eyeonus/Trade-Dangerous/commit/d9b62a29167a0edbc3fbba88c05a97df71c03c2b))

* small docu change ([`0b4f41e`](https://github.com/eyeonus/Trade-Dangerous/commit/0b4f41e0c5fe5f565efad0a909154583d6e8c3cb))

* Ignore price tables for standard export. Use &#39;--all-tables&#39; if you really want them. ([`b864cbc`](https://github.com/eyeonus/Trade-Dangerous/commit/b864cbcb3c70a4cf0e6489f3df71b46a25779536))

* Merged kfsone/tradedangerous into master ([`f4f3695`](https://github.com/eyeonus/Trade-Dangerous/commit/f4f3695c07850ebd25cc366972312793fea1af0a))

* HR8170 ([`94576a2`](https://github.com/eyeonus/Trade-Dangerous/commit/94576a2c9be90b91a60f963ff305a561b37445b3))

* fixes #90 import fails if trying to import from scratch ([`b6f3a49`](https://github.com/eyeonus/Trade-Dangerous/commit/b6f3a49f67ff8e828119288a7a764e03af12058b))

* v6.2.3 ([`2d7123e`](https://github.com/eyeonus/Trade-Dangerous/commit/2d7123e8415393b249490eb938f0593a665be9d7))

* stamp tracking and pre-processing in maddavo plugin ([`a6111dd`](https://github.com/eyeonus/Trade-Dangerous/commit/a6111dd8c81b99e351b659585f46f21b1eb36744))

* Capture dataDir as a path in TradeDB() instances ([`3cde052`](https://github.com/eyeonus/Trade-Dangerous/commit/3cde05229ba87087f9f8597b087d07b69a2f54f3))

* Catch plugin exceptions in trade.py ([`276d4cf`](https://github.com/eyeonus/Trade-Dangerous/commit/276d4cf48a04eae4726b5fb7e4600d0d25d9d654))

* Ignore files in data with the suffix .stamp ([`52a5bf9`](https://github.com/eyeonus/Trade-Dangerous/commit/52a5bf9550089d2ff655d4f39920c96974bbd760))

* Bunch of stations ([`840833f`](https://github.com/eyeonus/Trade-Dangerous/commit/840833feda37d5daa7d2ae24bccba11a1607d43b))

* Merge remote-tracking branch &#39;origin/master&#39;

Conflicts:
	corrections.py ([`cb711ea`](https://github.com/eyeonus/Trade-Dangerous/commit/cb711ea7df2d2320093710367c9c6cf370df1d7c))

* Combat Stabilisers exist ([`2bb2645`](https://github.com/eyeonus/Trade-Dangerous/commit/2bb264554dc8fd182028d26c89f7d6477f509d18))

* Merged kfsone/tradedangerous into master ([`3f01f61`](https://github.com/eyeonus/Trade-Dangerous/commit/3f01f618e7b80ac30b99ee676273b18eacf19fdd))

* Relaxed warnings for price differences ([`4962326`](https://github.com/eyeonus/Trade-Dangerous/commit/49623260ee88f4a514c5b68686e72e2181ca0b13))

* Eliminated StationLink and minor cleanup

&#34;-v&#34; now shows station count for &#34;nav&#34; command instead of &#34;--stations&#34; ([`9819356`](https://github.com/eyeonus/Trade-Dangerous/commit/9819356a683fd8e212b40e47d3e6a908290848d9))

* Merged kfsone/tradedangerous into master ([`ab80022`](https://github.com/eyeonus/Trade-Dangerous/commit/ab800221a9a2b1b8b1257122d8e33708787d3e7a))

* fixes #89 synchronizing some item names with 1.0 ([`e0d7b71`](https://github.com/eyeonus/Trade-Dangerous/commit/e0d7b7122ca3029c7ebe80223ed64e4e505c7185))

* Merged kfsone/tradedangerous into master ([`471b440`](https://github.com/eyeonus/Trade-Dangerous/commit/471b440f4a86d78518ff858278568545363e55e4))

* v6.2.2 ([`2134657`](https://github.com/eyeonus/Trade-Dangerous/commit/213465762189517d91d95e8a7d2f480c1bc1a1a0))

* Removed Alloys, Plastics, Cotteon and Combat Stabilisers. ([`39b5807`](https://github.com/eyeonus/Trade-Dangerous/commit/39b58072ab1d4b1903b500dff45133259f50555c))

* Ships for Fiennes Vision ([`dd54183`](https://github.com/eyeonus/Trade-Dangerous/commit/dd54183ec22c757b1d503c4314536731c6aad783))

* Added &#34;--option=syscsv&#34; and &#34;--option=stncsv&#34; to maddavo plug

This options will download Dave&#39;s System and Station csv respectively. ([`2bb0c04`](https://github.com/eyeonus/Trade-Dangerous/commit/2bb0c0428e49c13a242e7ddccd671da79e9b182d))

* Safe downloads in transfers.py

Download remove files to a &#34;.dl&#34; extension so that if the download fails you don&#39;t lose the original file. Transfer the files when done.

Also added a &#34;backup&#34; option which leaves a &#34;.bak&#34; file of the original ([`2d0aa1a`](https://github.com/eyeonus/Trade-Dangerous/commit/2d0aa1a1793949f8e8fedad63e541726f11639a4))

* Handle blank lines during processing of .csv files ([`b89a0d1`](https://github.com/eyeonus/Trade-Dangerous/commit/b89a0d1e7847c272b3cd2d862db463535ae4423c))

* Added --option to import cmd

This allows the user to pass arguments to a plugin, --option=foo ([`c65198a`](https://github.com/eyeonus/Trade-Dangerous/commit/c65198a1580be2943a5b6e9c7a157df6706c078c))

* Add --download and --url to make import a general downloader

The import command can now be used as a general downloader by specifying &#34;--download --url=http://... filename&#34; ([`7f5fc47`](https://github.com/eyeonus/Trade-Dangerous/commit/7f5fc47577a746ce582041e4567ac6b538e022e6))

* Plugins can now handle tdenv.pluginOptions ([`c9667fa`](https://github.com/eyeonus/Trade-Dangerous/commit/c9667fa397569d572a2695ff301193adc9634480))

* import does not actually want the database loaded. ([`d4d44cb`](https://github.com/eyeonus/Trade-Dangerous/commit/d4d44cb2eff71534e7e32de294f72a84988b24fa))

* Merged kfsone/tradedangerous into master ([`e077fd6`](https://github.com/eyeonus/Trade-Dangerous/commit/e077fd629b937d3b60374ff1fd6f3aeaceecba76))

* I&#39;m having a bad day, sorry for sharing ([`7e3e398`](https://github.com/eyeonus/Trade-Dangerous/commit/7e3e398009a0986f6399eb0f8dcc3b7bf6216b04))

* Rob hubbard? Who the hell is he? :) ([`2672979`](https://github.com/eyeonus/Trade-Dangerous/commit/267297985ed5eb2a4c495815c394ce95faf5b86f))

* Merged kfsone/tradedangerous into master ([`8b37266`](https://github.com/eyeonus/Trade-Dangerous/commit/8b372663451a18427bcfa4d827180b0f779b9936))

* More stations ([`cdb4b51`](https://github.com/eyeonus/Trade-Dangerous/commit/cdb4b51d023ad87a5f65ce7bb42a9f4406c7ed2d))

* tweaked tdbuyfrom ([`0495413`](https://github.com/eyeonus/Trade-Dangerous/commit/0495413a5e544d117236eb7dbd44609be1df1d20))

* fixes #88 --via wasn&#39;t working or reporting when vias were incompatible ([`09247cf`](https://github.com/eyeonus/Trade-Dangerous/commit/09247cf69a1c08e3524a1e3f928880cdcacb6ccb))

* Little bit more flex in the 25% price boundary ([`c6b7d5a`](https://github.com/eyeonus/Trade-Dangerous/commit/c6b7d5a959e9b0bb520e5a0d59b49d4446d4cd2a))

* Fix for 64-bit saitek drivers ([`0444183`](https://github.com/eyeonus/Trade-Dangerous/commit/0444183f89608e1a1b5fa6333a7fdd0cf29649a0))

* Merged kfsone/tradedangerous into master ([`2139508`](https://github.com/eyeonus/Trade-Dangerous/commit/2139508918e72b224cf2f752b9f2174109fc7e64))

* Merged kfsone/tradedangerous into master ([`36a9ad2`](https://github.com/eyeonus/Trade-Dangerous/commit/36a9ad2195b89d9460d881d4b086c76e64f270f8))

* Added &#39;--max-days-old&#39; (-MD) to run command ([`5292359`](https://github.com/eyeonus/Trade-Dangerous/commit/529235963b0b9ed8113d1103ceddef6cae45be38))

* Data updates ([`e55c9e7`](https://github.com/eyeonus/Trade-Dangerous/commit/e55c9e73d8b5e17b47a6d68ff8917e18202bd48e))

* Gong Gu Ships ([`714b0c8`](https://github.com/eyeonus/Trade-Dangerous/commit/714b0c8fca6e0e59dedc3b1fa89859612532cc62))

* Gong Gu Ships ([`f24b36b`](https://github.com/eyeonus/Trade-Dangerous/commit/f24b36b33f0337b62ccee98920c0eb3818074cba))

* Gong Gu/Kelly ([`a365fb7`](https://github.com/eyeonus/Trade-Dangerous/commit/a365fb7803923fb120832ae2203efe45e43d062a))

* Evergreen stations ([`24c2577`](https://github.com/eyeonus/Trade-Dangerous/commit/24c257764e1fcab7e98ad8b1bfcfb9a010b52647))

* Merged in cmdrgulsch/tradedangerous (pull request #48)

ship vendors and stations with distances ([`757c66f`](https://github.com/eyeonus/Trade-Dangerous/commit/757c66f8c2f8f2b40d3285244e6773f0a4e45162))

* Merged kfsone/tradedangerous into master ([`a0f9aec`](https://github.com/eyeonus/Trade-Dangerous/commit/a0f9aec289c7d08867bde5991850cd2d22f51502))

* Merged kfsone/tradedangerous into master ([`fe25b2f`](https://github.com/eyeonus/Trade-Dangerous/commit/fe25b2fba6de9426a8a72b0283ccf2f3b220efa5))

* ship vendors and stations with distances ([`278d228`](https://github.com/eyeonus/Trade-Dangerous/commit/278d228706ec0f8df302c0bfa2d5a8ecd0cd8fb6))

* Merged kfsone/tradedangerous into master ([`e1f2249`](https://github.com/eyeonus/Trade-Dangerous/commit/e1f2249feeafab8eceee504e9c26290142d2ffd5))

* Added &#34;old data&#34; command ([`85586fe`](https://github.com/eyeonus/Trade-Dangerous/commit/85586fef34d1b6d65753b75cbc4ec13d6865c333))

* Merged kfsone/tradedangerous into master ([`446c7f2`](https://github.com/eyeonus/Trade-Dangerous/commit/446c7f2743bdc02085f50402f8cafe7e50aa917e))

* Correction for Watson Station ([`ebbb956`](https://github.com/eyeonus/Trade-Dangerous/commit/ebbb956c68e973136efb8f728e2c2141172ea9e1))

* Stations ([`09d87ed`](https://github.com/eyeonus/Trade-Dangerous/commit/09d87edbacddc3537aaa0a2adb7c5edf88c750b6))

* Fixup ([`85929bc`](https://github.com/eyeonus/Trade-Dangerous/commit/85929bccd9e649abfd1bbdebdcfec4d627b896d9))

* Merged kfsone/tradedangerous into master ([`f3f483d`](https://github.com/eyeonus/Trade-Dangerous/commit/f3f483d34afe7b43ffb3c7797bb26bde951d2e05))

* added stations and distances ([`57254c9`](https://github.com/eyeonus/Trade-Dangerous/commit/57254c93eef2e7a8dcc0d6ab51e2cc44f82fc8ae))

* Merged in fawick/tradedangerous (pull request #46)

Added Alpha Centauri stations ([`849208a`](https://github.com/eyeonus/Trade-Dangerous/commit/849208a1afc9acd141792dd0f1c1f764e5ff379e))

* Merged in cmdrgulsch/tradedangerous (pull request #47)

Added stations and distances ([`0dc42ac`](https://github.com/eyeonus/Trade-Dangerous/commit/0dc42ac7372816e01522814849109ac0914bd1b9))

* Merged in martin_griesbach/tradedangerous (pull request #44)

Stations in Lugh and LTT 4846 ([`2d53b8c`](https://github.com/eyeonus/Trade-Dangerous/commit/2d53b8cb8cff2b0b996df22917787cd41b55966d))

* First pass at showing age (-vv) on run command ([`9e8d7b1`](https://github.com/eyeonus/Trade-Dangerous/commit/9e8d7b1108add6733a28974c9fb5b31d2eaca5e0))

* Fixed repr for tradedb.Trade ([`cc306dc`](https://github.com/eyeonus/Trade-Dangerous/commit/cc306dce095041d16a1867e6dfd6687b40c15efb))

* Added ship vendors ([`83bed0c`](https://github.com/eyeonus/Trade-Dangerous/commit/83bed0cea9f7f6410de492b43282caf2cb0262fc))

* Handle item and category changes ([`515efbf`](https://github.com/eyeonus/Trade-Dangerous/commit/515efbf2fa57be8b5c18c00435da9e9ac8fe4cea))

* Added stations and distances ([`cd2aa94`](https://github.com/eyeonus/Trade-Dangerous/commit/cd2aa945d0bb48f8031af5a4f5b957cecfcdbb7f))

* Merged kfsone/tradedangerous into master ([`3eaea15`](https://github.com/eyeonus/Trade-Dangerous/commit/3eaea15ba498b2fee08581c32bce39aab530d89d))

* Revert &#34;Added stations and distances&#34;

This reverts commit 8550537e758180df367f600d4d17f6f7f9ddc374. ([`5c8c36d`](https://github.com/eyeonus/Trade-Dangerous/commit/5c8c36d525329ce6077154ec3f794bcc8f02f024))

* Added stations and distances ([`8550537`](https://github.com/eyeonus/Trade-Dangerous/commit/8550537e758180df367f600d4d17f6f7f9ddc374))

* Added Alpha Centauri stations ([`bd38f7c`](https://github.com/eyeonus/Trade-Dangerous/commit/bd38f7cd7b4019c2a5a05de8b298310778a72255))

* Merged kfsone/tradedangerous into master ([`3624698`](https://github.com/eyeonus/Trade-Dangerous/commit/36246989ff28568b0001fd6cbbf781231287c0b0))

* fixes #84, missing item slaves/slaves ([`a3dd276`](https://github.com/eyeonus/Trade-Dangerous/commit/a3dd2761dd269ba0dcc9f867e9995e9478dc0507))

* Credit for updates ([`188842f`](https://github.com/eyeonus/Trade-Dangerous/commit/188842fbdd053d3f0acff931ded3d5579cd88952))

* Merged in bgol/tradedangerous/devel (pull request #45)

new stations, distances, shipyards and some ship data updates ([`d4d7cc6`](https://github.com/eyeonus/Trade-Dangerous/commit/d4d7cc6d9ab9642b299db4263c3b0f22a1c85dcf))

* Merge branch &#39;master&#39; into devel

Conflicts:
	corrections.py ([`c9a625c`](https://github.com/eyeonus/Trade-Dangerous/commit/c9a625cbe82999a66a32b80b5e60e7750ded64bc))

* Fix for certain broken station names.

Some people are using station names in a station.csv that are missing spaces. ([`505f9ce`](https://github.com/eyeonus/Trade-Dangerous/commit/505f9ce320e77cb4e03af36e2c433cbacad3ed85))

* Fixed cython compile errors ([`3b92412`](https://github.com/eyeonus/Trade-Dangerous/commit/3b92412bb3eb76fedc57a6282e5da3fa37bfd804))

* correction: Tito Colony ([`9d75a26`](https://github.com/eyeonus/Trade-Dangerous/commit/9d75a2636395b2666a406f9e8fae4aecb0b35fba))

* new stations, distances and shipyards ([`937c962`](https://github.com/eyeonus/Trade-Dangerous/commit/937c962fa71cb142c888057dcc5d5d8d09ae81cb))

* ship status updates, some values from https://forums.frontier.co.uk/showthread.php?t=73571 ([`6188a8d`](https://github.com/eyeonus/Trade-Dangerous/commit/6188a8db9c03301465082b53c130c442fafc6bce))

* Stations in Lugh and LTT 4846 ([`e901cdb`](https://github.com/eyeonus/Trade-Dangerous/commit/e901cdb20d7c4fd043905e2be55ce31ab40eb36f))

* added --age to sell command ([`5d1df63`](https://github.com/eyeonus/Trade-Dangerous/commit/5d1df633abe638f9fef97d195011ca27269d267e))

* Ho Hsien stations ([`5233d20`](https://github.com/eyeonus/Trade-Dangerous/commit/5233d20809728257ffaf18ebd64031579be0a8d2))

* More stations ([`b660e12`](https://github.com/eyeonus/Trade-Dangerous/commit/b660e12723a0b5a3b2ff978ac6815bc1a46c264d))

* Merged kfsone/tradedangerous into master ([`a0a9e34`](https://github.com/eyeonus/Trade-Dangerous/commit/a0a9e34a77f82b07f0d2cc17cc5cad3cb687b9d3))

* Vetulani distance ([`94b5b11`](https://github.com/eyeonus/Trade-Dangerous/commit/94b5b11c161f53c092d19d000954c36b8e7de540))

* &#34;buy&#34; and &#34;sell&#34; --near now works in-system too ([`c656e7f`](https://github.com/eyeonus/Trade-Dangerous/commit/c656e7f3a6492d33605312747d3a6f2624583891))

* Merged in cmdrgulsch/tradedangerous (pull request #43)

Added stations/distances and ships/stats ([`35dd37b`](https://github.com/eyeonus/Trade-Dangerous/commit/35dd37ba5b1133a580040c396ee102812461cc02))

* Buy and Sell now show average price if you use --detail ([`0d31f49`](https://github.com/eyeonus/Trade-Dangerous/commit/0d31f49245b5839ba6d021c6dfa9e740d60b30ee))

* Vetulani Installation ([`badcf15`](https://github.com/eyeonus/Trade-Dangerous/commit/badcf151093eb277d6c59b606d1c648ab4e08b7d))

* Removed --aggressive from nav ([`b917f7f`](https://github.com/eyeonus/Trade-Dangerous/commit/b917f7f7c09b1091d24011f574344effe33d7084))

* Fixed --via ([`c39a856`](https://github.com/eyeonus/Trade-Dangerous/commit/c39a8568e542235282ddadba305aced8cebc2c5d))

* Visual Studio solution ([`53fb583`](https://github.com/eyeonus/Trade-Dangerous/commit/53fb583320060a6c587e2ab0c4c426c749619454))

* Assorted code cleanup ([`5e08036`](https://github.com/eyeonus/Trade-Dangerous/commit/5e080369d57a5f99821394617e393365fcd58d6d))

* Merged kfsone/tradedangerous into master ([`09c151f`](https://github.com/eyeonus/Trade-Dangerous/commit/09c151fa2e3884a8c60cfeb4c3c7c227f9c8cecb))

* Merged kfsone/tradedangerous into master ([`c287b5f`](https://github.com/eyeonus/Trade-Dangerous/commit/c287b5f0868e4bfa83405990dd58d9787cb001c0))

* Added ships and stats ([`ce2b670`](https://github.com/eyeonus/Trade-Dangerous/commit/ce2b67039ca331e8aea055d0dd5e8c92f95ab97b))

* Fix for missing import in mfd module ([`9b52e4b`](https://github.com/eyeonus/Trade-Dangerous/commit/9b52e4b38701c152ca906586485a5b8dc505dc9d))

* Import all commands at startup ([`20b263e`](https://github.com/eyeonus/Trade-Dangerous/commit/20b263e8d70d774436e2de053f2f372d3d0500d3))

* Cleanup ([`dadd6b1`](https://github.com/eyeonus/Trade-Dangerous/commit/dadd6b1a201dc45622290a0b5de251eb660712a2))

* Call regeneratePricesFile() after calling ImportPlugin.finish()

This ensures that a plugin&#39;s custom work is always reflected in the .prices file if we wind up doing a rebuild ([`4707c91`](https://github.com/eyeonus/Trade-Dangerous/commit/4707c91ace248c915040f81cfda4df3b7d29204a))

* Merged kfsone/tradedangerous into master ([`e04bee1`](https://github.com/eyeonus/Trade-Dangerous/commit/e04bee1900d970966632c8c0ec6d8a06ea8d26f3))

* BD+43 stations ([`b1aa1e8`](https://github.com/eyeonus/Trade-Dangerous/commit/b1aa1e8a045e2d52aa2c54f15f323f6fae758fb9))

* Fix for &#39;run&#39; to a system with no stations not generating a warning ([`5868f07`](https://github.com/eyeonus/Trade-Dangerous/commit/5868f0774de3794134700d0f45bb680bcc5abd66))

* Thornycroft Penal Colony ([`b6a87eb`](https://github.com/eyeonus/Trade-Dangerous/commit/b6a87ebb4dd0818bbc9eb20f7715671f78f9aab5))

* Changed &#39;tdimad&#39; script to use the plugin option ([`ef9dc1a`](https://github.com/eyeonus/Trade-Dangerous/commit/ef9dc1adb0bef80eef4b8c68a55af8d83f79baaa))

* Added plugin system and implemented maddavo&#39;s import as an ImportPlugin ([`4db2f6d`](https://github.com/eyeonus/Trade-Dangerous/commit/4db2f6d4860bc9fe75ac4abdcc67988ab25d0e1c))

* Fix for use of TradeDB with no TradeEnv ([`cc4443e`](https://github.com/eyeonus/Trade-Dangerous/commit/cc4443e19f81a230490fbd6849903b4da84ff140))

* Discrete base classes for different plugin types ([`7fa6cd9`](https://github.com/eyeonus/Trade-Dangerous/commit/7fa6cd9662f774cb0801a95ba97d5484e417fb85))

* Merged kfsone/tradedangerous into master ([`f588b6e`](https://github.com/eyeonus/Trade-Dangerous/commit/f588b6e67262f0b057075fc9b121e5d0cf7250c5))

* &#34;update&#34; now defaults to &#34;-G&#34; ([`8d5edd6`](https://github.com/eyeonus/Trade-Dangerous/commit/8d5edd6a80d28b8421a1fded7e8d270921d6df48))

* Made &#34;--capacity&#34; and &#34;--ly-per&#34; required arguments to &#34;run&#34; ([`1d741ca`](https://github.com/eyeonus/Trade-Dangerous/commit/1d741ca5dfe6eedef9e347e8a189afb98622e478))

* Fixed &#34;--ly=0&#34; under &#34;local&#34; command ([`9d2ac83`](https://github.com/eyeonus/Trade-Dangerous/commit/9d2ac831cc3031bc21a171c613375e939a27faf2))

* Tell the user about cache rebuilds (-q to silence) ([`a79a41b`](https://github.com/eyeonus/Trade-Dangerous/commit/a79a41b306ee450ecb00c76b976a7fe6e0f7037f))

* Added stations and distances ([`cef0295`](https://github.com/eyeonus/Trade-Dangerous/commit/cef0295b9656c97d25e412fe1c1c89886a77ac5a))

* Merged kfsone/tradedangerous into master ([`6d03ea2`](https://github.com/eyeonus/Trade-Dangerous/commit/6d03ea21444a4e9d15fef0c98cf5b6ac933852f2))

* PluginBase and PluginException ([`0655e32`](https://github.com/eyeonus/Trade-Dangerous/commit/0655e323e1cc219943d933e3394f7e7cd270e836))

* Some more files to ignore ([`d367c95`](https://github.com/eyeonus/Trade-Dangerous/commit/d367c95df516619c701e4f2b82dbfc8aa81e8b1b))

* First pass at the plugin base class ([`32b6da8`](https://github.com/eyeonus/Trade-Dangerous/commit/32b6da8b1ad88b921e1586ea8841c1540a4cefe5))

* Moved the download module into transfers.py

This will make it easier to share amongst plugins ([`4210223`](https://github.com/eyeonus/Trade-Dangerous/commit/4210223eadf1f5248968d174afe834230edc404d))

* more aggressive sub-matching so &#39;ascendingp&#39; matches &#39;the ascending phoeenix&#39; ([`ef42a04`](https://github.com/eyeonus/Trade-Dangerous/commit/ef42a04a35dd208722fbbd90d13a86e0cd5d8d4b))

* Experimental json generator ([`bd73e5e`](https://github.com/eyeonus/Trade-Dangerous/commit/bd73e5e0b9fed31ad0b57d641a25f1b83bf04795))

* Merged kfsone/tradedangerous into master ([`d4abea2`](https://github.com/eyeonus/Trade-Dangerous/commit/d4abea2283ad3bc28e4ae0d9d29c884705c94257))

* Merged kfsone/tradedangerous into master ([`13b3ddb`](https://github.com/eyeonus/Trade-Dangerous/commit/13b3ddbe4647493b3f116b05b9058e05317f1ec2))

* Slaves ([`02dc9be`](https://github.com/eyeonus/Trade-Dangerous/commit/02dc9bebb1cb7fa1c6b50035d9a376c24f7f1f99))

* Gulasch&#39;s credit ([`9560aa4`](https://github.com/eyeonus/Trade-Dangerous/commit/9560aa4ea1413d005c8c03cac6a7ba665c408bc3))

* Yay, they fixed the order of Microbial/Mineral ([`064c65a`](https://github.com/eyeonus/Trade-Dangerous/commit/064c65a00c78e72a24911aea75669c211db07882))

* Merged in cmdrgulsch/tradedangerous (pull request #41)

Added Stations and changed corrections.py for Opala ([`2d33953`](https://github.com/eyeonus/Trade-Dangerous/commit/2d33953af7172b78e9eaf1f453c9133f55ee6089))

* Merged kfsone/tradedangerous into master ([`d5b0d20`](https://github.com/eyeonus/Trade-Dangerous/commit/d5b0d20833b0ee2fe1b548efa53ac211673f4db4))

* Ross 733 Stations ([`32ebc58`](https://github.com/eyeonus/Trade-Dangerous/commit/32ebc583b0aba6b9fdee26edb5988bc215a3eabe))

* Merged kfsone/tradedangerous into master ([`7b79172`](https://github.com/eyeonus/Trade-Dangerous/commit/7b79172d981e037be0809789918b470e0823d8d5))

* Giant documentation cleanup ([`64e838c`](https://github.com/eyeonus/Trade-Dangerous/commit/64e838c8d768bc61656422636130e3297494b21f))

* Scripts need to be executable ([`9a1b9a9`](https://github.com/eyeonus/Trade-Dangerous/commit/9a1b9a9082911d7de2848bccc12c8118fdbab690))

* Merged in Mhughes2k/tradedangerous/StationsOnNav (pull request #42)

Added option to display station count in navigation ([`5d49051`](https://github.com/eyeonus/Trade-Dangerous/commit/5d490518414ea3579d38df5bdaa7e96e30dce44a))

* Added stations ([`1b61a1d`](https://github.com/eyeonus/Trade-Dangerous/commit/1b61a1d538385915215437ef2f9a46ba18bae292))

* reverted corrections.py ([`34e290f`](https://github.com/eyeonus/Trade-Dangerous/commit/34e290f1b0e6a8b2413c5526a27d71b0f8cd648d))

* Added option to display station count in navigation ([`e68dad7`](https://github.com/eyeonus/Trade-Dangerous/commit/e68dad7ec278a874bff880755394d253f45ff57d))

* Added --ages to local command ([`070f579`](https://github.com/eyeonus/Trade-Dangerous/commit/070f57950e4d196ec68b5c529f21769f406695ae))

* Improvements to genSystemsInRange

gsir now uses the database to reduce the number of systems it has to check and avoids a looped conditional when the cache is already &#34;big enough&#34;. Also, gsir now returns sqrt()d values ([`0c126b0`](https://github.com/eyeonus/Trade-Dangerous/commit/0c126b07302276eedf417ed668a4501829967183))

* Merged kfsone/tradedangerous into master ([`206a02c`](https://github.com/eyeonus/Trade-Dangerous/commit/206a02c949cff346c6466923c1b1760d75ba3255))

* Issue #79: support for &#39;--avoid&#39; in &#39;nav&#39; command

If a station name is given, it assumes you want to avoid the
system the station is in. ([`53f53a1`](https://github.com/eyeonus/Trade-Dangerous/commit/53f53a1f7c01bc117a921060ce078e0003654106))

* Merged kfsone/tradedangerous into master ([`ab48477`](https://github.com/eyeonus/Trade-Dangerous/commit/ab484770ab63fa9943058f0614bca19879c19454))

* Remove Seting ([`ca6137d`](https://github.com/eyeonus/Trade-Dangerous/commit/ca6137d3450ed640fa9724c18dea1dc708e9c0e2))

* Merged in mbcx4jrh/tradedangerous (pull request #40)

Removing System: Seting ([`3ccdad4`](https://github.com/eyeonus/Trade-Dangerous/commit/3ccdad4206451f0f1ab8d7a065c82d279db04883))

* Added Station and distances. Deleted Leoniceno Camp which is not part of Gamma 1.05 ([`39e5be5`](https://github.com/eyeonus/Trade-Dangerous/commit/39e5be505b1bb2f3cf9ca08c77568f6e1fb81901))

* Added some more stations ([`6989819`](https://github.com/eyeonus/Trade-Dangerous/commit/69898191458d11c468c99001364c46b89af3da2c))

* Added Stations ([`6dc0df9`](https://github.com/eyeonus/Trade-Dangerous/commit/6dc0df9a1a5f3d92c3e06d080498dfe0eebebcc8))

* Delete for double Opala ([`172fb72`](https://github.com/eyeonus/Trade-Dangerous/commit/172fb720cc897dfce33569d04b2bf28835611334))

* Merged kfsone/tradedangerous into master ([`f64c4f7`](https://github.com/eyeonus/Trade-Dangerous/commit/f64c4f7e717de930d2a19b48816c01d2c628cf63))

* Removed &#34;Seting&#34; system from csv. Varified it does not exist at all in Gamma 1.05 ([`b429df6`](https://github.com/eyeonus/Trade-Dangerous/commit/b429df6191e2139265ac577f997393e750d0e513))

* Merged kfsone/tradedangerous into master ([`130cfec`](https://github.com/eyeonus/Trade-Dangerous/commit/130cfec089970bda196b09924ceeeac91a3385ac))

* Merged kfsone/tradedangerous into master ([`aa96ed1`](https://github.com/eyeonus/Trade-Dangerous/commit/aa96ed14f4bd9b8cc3ed6954d89742c4e0c15a4d))

* more stations ([`f9659e7`](https://github.com/eyeonus/Trade-Dangerous/commit/f9659e73d72950be6bcd8ad3eecdb978c8717fcc))

* Merged in orphu/tradedangerous/stations (pull request #39)

Stations and distances. ([`b457104`](https://github.com/eyeonus/Trade-Dangerous/commit/b457104e86fe248b5c52e16c7823bb5dfd2c4bf9))

* More stations ([`1b27dea`](https://github.com/eyeonus/Trade-Dangerous/commit/1b27dea87d035ccd6732eb064e8e54e2a92716c3))

* Merged kfsone/tradedangerous into master ([`01d519d`](https://github.com/eyeonus/Trade-Dangerous/commit/01d519d6232d0c2344b2b456b453ba2eb500107e))

* Merge branch &#39;master&#39; into stations

Conflicts:
	data/Station.csv ([`b08e34f`](https://github.com/eyeonus/Trade-Dangerous/commit/b08e34fbdd524372da78035fce4d447293dcb11b))

* Merged kfsone/tradedangerous into master ([`f253a74`](https://github.com/eyeonus/Trade-Dangerous/commit/f253a7413185456fd56f188d894ee1df856b599c))

* Beatty port is a LONG way out ([`05cba02`](https://github.com/eyeonus/Trade-Dangerous/commit/05cba026c42085ec62d641669d12fcd7fc3e0aa5))

* Heike/Braun Enterprise ([`0ed892b`](https://github.com/eyeonus/Trade-Dangerous/commit/0ed892bbb72ba502f6c2fa1fb45dc0010e48fa55))

* Added window position args to update ([`a8515cb`](https://github.com/eyeonus/Trade-Dangerous/commit/a8515cb7dff04d5c9b6b89886ff583dae7dbd32a))

* More stations and distances. ([`8fade27`](https://github.com/eyeonus/Trade-Dangerous/commit/8fade27caceba75615f7d62ba0315342f5ba8eed))

* 48 more stations ([`9ffcfcd`](https://github.com/eyeonus/Trade-Dangerous/commit/9ffcfcd1be55663d86f439852682e677831c10d7))

* Additional stations and distances. ([`e1ebcf4`](https://github.com/eyeonus/Trade-Dangerous/commit/e1ebcf4f41832bbf5376b50e3f692067fdbe0d5a))

* Fixed the problem with Zamk/Zamka ([`544098d`](https://github.com/eyeonus/Trade-Dangerous/commit/544098d3db9cf69d0881b5221126d5d72d56b315))

* Added download progress to import ([`8a6421d`](https://github.com/eyeonus/Trade-Dangerous/commit/8a6421d02d8cdaddd2def24da0bdd58d2a8e2fea))

* Correction for Ama/Werner ([`92716cf`](https://github.com/eyeonus/Trade-Dangerous/commit/92716cf126c51a7510b445000ecef628c4a101c5))

* Missed a script (tdloc) ([`9885690`](https://github.com/eyeonus/Trade-Dangerous/commit/9885690f6fa9e360018c474788fffa5bdd82a758))

* v6.1.7 ([`b3a10d8`](https://github.com/eyeonus/Trade-Dangerous/commit/b3a10d8cf36b427083a3e74be821193aafd5278f))

* Lenience for the difference between prices ([`1c878e1`](https://github.com/eyeonus/Trade-Dangerous/commit/1c878e143ce311ecb24f0eee49b743d11c090d00))

* Added bash scripts to make life easier ([`de558cf`](https://github.com/eyeonus/Trade-Dangerous/commit/de558cfcc21ca7be82a8163eb34792b03a9e0945))

* Merged kfsone/tradedangerous into master ([`4d0fc6c`](https://github.com/eyeonus/Trade-Dangerous/commit/4d0fc6c2c7b7b9b44d918ccc95f5b8544b145dae))

* Ignore duplicates caused by a correction ([`95a3eed`](https://github.com/eyeonus/Trade-Dangerous/commit/95a3eedef579b5d47049b90ce5dcb25152cc2ce5))

* Merge remote-tracking branch &#39;cmdrgulsch/tradedangerous/sync-maddavo-stations_2014-12-07&#39;

Conflicts:
	corrections.py
	data/Station.csv ([`baf720a`](https://github.com/eyeonus/Trade-Dangerous/commit/baf720ad91e324329c2b978d61dde62195540fb5))

* Merge branch &#39;master&#39; of bitbucket.org:kfsone/tradedangerous ([`de7910d`](https://github.com/eyeonus/Trade-Dangerous/commit/de7910d4594ff4cabf6f1b67e42e409ae196ab74))

* Merged in cmdrgulsch/tradedangerous/cmdrgulsch/3-new-stations-1417951501466 (pull request #36)

4 new stations ([`4a95828`](https://github.com/eyeonus/Trade-Dangerous/commit/4a9582816cf9b3ec9bd4567dec0c8e580bb80b0b))

* Metcalf distance ([`11c9306`](https://github.com/eyeonus/Trade-Dangerous/commit/11c93069445c930f9e49951b5fea2b968ff383a9))

* Merged in orphu/tradedangerous/correct (pull request #38)

Corrected Meredith Station to &#34;City.&#34; Added the distance because why not? ([`cce47b0`](https://github.com/eyeonus/Trade-Dangerous/commit/cce47b0b3f8f0444bb87d96c80e401e185c4ce4c))

* Additional distances. ([`8a7f0cb`](https://github.com/eyeonus/Trade-Dangerous/commit/8a7f0cbdbb55a4223577aa330d48db5fa954cf5e))

* Some more distances. ([`53c4156`](https://github.com/eyeonus/Trade-Dangerous/commit/53c415680ffac7d32065b9806067a7f390c0d09c))

* Additional stations. ([`3153cd6`](https://github.com/eyeonus/Trade-Dangerous/commit/3153cd665ab90913588dccb5ab3d0a01971f0b42))

* Distances for Lave. ([`908523a`](https://github.com/eyeonus/Trade-Dangerous/commit/908523a3874d0b93250ce037d1c5bad0db7a1433))

* Corrected Meredith City. ([`1a5c074`](https://github.com/eyeonus/Trade-Dangerous/commit/1a5c07423abc7421dc6e787604f3f57c64464488))

* added G 139-50/FILIPCHENKO to corrections.py ([`d74bebd`](https://github.com/eyeonus/Trade-Dangerous/commit/d74bebd0f32f8205673ff8450fbdff2b8de44cb2))

* Added 2 more stations and corrected G 139-50/Filipchenko City ([`97d0f59`](https://github.com/eyeonus/Trade-Dangerous/commit/97d0f5961ea82008279e5d813567f342bd6deaef))

* Merged kfsone/tradedangerous into master ([`5d91b51`](https://github.com/eyeonus/Trade-Dangerous/commit/5d91b51caa668b21b670ffb42b5e04d2869b8287))

* correction for Opala/Zamka Platform ([`7fa0df2`](https://github.com/eyeonus/Trade-Dangerous/commit/7fa0df21e97060e6ef0adfd3f2c648434760ff8a))

* Corrected OPALA/Zamka Platform ([`41b742a`](https://github.com/eyeonus/Trade-Dangerous/commit/41b742a51d9b5c915810a300a9b1972c75e042f9))

* added line ([`b50e57e`](https://github.com/eyeonus/Trade-Dangerous/commit/b50e57e3f4cc07c3266f7b1b362ce5d4a6dfd1f6))

* Synced stations with Maddavo&#39;s ([`90f234a`](https://github.com/eyeonus/Trade-Dangerous/commit/90f234a9f4cc5a358f01d78cdd69516cf87a12e5))

* New station ([`baab779`](https://github.com/eyeonus/Trade-Dangerous/commit/baab77968e3258007a55cf99fd317d13849daa9d))

* 3 new stations ([`2a90888`](https://github.com/eyeonus/Trade-Dangerous/commit/2a908885e86a24a5b461cb8d426fa70b4c4c3bd3))

* Added &#39;--age&#39; option to &#39;buy&#39; sub-command

Shows the age of the data items so you can tell how likely
it is you&#39;re about to waste your time. ([`e31b7eb`](https://github.com/eyeonus/Trade-Dangerous/commit/e31b7eba3cf5b7e944b4c58f02d6aacdf3f4ac74))

* Aritimi station distances ([`b80bea1`](https://github.com/eyeonus/Trade-Dangerous/commit/b80bea1346a6b7a48ce46794b5a216250efccb2b))

* Distance for Vela port ([`17302da`](https://github.com/eyeonus/Trade-Dangerous/commit/17302da712f6d74d501708ac85782a45d6548b77))

* Merged in orphu/tradedangerous/local (pull request #35)

A few additional stations. ([`405ebd5`](https://github.com/eyeonus/Trade-Dangerous/commit/405ebd575c7b81cc9312144dbe8cc4553395b44d))

* Merge branch &#39;master&#39; of bitbucket.org:orphu/tradedangerous ([`5f107d0`](https://github.com/eyeonus/Trade-Dangerous/commit/5f107d087cec29e531556fbf9098de387ca7b119))

* A few additional stations, ([`ef08773`](https://github.com/eyeonus/Trade-Dangerous/commit/ef08773daa34a124e752fd49e94b1b05283bd90e))

* Merged kfsone/tradedangerous into master ([`0f53615`](https://github.com/eyeonus/Trade-Dangerous/commit/0f536154831d18a5acb34a90bd3d2b05d6523137))

* Open text files in &#39;universal end-of-line&#39; mode ([`601f47b`](https://github.com/eyeonus/Trade-Dangerous/commit/601f47b2e0a9d309ab4dd6f4b9eea5f4536ebfca))

* Added &#34;--start-jumps&#34; and &#34;--empty&#34; to &#34;run&#34; ([`2edab90`](https://github.com/eyeonus/Trade-Dangerous/commit/2edab90240cb8e864efcaed17df2d35f20a8efc3))

* Include origin system in &#34;local&#34; output ([`0a7de1a`](https://github.com/eyeonus/Trade-Dangerous/commit/0a7de1a1d0be6fb0c26292c7bbd2192e671d6ef5))

* ui_order comes from Item rather than StationItem now ([`e3ad914`](https://github.com/eyeonus/Trade-Dangerous/commit/e3ad9140dcb23850cb154d8f3bf4f3640fd8a3b3))

* Merged in bgol/tradedangerous/devel (pull request #34)

Use dataDir as default for the csv export (and ignore it for the database when using &#34;--db&#34;) ([`d4536bc`](https://github.com/eyeonus/Trade-Dangerous/commit/d4536bca817691021fa26a6ce39211f09050629b))

* Do not use the dataDir if the DB-name was given on the commandline. ([`c75adff`](https://github.com/eyeonus/Trade-Dangerous/commit/c75adffb4ec1ddc01cacf96082d0fa4d59888e74))

* Use default dataDir of tradeenv ([`abeb5a7`](https://github.com/eyeonus/Trade-Dangerous/commit/abeb5a72dce633b2466f596c9e0e58ba0a950e04))

* Thank you, Bernd ([`098f860`](https://github.com/eyeonus/Trade-Dangerous/commit/098f8601945d23bb22ea1bcf79742ba2fca5f88e))

* Merged in bgol/tradedangerous/devel (pull request #33)

station update, one new, some distances, order ([`369c66f`](https://github.com/eyeonus/Trade-Dangerous/commit/369c66fb6e48c44e5913297d4c95c2fe1743e813))

* Changes from Eggplant ([`0b02f7b`](https://github.com/eyeonus/Trade-Dangerous/commit/0b02f7b789223921c6d86fab0e8a19b2f8ed6da6))

* Distance to Perrin Settlement, because it&#39;s a bit far ([`5a52b53`](https://github.com/eyeonus/Trade-Dangerous/commit/5a52b530d4aa69d0f2797dc78115df61d90e0d29))

* Merged in orphu/tradedangerous/datapath (pull request #31)

This makes it possible to easily point to another data directory when importing tradedb into other scripts. ([`faaab73`](https://github.com/eyeonus/Trade-Dangerous/commit/faaab73bd1fdbd15a36737be96bf1f656094f605))

* station update, one new, some distances, order ([`f4f71e3`](https://github.com/eyeonus/Trade-Dangerous/commit/f4f71e399cd69979b69a8cd62d8efc399dc5382e))

* Merge branch &#39;master&#39; of bitbucket.org:orphu/tradedangerous ([`0debfc5`](https://github.com/eyeonus/Trade-Dangerous/commit/0debfc567abe38937323d42cbd980e74b85acd49))

* Merged kfsone/tradedangerous into master ([`820b499`](https://github.com/eyeonus/Trade-Dangerous/commit/820b499350800a29567d190f35de73f67199e473))

* Typo correction ([`de64239`](https://github.com/eyeonus/Trade-Dangerous/commit/de64239466752d2285c72d9dc21ac86e1f5ab6da))

* Fixed Halai stations ([`4545a5b`](https://github.com/eyeonus/Trade-Dangerous/commit/4545a5bf66366298386d6bb33feec0f06eaae715))

* &#34;run&#34; --from now accepts a System name ([`1d3df72`](https://github.com/eyeonus/Trade-Dangerous/commit/1d3df72d53bddfe1d39bf1766fd53492a0f620c8))

* More station data ([`00cb850`](https://github.com/eyeonus/Trade-Dangerous/commit/00cb85077d9d7ed4657ff8a2e5b232466d0a3167))

* New stations ([`7561491`](https://github.com/eyeonus/Trade-Dangerous/commit/7561491a9dcb8605b42daac92a6f461ed4b3b0e2))

* CHANGES.txt ([`6af5dd5`](https://github.com/eyeonus/Trade-Dangerous/commit/6af5dd59f05510dff6fbe7d43b21ad666e5393dc))

* Additional sanity checking on prices ([`e74bc8c`](https://github.com/eyeonus/Trade-Dangerous/commit/e74bc8ce7db538accad72853e032b9bf4ca057d7))

* Sanity check BUY &gt;= SELL ([`12d4658`](https://github.com/eyeonus/Trade-Dangerous/commit/12d465823bbad4e9f037197c588982a79834aa5d))

* Get route correct way around when there&#39;s only one hop ([`40d8299`](https://github.com/eyeonus/Trade-Dangerous/commit/40d8299c8b49f214fdeb2b6e45f227479f2dd4ee))

* Merged in bgol/tradedangerous/devel (pull request #32)

Bug in cache.py and two corrected station ([`6d437ad`](https://github.com/eyeonus/Trade-Dangerous/commit/6d437ad5548b4faee5eedab1b5b07f7e95faf39e))

* Merged kfsone/tradedangerous into master ([`7ae95c5`](https://github.com/eyeonus/Trade-Dangerous/commit/7ae95c5571678213ceba84dcca0120b55e72cfdf))

* only make the deprecation check in debug mode (as per owner request) ([`be00b01`](https://github.com/eyeonus/Trade-Dangerous/commit/be00b01c230027d380103f76129ff115dcbaa08d))

* disambiguation &#39;systems&#39; should be a set not a list ([`5457f0b`](https://github.com/eyeonus/Trade-Dangerous/commit/5457f0b0d3b28177d5e9f63a4827a04fb6f041da))

* Import all the commands at the start of trade.py ([`05b73c4`](https://github.com/eyeonus/Trade-Dangerous/commit/05b73c42141065b6c4877cf2aa4ae793eefd2abd))

* Fixed missing array decl in tradedb

AmbiguityError resolution in lookupPlace wasn&#39;t creating the array to store systems in. ([`cf5d763`](https://github.com/eyeonus/Trade-Dangerous/commit/cf5d763f6348d4a9e20ce4c305cd7fe667c0d482))

* Fixed typo in formatting.py ([`9ebfbbd`](https://github.com/eyeonus/Trade-Dangerous/commit/9ebfbbd906ed58f8b4eae35ac549d36ee6ce396c))

* Fixed bug with corrections in cache.py ([`bd375c4`](https://github.com/eyeonus/Trade-Dangerous/commit/bd375c4758fb8b2ad7a81556b0959d60ddba36c0))

* Corrected two stationnames:
	Eravate/Askerman Market -&gt; Ackerman Market
	Yakabugai/Serebov Station -&gt; Serebrov Station ([`2a80574`](https://github.com/eyeonus/Trade-Dangerous/commit/2a8057461b0afc5fed14621cf2bf79b3aa3bb34f))

* The &#34;deprecationFn&#34; must always be initialized. ([`9d2d72d`](https://github.com/eyeonus/Trade-Dangerous/commit/9d2d72d2b32e6ac5faed0c06bc194ad654c7ba54))

* Merge branch &#39;master&#39; of bitbucket.org:orphu/tradedangerous ([`9d0dbef`](https://github.com/eyeonus/Trade-Dangerous/commit/9d0dbef8b651db8cfaf1c2d794ba30de96bffd7a))

* Merged kfsone/tradedangerous into master ([`714f007`](https://github.com/eyeonus/Trade-Dangerous/commit/714f00780f3bebc9600ec53dfc59b3db6a4f8ef8))

* Optimization and improvements to &#34;nav&#34; command

Using &#39;-vv&#39; will output the direct distance left to the target (so you can see when you are having to go around to reach a destination) ([`79c654b`](https://github.com/eyeonus/Trade-Dangerous/commit/79c654b6bb31f9bc37288fda70ac2d11e2d349ce))

* Added System.distToSq

Calculates distance between two stars ([`7740fc8`](https://github.com/eyeonus/Trade-Dangerous/commit/7740fc8a5239e5ed21b3c72f4f0983c28cc03f91))

* Minor optimization for genSystemsInRange ([`e5d4393`](https://github.com/eyeonus/Trade-Dangerous/commit/e5d439321d2a9dd128d454c9dad09fa4facbcb96))

* Merge branch &#39;master&#39; into datapath ([`83d7662`](https://github.com/eyeonus/Trade-Dangerous/commit/83d766283d049ef89a0b6c41166524b804adaab3))

* Merge branch &#39;master&#39; of bitbucket.org:orphu/tradedangerous ([`b4b5a2b`](https://github.com/eyeonus/Trade-Dangerous/commit/b4b5a2b38c63e044167314cc44306c5761f96328))

* Merged kfsone/tradedangerous into master ([`0d26755`](https://github.com/eyeonus/Trade-Dangerous/commit/0d2675540109b910e91b3fb236ef54c215ff0383))

* Performance pass for buildcache/import

Improved performance of .prices parsing to shave several seconds off the time it takes to build the cache. ([`8afc5ed`](https://github.com/eyeonus/Trade-Dangerous/commit/8afc5edb07e95a547ce6584fe30fb8b41ad43b30))

* Rename dataPath to dataDir. ([`47e53f7`](https://github.com/eyeonus/Trade-Dangerous/commit/47e53f7740205a8819610f7f9454dba859f0068b))

* Merge branch &#39;master&#39; into datapath

Conflicts:
	tradedb.py ([`65923c2`](https://github.com/eyeonus/Trade-Dangerous/commit/65923c2f930a7c2e257e59d42e730108f155ea5c))

* Only try system-specific corrections for station names ([`87ca598`](https://github.com/eyeonus/Trade-Dangerous/commit/87ca598fa6f23a3dea90ea678ba3fc13b3cb500a))

* &#34;--supply&#34; update switch is now deprecated ([`6fb8f08`](https://github.com/eyeonus/Trade-Dangerous/commit/6fb8f084f3dc6c7011febe1c36db2f2894c8edb5))

* Herptimization

Ok - so we were spending ~20ms processing avoids on startup when no avoids were specified. Reduced that to .2ms. ([`97029a8`](https://github.com/eyeonus/Trade-Dangerous/commit/97029a8cdc5f692cc5cb1c4ef266d291c1360c97))

* Optimization pass of dump prices

Reduced time to generate .prices file on my macbook air from 3.xs to 1.2s; part of this includes always listing supply now. People who don&#39;t want to bother with supply can just leave it empty.

This in turn will feed into not having to worry about whether or not supply values are supplied in the .prices parser making it much faster ([`ebba4d2`](https://github.com/eyeonus/Trade-Dangerous/commit/ebba4d2b3cdf85af652b4cc59e1aecf53728e764))

* Merge branch &#39;master&#39; of bitbucket.org:orphu/tradedangerous ([`b61a797`](https://github.com/eyeonus/Trade-Dangerous/commit/b61a797c555b9619eb80afda167887aa40da5708))

* Merged kfsone/tradedangerous into master ([`fa7fa11`](https://github.com/eyeonus/Trade-Dangerous/commit/fa7fa117c59beef8cb33267774a496e00edf539b))

* We know item names are going to be unique in future ([`fc35b35`](https://github.com/eyeonus/Trade-Dangerous/commit/fc35b356d26f3aedf642ae3c467128f319f1c898))

* Merged kfsone/tradedangerous into master ([`ff0f0df`](https://github.com/eyeonus/Trade-Dangerous/commit/ff0f0df36a32b2c9036e83e4f57e3e75ecb8f886))

* LTT 16016 systems ([`b4f411d`](https://github.com/eyeonus/Trade-Dangerous/commit/b4f411d625fddecf007020115945ca8038de1dd5))

* Typo in Gytons ([`c0eba25`](https://github.com/eyeonus/Trade-Dangerous/commit/c0eba2547e0a3cfa92512c1b1d86b2d580ef6dbf))

* Fixed typo in luyten&#39;s star ([`de034bb`](https://github.com/eyeonus/Trade-Dangerous/commit/de034bb7474f9be27b23581d30fc83a868b923f8))

* Stations from Maddavo ([`ea14b8a`](https://github.com/eyeonus/Trade-Dangerous/commit/ea14b8a5f44d163ac766fade62bb72fdf25a88a8))

* Big glut of new stations ([`a82f552`](https://github.com/eyeonus/Trade-Dangerous/commit/a82f5522fb848615b6abdf50f0a4b7c44304d6ba))

* Diacritics in names, great. ([`3c88b30`](https://github.com/eyeonus/Trade-Dangerous/commit/3c88b30dad6441b62c7d699904660c8debd81206))

* Normalized use of dbFilename in update_cmd ([`4a27a15`](https://github.com/eyeonus/Trade-Dangerous/commit/4a27a15bc2526136ac388d519a87b9422f5bb393))

* Normalization pass on export_cmd ([`0ef95e5`](https://github.com/eyeonus/Trade-Dangerous/commit/0ef95e5fe8428ce7d30cbe72767d41fdf7abb271))

* Sloppy code removed ([`3269e29`](https://github.com/eyeonus/Trade-Dangerous/commit/3269e29cebbe88461c147f816d7be211ed0d91d3))

* unused argument to TradeDB.load ([`a42efd8`](https://github.com/eyeonus/Trade-Dangerous/commit/a42efd8ad4646e382cd23f5ca83482672d3a4e30))

* Streamlined argument set for buildCache ([`7af37fa`](https://github.com/eyeonus/Trade-Dangerous/commit/7af37fa77ba6800e5f10f72b32f23665e6c4f0c4))

* More consistent use of Path ([`470614b`](https://github.com/eyeonus/Trade-Dangerous/commit/470614b6e9e52397fb78e9ea72e1c413bf2414a5))

* TradeDB.dbURI becomes TradeDB.dbFilename

Incremental work to make it easier to override the data directory location ([`e0f481b`](https://github.com/eyeonus/Trade-Dangerous/commit/e0f481bdbcf22dc318a0d8d4f8589fb87bab425c))

* Made TradeDB take a load flag, defaulting to True.

This allows me to eliminate the notion of an uninitialized TradeDB
in many of the command tools with a view to improving the line of
separation between TradeDB and TradeEnv. ([`39f193c`](https://github.com/eyeonus/Trade-Dangerous/commit/39f193c8d9d1436f768b6e62ce7b3457e88437a8))

* Cleaned up the corrections list ([`287d7ff`](https://github.com/eyeonus/Trade-Dangerous/commit/287d7ff3357f11ab2db85367534a4e1ba6cd4cad))

* moved &#39;corrections&#39; out of data directory ([`97c0bd0`](https://github.com/eyeonus/Trade-Dangerous/commit/97c0bd0a0915cf50e1ad8852788429adcdf92d7a))

* Removed ships.py ([`ef393ee`](https://github.com/eyeonus/Trade-Dangerous/commit/ef393eeb5d73186a940d8b18238f1b2967b75ad8))

* Moved dataPath to TradeEnv. ([`c8e939d`](https://github.com/eyeonus/Trade-Dangerous/commit/c8e939d0b8f3cc5a26a2b4626e2b7f6d8e65f9f0))

* Simplify a call and remove the need to import os. ([`5364c69`](https://github.com/eyeonus/Trade-Dangerous/commit/5364c69606b98ae6afc27ca08c14c670300968d0))

* Merged kfsone/tradedangerous into master ([`2309b01`](https://github.com/eyeonus/Trade-Dangerous/commit/2309b01a0b6c8cc1e82364f1df97eec3b6798ecf))

* Merge branch &#39;master&#39; into datapath ([`f411ccf`](https://github.com/eyeonus/Trade-Dangerous/commit/f411ccff874567d9e100940b6c5d4f2334293529))

* Merge branch &#39;master&#39; of bitbucket.org:orphu/tradedangerous ([`efad1fa`](https://github.com/eyeonus/Trade-Dangerous/commit/efad1fad04d02e388a1a841e66f9947f60990152))

* Merged kfsone/tradedangerous into master ([`674a70e`](https://github.com/eyeonus/Trade-Dangerous/commit/674a70e9f73c0e61fb8f21ed2b5390cdcd5b33e8))

* Adds a configurable data path to TradeDB. ([`6f98a9b`](https://github.com/eyeonus/Trade-Dangerous/commit/6f98a9ba36228036f448cf81c43651cb9ae54381))

* Include unavailable items in updated.prices

This makes it easier to be explicit when exporting data to a 3rd party that the items is not just missing but is unavailable ([`697db71`](https://github.com/eyeonus/Trade-Dangerous/commit/697db71c9994501d30de0e7e358f462cfd5dec69))

* README explains that import is per-station destructive ([`690f0f3`](https://github.com/eyeonus/Trade-Dangerous/commit/690f0f3bd04086f3c3df377e47d3d7a3a898d269))

* 155 new stations from RedWizard ([`8fd8ecc`](https://github.com/eyeonus/Trade-Dangerous/commit/8fd8ecc5b5f52c33ed3d19f56aad797838903112))

* Merge towards RedWizard.

Systems are sorted with sort -f -t, ([`b786016`](https://github.com/eyeonus/Trade-Dangerous/commit/b786016393455149f272a9c48d0bc85e23e61d7d))

* RW is calling Gamma1 Gamma ([`9cdb1f2`](https://github.com/eyeonus/Trade-Dangerous/commit/9cdb1f2ea9553e8a6903ff0dda57a4c2b474081a))

* Updating Added so I can merge RedWizard ([`379af0c`](https://github.com/eyeonus/Trade-Dangerous/commit/379af0c43be9578c9795a73ebd1ad557d7c3afa6))

* Prepping System.csv for merge with RedWizard ([`8937931`](https://github.com/eyeonus/Trade-Dangerous/commit/8937931ff878bd3c84a242fe501d78c98787b24d))

* Made version check explicitly check for 3.4.1 ([`ec943e5`](https://github.com/eyeonus/Trade-Dangerous/commit/ec943e56e2c3dad4207593738e13a658eeb76ded))

* Merge branch &#39;master&#39; of bitbucket.org:orphu/tradedangerous ([`b5148f5`](https://github.com/eyeonus/Trade-Dangerous/commit/b5148f560a08e0f5665970cbb90355d0b4d87d61))

* Merged kfsone/tradedangerous into master ([`6a8fc3c`](https://github.com/eyeonus/Trade-Dangerous/commit/6a8fc3caa4e978885c439b496ac313adbe38b801))

* Credit for Eggplant&#39;s stations ([`72810bd`](https://github.com/eyeonus/Trade-Dangerous/commit/72810bdcb1ca88f27348f993a97a36474f3692f7))

* Fixed issues with same-system hops ([`0bdc62e`](https://github.com/eyeonus/Trade-Dangerous/commit/0bdc62ed1cfb93872deda6b83f8a9c16f4845793))

* Skip in-system hops when counting jumps ([`9bc342e`](https://github.com/eyeonus/Trade-Dangerous/commit/9bc342e0a6f3977b407e2584e8a1351c99803a73))

* Merged in orphu/tradedangerous/local (pull request #30)

Additional stations. ([`47bcb85`](https://github.com/eyeonus/Trade-Dangerous/commit/47bcb85b7a084c8dcefdba815194793b852fbb9d))

* Additional stations. ([`bd6f374`](https://github.com/eyeonus/Trade-Dangerous/commit/bd6f3748560a6b30d8dd500204409797ee23b590))

* Additional stations. ([`1be6729`](https://github.com/eyeonus/Trade-Dangerous/commit/1be67292809827ac7161aef064deeec12ddeac26))

* Merged kfsone/tradedangerous into master ([`afbe920`](https://github.com/eyeonus/Trade-Dangerous/commit/afbe9201b6f672f7e3b083e22166804b85c42173))

* Updated CHANGES ([`3611647`](https://github.com/eyeonus/Trade-Dangerous/commit/3611647a4cc64314f90016f4250593320a669f1b))

* Merged in bgol/tradedangerous/devel (pull request #29)

some more data (and corrected order) ([`57b3b7c`](https://github.com/eyeonus/Trade-Dangerous/commit/57b3b7c054e4255044f2802c0087a38ba41df799))

* Updated README to reflect the requirement of Python 3.4 ([`ae32656`](https://github.com/eyeonus/Trade-Dangerous/commit/ae32656125cf24bc1aeb420e5a6716b80515e1a1))

* Merged kfsone/tradedangerous into master ([`1a1a4e9`](https://github.com/eyeonus/Trade-Dangerous/commit/1a1a4e9f6adeba675d52c14d276617d39fae1d67))

* Ross 765 Stations ([`8d6bc7a`](https://github.com/eyeonus/Trade-Dangerous/commit/8d6bc7aeadff61f5369aed2cdc23a2bce26f2213))

* Missing import in nav_cmd ([`2687a49`](https://github.com/eyeonus/Trade-Dangerous/commit/2687a4951d97b8a95827eba8604114bdab239dc0))

* Fix for nav in the case of specifying a dest station ([`2686f84`](https://github.com/eyeonus/Trade-Dangerous/commit/2686f840ee4cdec653ba8a7d562cd7675147c57c))

* Stupid typo ([`716087f`](https://github.com/eyeonus/Trade-Dangerous/commit/716087fee4b34cf0455af2923c05ca18f2b1e78a))

* &#34;update&#34; now puts timestamps in updated.prices.

Also made it use &#34;place&#34;s for the start station. ([`f976f8a`](https://github.com/eyeonus/Trade-Dangerous/commit/f976f8a9973578b3c5f6539fe0360c6825aed70f))

* Changed commandenv to use lookupPlace for &#39;starting&#39; and &#39;ending&#39;

I&#39;ve replaces startSys and endSys with the simpler &#39;starting&#39; and &#39;ending&#39; which use lookupPlace. The command is then expected to check what it actually wants from a place and report accordingly. ([`fe34171`](https://github.com/eyeonus/Trade-Dangerous/commit/fe34171e9a2746f2e852b7f7329cd6bc43720ced))

* Herpage in the tradecalc debug ([`d0ad654`](https://github.com/eyeonus/Trade-Dangerous/commit/d0ad65450144a89dfa8133337caba9e59f15eb2b))

* Merge branch &#39;master&#39; into devel ([`0006252`](https://github.com/eyeonus/Trade-Dangerous/commit/0006252c35535d5446bbdb502514edcb078b3be0))

* Merged kfsone/tradedangerous into master ([`db55160`](https://github.com/eyeonus/Trade-Dangerous/commit/db55160ec24217e690e338064be46da2391412bb))

* v6.1.3 changes ([`2502e18`](https://github.com/eyeonus/Trade-Dangerous/commit/2502e188da269b743b9fbb08ee46281761e072ce))

* System/Station disambiguation improvements

TradeDB.lookupPlace now supports disambiguation of system
and station names.

System or Station: aulin, asellusprim  or  beagle2
Explicit System: @asellus
Explicit Station: /beagle or @/beagle
System/Station: primus/beag
Overkill: &#34;@asellus primus/beagle 2 landing&#34; ([`cc5a02d`](https://github.com/eyeonus/Trade-Dangerous/commit/cc5a02df7d00b5d752b814d34df0ea3dcbf6a4b3))

* Removing unused functions

Removed &#39;lookupStationExplicitly&#39; and &#39;distanceSq&#39; from TradeDB ([`3d829ac`](https://github.com/eyeonus/Trade-Dangerous/commit/3d829ac717ad7f7188730b44e6df050d5a4b251b))

* Fixes #66: avoid station avoiding entire system

Converted &#39;avoid&#39; to using &#39;places&#39; concept rather than using
systems and stations separately. We now ignore stations as
endpoints and systems as waypoints/endpoints, as expected. ([`c6e29eb`](https://github.com/eyeonus/Trade-Dangerous/commit/c6e29ebe8e1d3a4ec2c8662f7d9c75834a878c91))

* Case in Apala/jones terminal ([`8e635d7`](https://github.com/eyeonus/Trade-Dangerous/commit/8e635d715374821fb758fb75a535da13d89ce4b0))

* Annotation cleanup of getDestinations ([`291f63c`](https://github.com/eyeonus/Trade-Dangerous/commit/291f63c7a3e6088911798e954563ac80b4a356b4))

* some more data (and corrected order) ([`ca73818`](https://github.com/eyeonus/Trade-Dangerous/commit/ca73818ad44bee726fe9ba0f3054a88dab3217cf))

* Corrections to the header of the .SQL file ([`86dd777`](https://github.com/eyeonus/Trade-Dangerous/commit/86dd777e4d7ab80ede7dbd575490ddfc6fea780c))

* Another star ([`4fb7e87`](https://github.com/eyeonus/Trade-Dangerous/commit/4fb7e8716973fbe323bb5246e5eb429ced9724d9))

* Cephei Sectors from DRY4112S ([`c077711`](https://github.com/eyeonus/Trade-Dangerous/commit/c0777113ca16bf99a535e87ade0b9d81d7c2b6a4))

* LP 27-9 Stations ([`cbc80dd`](https://github.com/eyeonus/Trade-Dangerous/commit/cbc80dd1dc25f4476d11199f11b958980acf279d))

* Update for Tyr ([`bb1bd70`](https://github.com/eyeonus/Trade-Dangerous/commit/bb1bd704e8ab0e2cca290303ee70752ce3058903))

* Correction for Maujinagoto ([`f796d98`](https://github.com/eyeonus/Trade-Dangerous/commit/f796d9891df6d6cc3b3aee34cef2adad013759ee))

* More stations ([`df343ef`](https://github.com/eyeonus/Trade-Dangerous/commit/df343efc49b3559ef0bb4ad2831c22f680b13e45))

* Improved performance of nav command ([`71aecc8`](https://github.com/eyeonus/Trade-Dangerous/commit/71aecc82ae056ba850e30ad6ebb067aec09272da))

* Fixed bug reporting a bad item entry ([`593a932`](https://github.com/eyeonus/Trade-Dangerous/commit/593a93254a1acf3740d4986e5e4f51f0ac6718fd))

* Merged in bgol/tradedangerous/devel (pull request #28)

Some new data from my gameplay ([`b645f19`](https://github.com/eyeonus/Trade-Dangerous/commit/b645f19585b65b055b2564aaf0a4b7c2e09af099))

* One new System on the way EDSC could calculate ([`26a50b9`](https://github.com/eyeonus/Trade-Dangerous/commit/26a50b95069c30ec8c2667a9ee8f0ced82ec02a0))

* Some new data from my gameplay ([`92b9f5b`](https://github.com/eyeonus/Trade-Dangerous/commit/92b9f5b0a05ccdbedff68234de3056aa832d8f43))

* Fix for saving price updates ([`8f55c4e`](https://github.com/eyeonus/Trade-Dangerous/commit/8f55c4efba211a60dc164234e974e06b30cadb97))

* Let user know we saved their changes ([`90b021e`](https://github.com/eyeonus/Trade-Dangerous/commit/90b021e2d7db8a2f0da29f6413cddbbe013c8f5d))

* Update command now saves its .prices file ([`63996d4`](https://github.com/eyeonus/Trade-Dangerous/commit/63996d45aa881a68659da543b96887869cd32776))

* NLTT49528 stations ([`6a4434a`](https://github.com/eyeonus/Trade-Dangerous/commit/6a4434acc60987db025f7e43a05f9f5d70e34bf4))

* Hach corrections ([`f26e208`](https://github.com/eyeonus/Trade-Dangerous/commit/f26e2081061477c75405214bcee96dd0e959d60a))

* Fixed nav command wanting stations instead of systems ([`f012bfb`](https://github.com/eyeonus/Trade-Dangerous/commit/f012bfbccb686e4ae4d705fc052cf62a7c8ad438))

* &#39;run --to&#39; now accepts stations AND systems

e.g. specifying &#39;--to lhs64&#39; will try all stations in that system. ([`804ab98`](https://github.com/eyeonus/Trade-Dangerous/commit/804ab98c33143255ebf7e8561c694e389fa502c5))

* Minor fixes ([`2d9ad55`](https://github.com/eyeonus/Trade-Dangerous/commit/2d9ad553fc129f0f263b5f442d4926f824a8b75c))

* Don&#39;t try to parse Station/System objects as names ([`0ecebe6`](https://github.com/eyeonus/Trade-Dangerous/commit/0ecebe6d61ef1eeed32202752dd764e13c352219))

* Using &#39;lookupPlace&#39; for most station/system lookups now. ([`f3d9f20`](https://github.com/eyeonus/Trade-Dangerous/commit/f3d9f20fa1b552a7d709af50710829adb32e6290))

* let &#39;-q&#39; silence unknown warnings import with -i ([`10e132f`](https://github.com/eyeonus/Trade-Dangerous/commit/10e132f3d2aecf3089b8660ed2aed5bdbb76a2f5))

* Gazelle&#39;s changes ([`2f6cae1`](https://github.com/eyeonus/Trade-Dangerous/commit/2f6cae1fd584ea0967c8ce0f2033ae8f89d61eda))

* Merged in bgol/tradedangerous/devel (pull request #27)

CSV import/export update ([`24deffc`](https://github.com/eyeonus/Trade-Dangerous/commit/24deffc2fb26baf75ebf23904f943620f3fcf35e))

* Fix for &#39;update&#39; command without -S ([`6e0ae9e`](https://github.com/eyeonus/Trade-Dangerous/commit/6e0ae9ec4528256f29b1575f4748bb3b1a9be78d))

* Removed import-from-davo.py (use import instead) ([`1a00f82`](https://github.com/eyeonus/Trade-Dangerous/commit/1a00f822cf174808c9dc34b3ce353731dfe0982d))

* Allow import to retrieve files from the web.

Also added a --maddavo option to import which fetches daves&#39; prices. ([`8e1bd3e`](https://github.com/eyeonus/Trade-Dangerous/commit/8e1bd3ec7677827a86cd06580f202b78ed80da02))

* Typo ([`88b8a61`](https://github.com/eyeonus/Trade-Dangerous/commit/88b8a61b2b77aefcfb842a115b67ca6ad9c7d5d6))

* More conversions to using lookupPlace ([`bd7a836`](https://github.com/eyeonus/Trade-Dangerous/commit/bd7a8361cae6d3ab5497a51ede9006f2ee3e2d72))

* Corrected some system names where the &#39; was wrong ([`e9a5e05`](https://github.com/eyeonus/Trade-Dangerous/commit/e9a5e05ee089e6428a02225946ab5b93a49ea6f1))

* removed unused variable ([`5501dae`](https://github.com/eyeonus/Trade-Dangerous/commit/5501daecbbc356eb1fda1572878d7e3068aba0b4))

* Use the same naming for the prefixes in CSV importer/exporter ([`51b6829`](https://github.com/eyeonus/Trade-Dangerous/commit/51b68296d9a1bbb6f16e24f1d2bf1c1e6e4fc834))

* Added description of the new --delete-empty switch ([`4679226`](https://github.com/eyeonus/Trade-Dangerous/commit/4679226c7d00746b998269d899fbf68c322f63fb))

* Added comment about FK requirement ([`f1246da`](https://github.com/eyeonus/Trade-Dangerous/commit/f1246da70682d7b0c1b61a2d679fe52e7311fda3))

* Updated all CSV data files with new format. ([`a9497e2`](https://github.com/eyeonus/Trade-Dangerous/commit/a9497e26d4a4cd378c7a90d79b3b2577ae5ebc42))

* CSV importer/exporter can now handle UNIQUE with multiple columns as long
as the last FK resolves to a single column. ([`6a609d3`](https://github.com/eyeonus/Trade-Dangerous/commit/6a609d3876ccdf1f22aee33e86c5f37743ce1417))

* Merge branch &#39;master&#39; into devel ([`3785045`](https://github.com/eyeonus/Trade-Dangerous/commit/378504587b3ad788ab387488198bbc8a98c74f6b))

* Use an real UNIQUE index for &#34;unq&#34; prefix. ([`52328db`](https://github.com/eyeonus/Trade-Dangerous/commit/52328db29488bddf335ca97c67fbae5a6b469049))

* New command switch &#34;--delete-empty&#34; to delete CSV files without content. ([`7fe6978`](https://github.com/eyeonus/Trade-Dangerous/commit/7fe69783a04e0da60492131763d9f05d384302f0))

* Initial pass at &#34;lookupPlace&#34;

LookupPlace should replace &#34;lookupSystem&#34; and &#34;lookupStation&#34; because you&#39;re frequently going to wind up needing qualification.

It can accept a system or station name, or a string made of a &#34;system/station&#34; and use partials and ranked matching to try and do its best to find a singular match.

the &#34;system/station&#34; lookup is not implemented in this pass. ([`244f63b`](https://github.com/eyeonus/Trade-Dangerous/commit/244f63b8bf430f6df3bcb3dad5c4deacce645461))

* AmbiguityError now lists more candidates. ([`2655247`](https://github.com/eyeonus/Trade-Dangerous/commit/2655247a38906f0eb3c1075cc7b6e52857e90370))

* normalizedStr adjustments

In order to increase the much larger namespace, we&#39;re going to require users to sometimes be more specific in naming things. To support this, I&#39;ve made the normalizer a little less aggressive. This should be followed by some changes which make the lookup system a little more aggressive and also explain in more detail what the ambiguities that arise are. ([`6bb2241`](https://github.com/eyeonus/Trade-Dangerous/commit/6bb2241a616909918d64210c19b6682ff535ee6d))

* Fix for uninitialized &#39;debug&#39; value in some conditions ([`e031c8d`](https://github.com/eyeonus/Trade-Dangerous/commit/e031c8d424ea1a8a0aa59b4c30e4870f7e5f0a5f))

* stationByName was never used. ([`19cb1e0`](https://github.com/eyeonus/Trade-Dangerous/commit/19cb1e0872ae8790612410ebed61cc5a82cc682c))

* Restrict station names to unique-per-star ([`f5f783d`](https://github.com/eyeonus/Trade-Dangerous/commit/f5f783d8fd398d68f6b9321ef9dff276d37d4242))

* CSVs can now have a unique index on multiple fields ([`defefa0`](https://github.com/eyeonus/Trade-Dangerous/commit/defefa01ededd8742202b843d073f9d21403c6a1))

* Reduce the calls to python&#39;s upper() ([`6b50ca9`](https://github.com/eyeonus/Trade-Dangerous/commit/6b50ca9edef3f814e4213cf75b44ed8b5ca76175))

* More stations ([`83afd2b`](https://github.com/eyeonus/Trade-Dangerous/commit/83afd2bee6c30ab0b0c88dbe61354312d0b16c5d))

* More stations ([`0486752`](https://github.com/eyeonus/Trade-Dangerous/commit/04867528545533bb95b5ffffb94799864bffb0ba))

* Station overhaul ([`b8d5ec6`](https://github.com/eyeonus/Trade-Dangerous/commit/b8d5ec621d01ab72baf1cf45fc42105b4671c015))

* Changed SUPPLY column to STOCK

It&#39;s called STOCK elsewhere through-out the system and SUPPLY is an
overloaded term generally referring to EITHER demand or supply, see? ([`16757cd`](https://github.com/eyeonus/Trade-Dangerous/commit/16757cd8be14c8b16cd632f9987c1700aea28b3c))

* Optimization of .prices parsing/cache building ([`b1e2c72`](https://github.com/eyeonus/Trade-Dangerous/commit/b1e2c72b9736518822bb43bfe3e164eba624d515))

* Handle the case where the .prices file doesnt exist ([`b9be772`](https://github.com/eyeonus/Trade-Dangerous/commit/b9be772ef96fac525c629439041d84dfedd3f80b))

* Fix for args parsing error ([`ad61509`](https://github.com/eyeonus/Trade-Dangerous/commit/ad615098defb619392622f505f1d0a268fe3db9e))

* Made the update GUI significantly more user friendly. ([`ac62de5`](https://github.com/eyeonus/Trade-Dangerous/commit/ac62de55428c9601ea4b11008f6c3f7f0fe1409e))

* Big cleanup of the Update GUI. ([`5f377ed`](https://github.com/eyeonus/Trade-Dangerous/commit/5f377ed7f5554cb007728113a494a7cc92b348af))

* Fix for making focus follow the cursor properly. ([`b7e39d5`](https://github.com/eyeonus/Trade-Dangerous/commit/b7e39d571b2d81f383a458fd6e5d0f4648acc958))

* Merged in bgol/tradedangerous/devel (pull request #26)

Added description of &#34;export&#34; command. ([`ed8dac9`](https://github.com/eyeonus/Trade-Dangerous/commit/ed8dac96d377c4a57143fd4dc4451744e06c51cf))

* Added description of &#34;export&#34; command. ([`8ef4d2f`](https://github.com/eyeonus/Trade-Dangerous/commit/8ef4d2f64de3884d696b9089dbf394d456748bbe))

* Import WITHOUT a filename opens a file dialog ([`07c6721`](https://github.com/eyeonus/Trade-Dangerous/commit/07c6721ff2774384b56485e38647d99eb221bccb))

* Made it possible/easy to do optional positional arguments in command lines ([`5953f2e`](https://github.com/eyeonus/Trade-Dangerous/commit/5953f2ea1d3495dcd271e8551a2bf61638371cb3))

* Specifying &#39;-&#39; as a filename to import will present the user with an Open File dialog. ([`b1203e6`](https://github.com/eyeonus/Trade-Dangerous/commit/b1203e6f85c98fc3433875926a2d25243a71bd03))

* Added --ignore-unkown to import command ([`2fe8b87`](https://github.com/eyeonus/Trade-Dangerous/commit/2fe8b87e75ba29e5015ad9f452572e3ca269090c))

* Commands in alphabetical order ([`407b00d`](https://github.com/eyeonus/Trade-Dangerous/commit/407b00db32e59a93f8d34fdfdcc4e90e41cade85))

* Merge branch &#39;master&#39; of bitbucket.org:kfsone/tradedangerous ([`3552c92`](https://github.com/eyeonus/Trade-Dangerous/commit/3552c92e291b4d4fedbec1dd1c7b5f0e10f9f09d))

* Merged in bgol/tradedangerous/devel (pull request #23)

CSV Exporter ([`bad3e28`](https://github.com/eyeonus/Trade-Dangerous/commit/bad3e28db31ee620e829d00f45bd3a9289d984f5))

* Cleanup of local command ([`05cf8ed`](https://github.com/eyeonus/Trade-Dangerous/commit/05cf8ede466e08f799741e0c6630d823181b62c2))

* Merge branch &#39;master&#39; into devel

Conflicts:
	data/Added.csv ([`412690c`](https://github.com/eyeonus/Trade-Dangerous/commit/412690cb0f13439c3853b4fd421e8905e5bd731b))

* Stupid type in Added ([`8a0b4c3`](https://github.com/eyeonus/Trade-Dangerous/commit/8a0b4c39779e3c4cc09b61a936cbfdbeaf8a5008))

* Missing Added values ([`d0743db`](https://github.com/eyeonus/Trade-Dangerous/commit/d0743dbcc5600f64b2180b378595b73a6f87b2c7))

* Missing Added values ([`7f2ed9c`](https://github.com/eyeonus/Trade-Dangerous/commit/7f2ed9c570ff2650ab4ce90aa85862fc473cd030))

* Missing Added values ([`694a7e5`](https://github.com/eyeonus/Trade-Dangerous/commit/694a7e5a5b2afc96df6aa16610f1e3956977f296))

* Made unique column check case insensitive (per Bernd, thanks) ([`b7466e2`](https://github.com/eyeonus/Trade-Dangerous/commit/b7466e293e894244f30e49f599db87dbe7ab47ed))

* Training and Destination systems removed ([`d7dfa80`](https://github.com/eyeonus/Trade-Dangerous/commit/d7dfa8031b2a735fee11b360867189d9d72de44e))

* More stations ([`a97f035`](https://github.com/eyeonus/Trade-Dangerous/commit/a97f035594bc5c5e312c47f997075af1f9c6ea04))

* Change Log ([`33bf114`](https://github.com/eyeonus/Trade-Dangerous/commit/33bf114add3e2dca09193aa843c686eac22eb204))

* cache was mishandling deletes that could be renames ([`62db370`](https://github.com/eyeonus/Trade-Dangerous/commit/62db370b9bf7b22f70793dbe70fab62c5824b6cc))

* Bartoe Platform is no more (in Chemaku) ([`26bc7dd`](https://github.com/eyeonus/Trade-Dangerous/commit/26bc7ddd849355ac68b0077dbee1c3f731d98ad7))

* Unknown has 3 ns in it ([`a37939c`](https://github.com/eyeonus/Trade-Dangerous/commit/a37939c4eb23702bcc843c7465a7f9f0bede6dec))

* More stations ([`f677080`](https://github.com/eyeonus/Trade-Dangerous/commit/f677080cdcf7af3b3c48885dc2cf01bd3a980a73))

* Problem with default ctor for TradeDB ([`084e5df`](https://github.com/eyeonus/Trade-Dangerous/commit/084e5dfd08e1447e2f5f4c991ff6b801b07020fb))

* Allow debug parameter on TradeDB ([`755cbf3`](https://github.com/eyeonus/Trade-Dangerous/commit/755cbf38611cbe83bcb765e9786cddd53bd5cd25))

* Barf when someone uses a filename instead of a Path ([`d301468`](https://github.com/eyeonus/Trade-Dangerous/commit/d301468afc90ce03d93c42d920aa58cb30a66350))

* Experimental module for pulling and importing data from maddavo&#39;s site ([`c413a7c`](https://github.com/eyeonus/Trade-Dangerous/commit/c413a7c7cfbfcadd99a6724bf5649f04226b4e6a))

* Removed test systems ([`94d47da`](https://github.com/eyeonus/Trade-Dangerous/commit/94d47dac11165455bba62f25e9a069cf9b400e70))

* Missing items from CHANGES ([`3221971`](https://github.com/eyeonus/Trade-Dangerous/commit/32219714a6850c91033d3849fd8ad48590725149))

* maddavo&#39;s import of 20,000+ systems ([`0b0e8d4`](https://github.com/eyeonus/Trade-Dangerous/commit/0b0e8d43135690f883308390df79732f0a5e1a1d))

* Support for cProfiled runs ([`a31f201`](https://github.com/eyeonus/Trade-Dangerous/commit/a31f201dcbaf5124fe52d1467515e067b79b9c7a))

* fix over-aggressive normalization

diff-system-csvs was removing all punctuation and spaces, and there are now some system names which differ only by an apostrophe or a space. ([`8ab29c2`](https://github.com/eyeonus/Trade-Dangerous/commit/8ab29c24cc3825193186a4554512ba859b895aa8))

* Use unix style line ending. ([`174b0be`](https://github.com/eyeonus/Trade-Dangerous/commit/174b0becf925d2d6633db8882d05d81f2704767f))

* Enforce UTF-8 encoding of CSV files ([`929418a`](https://github.com/eyeonus/Trade-Dangerous/commit/929418a699f61a25057851d9078cdcaa82537832))

* Issue #63 Trade routes not across some routes

getDestinations was relying on system.links which only contains trading
destinations; that is, destinations that &#39;system&#39; is actively trading
with.

I&#39;ve moved System.getDestinations into TradeDB so that it can make use
of genSystemsInRange so that jump destinations are considered first
and then filtered when selecting for endpoints. ([`13b4a17`](https://github.com/eyeonus/Trade-Dangerous/commit/13b4a17e06f401d913b87585c9756dace94a5c94))

* More stations ([`4b8d054`](https://github.com/eyeonus/Trade-Dangerous/commit/4b8d05443eff415418e393da9b27e82d17c71f27))

* Merge branch &#39;master&#39; into devel ([`8dadf3d`](https://github.com/eyeonus/Trade-Dangerous/commit/8dadf3db6300dce808b192a9c49a5b60f1943762))

* Removed sys-that-need-work.txt ([`4888462`](https://github.com/eyeonus/Trade-Dangerous/commit/48884621cb6aaeba0890c5023b38c12a85f3c72f))

* LHS 64 Stations ([`0fff557`](https://github.com/eyeonus/Trade-Dangerous/commit/0fff557a0ee28fc3d600aa54220f4b43177cf5fc))

* Pemede stations ([`5946610`](https://github.com/eyeonus/Trade-Dangerous/commit/5946610af03a206423d92f31bcb307c8bed80a11))

* Station update ([`b88a66b`](https://github.com/eyeonus/Trade-Dangerous/commit/b88a66b97a046007f5b922daaef2a8481a4cb8c4))

* Temporarily disabling ShipVendor.csv until we have good data for it ([`37e6c8c`](https://github.com/eyeonus/Trade-Dangerous/commit/37e6c8ccbfbafb3cb3b9dc914c16d1675dfe7ae6))

* 21 new systems from Maddavo&#39;s data ([`7f020c7`](https://github.com/eyeonus/Trade-Dangerous/commit/7f020c7e501af045a88458f6ded6cc219a9ebd38))

* Systems that were out of order ([`e45bc00`](https://github.com/eyeonus/Trade-Dangerous/commit/e45bc00171ebcf3dec8f8ca4daeacddf5c66a2e9))

* Small tool for comparing two System.csv files ([`d888166`](https://github.com/eyeonus/Trade-Dangerous/commit/d888166b34bbd901f46b6501cdc97c6b2a4bf923))

* Tweaks to UI ([`2c8c62f`](https://github.com/eyeonus/Trade-Dangerous/commit/2c8c62f955876bccfef3467efc3fc91f8b8b311c))

* Slight UI refactor ([`e0291dc`](https://github.com/eyeonus/Trade-Dangerous/commit/e0291dcf65316fadebf83231cf581ed97160a181))

* Minor cleanup of gui code ([`88e935b`](https://github.com/eyeonus/Trade-Dangerous/commit/88e935b85112159f5ee932fcfbaafcc56ee84c05))

* Added --ignore-unknown option to buildcache ([`45879bf`](https://github.com/eyeonus/Trade-Dangerous/commit/45879bfc4a00693f464b8c48583ec170bdc5f080))

* Ups, left manual merge line ([`1561117`](https://github.com/eyeonus/Trade-Dangerous/commit/156111748a5c36dda8e5b494b2ecce039ea70b50))

* Merge branch &#39;master&#39; of bitbucket.org:kfsone/tradedangerous into devel

Conflicts:
	data/Added.csv ([`ef49c95`](https://github.com/eyeonus/Trade-Dangerous/commit/ef49c95c958c0976622fafca7d00b46e38f8d70b))

* Wrong term for column ([`c85ed3f`](https://github.com/eyeonus/Trade-Dangerous/commit/c85ed3fc9a1d0fd2f78c2ecefff4789246595695))

* If you miss the level on a price, turn it into ? rather than an error ([`0c88de9`](https://github.com/eyeonus/Trade-Dangerous/commit/0c88de98b4b5442363d03adc8d889be097ead89c))

* ROSS 210 Stations ([`85b2a97`](https://github.com/eyeonus/Trade-Dangerous/commit/85b2a97c211d03a26ef34934ecd5cb144893adff))

* Added Chemaku stations ([`561a27e`](https://github.com/eyeonus/Trade-Dangerous/commit/561a27ea2871952f10815fa13c9cc689ad9eb7ba))

* Added aiabiko stations ([`b8430b8`](https://github.com/eyeonus/Trade-Dangerous/commit/b8430b84b58cd0fbc4cbf5617b212311e589e91a))

* Changed Kamchaultultula to Aiabiko (newbie start area) ([`6c34c27`](https://github.com/eyeonus/Trade-Dangerous/commit/6c34c276e6ab52b035e106767066da96ed50e452))

* Added --front and --height to update GUI ([`e279417`](https://github.com/eyeonus/Trade-Dangerous/commit/e279417db3df4788751d478835e26e16d1a04bdc))

* Missing import command ([`c589c37`](https://github.com/eyeonus/Trade-Dangerous/commit/c589c377610ece016c9b72fc59eb264ab72eb119))

* Mini-api for querying EDStar ([`7853779`](https://github.com/eyeonus/Trade-Dangerous/commit/7853779bcd02215e79e2e4e94306cbe5e49d018f))

* LFT 926 and Nuenets data ([`9582f38`](https://github.com/eyeonus/Trade-Dangerous/commit/9582f38b6645b2fad64aa58ff4a407259d7a0be7))

* Added &#39;import&#39; command for importing one or more stations from a text file ([`1174024`](https://github.com/eyeonus/Trade-Dangerous/commit/1174024352c757b30f25085a9799943f40ba092a))

* Gamma1 Pilot&#39;s Federation Site/Jameson Memorial ([`a7adac2`](https://github.com/eyeonus/Trade-Dangerous/commit/a7adac263556cfe34e4c6940f7640b6fc1c05b31))

* Switched to INNER/OUTER JOIN syntax for SQL depending on the &#34;NOT NULL&#34; status
of the FK column. ([`6b8b4ad`](https://github.com/eyeonus/Trade-Dangerous/commit/6b8b4ada2c017b1063b9697c163f134ed2f3df1f))

* Merge branch &#39;master&#39; into devel

Conflicts:
	data/Station.csv ([`33de4a9`](https://github.com/eyeonus/Trade-Dangerous/commit/33de4a9c841adef4f7115153831f97611aa5d17f))

* Let the user know their prices.last file is there for recovery ([`62d87b2`](https://github.com/eyeonus/Trade-Dangerous/commit/62d87b2561200d447300a6c6b79cafe7deac3cc4))

* v6.0.4 README ([`37d3c78`](https://github.com/eyeonus/Trade-Dangerous/commit/37d3c78c75067a74c129b18a91107226fd471136))

* Added &#39;sell&#39; sub-command ([`42ed41f`](https://github.com/eyeonus/Trade-Dangerous/commit/42ed41f17762e5fbe85f4e1be10f1db4c3e7a197))

* Some 3.9.1 stations ([`2630ad4`](https://github.com/eyeonus/Trade-Dangerous/commit/2630ad43eab20327751766120342e148570471a5))

* Nav command was putting &#39;arrive&#39; in the wrong place ([`dc95072`](https://github.com/eyeonus/Trade-Dangerous/commit/dc95072c694830cdc4f09ad7177aa347dca11c72))

* Buy Command was showing the same item multiple times for systems with multiple stations ([`6a119d2`](https://github.com/eyeonus/Trade-Dangerous/commit/6a119d2f03d8bcaf2778ee37ebe55a243c867724))

* Fix for price data reset code in build cache ([`a73b16d`](https://github.com/eyeonus/Trade-Dangerous/commit/a73b16df277ab709687fd3f713ad8ac3a63aa49f))

* When we do rebuild prices, flush the data first ([`1e804bc`](https://github.com/eyeonus/Trade-Dangerous/commit/1e804bc8058898ab4f9a2951a4c387e900f63672))

* Added &#34;--all&#34; (-A) option to update GUI ([`c890253`](https://github.com/eyeonus/Trade-Dangerous/commit/c8902537a1ce85f8f2a60b746926f5132cc0352c))

* More tightly integrated update_gui

Improved startup times by taking tdb and cmdenv parameters and avoiding having to double-open the DB and re-read various tables. ([`8828c89`](https://github.com/eyeonus/Trade-Dangerous/commit/8828c8942cd0fba2f3741e6122046d58c653dde3))

* Only repopulate Price tables when .prices changes

This saves us doing a full cache rebuild every time which improves performance ([`bbfb091`](https://github.com/eyeonus/Trade-Dangerous/commit/bbfb09110189d2517eb57ad5a10f94312d0976f2))

* Issue #57 After an update, we rebuilt the cache again ([`6ff847b`](https://github.com/eyeonus/Trade-Dangerous/commit/6ff847b56ef26bdad4f28b99093f74bb1d60a0d7))

* CHANGES ([`4af60bb`](https://github.com/eyeonus/Trade-Dangerous/commit/4af60bbe52efe86f3bd12a2b734fe4d270c0da52))

* Fixed how we &#39;touch()&#39; the dbFile in an update ([`cad7c85`](https://github.com/eyeonus/Trade-Dangerous/commit/cad7c858ee77ee3846fca15f6810573a75c26e6c))

* Added up/down keys to update gui ([`bd67902`](https://github.com/eyeonus/Trade-Dangerous/commit/bd67902c8fdcdd1d5320c8df5f0c8d3bcf1be3e2))

* Support correctStation with a system name for more precise corrections ([`1459f1c`](https://github.com/eyeonus/Trade-Dangerous/commit/1459f1c83c407c9c1f30030ad8cf46821b6c8798))

* Tweaks to update GUI ([`cf1bd5f`](https://github.com/eyeonus/Trade-Dangerous/commit/cf1bd5f2b36bb6da2c7bd45c0fab9caedb81140c))

* Added Chemical Waste ([`63ef563`](https://github.com/eyeonus/Trade-Dangerous/commit/63ef563b5540b822e411a7dad727bdd3ebca6324))

* 3.9.1 calls &#39;reactivearmor&#39; &#39;Reactive Armour&#39; ([`2a2d216`](https://github.com/eyeonus/Trade-Dangerous/commit/2a2d2167a7ce0ef0ac469cd4208774aaff0d6486))

* Merge branch &#39;master&#39; of bitbucket.org:kfsone/tradedangerous ([`8437bfc`](https://github.com/eyeonus/Trade-Dangerous/commit/8437bfc4f0dc8c58928a69b42926af8e75f41316))

* Removed print spam when correcting item names ([`dc5b1a0`](https://github.com/eyeonus/Trade-Dangerous/commit/dc5b1a0ee21b4692b31dea519edf3fe7c63c0430))

* Merge branch &#39;master&#39; of bitbucket.org:kfsone/tradedangerous ([`132179a`](https://github.com/eyeonus/Trade-Dangerous/commit/132179aee7102bfc40eee686782c1f91c7286a99))

* Fix for SQL error populating initial prices for a station ([`e645f1b`](https://github.com/eyeonus/Trade-Dangerous/commit/e645f1bdc8db9e87bb791eaa7fc701f7aaa3906e))

* Provide a way to generate corrections for -STATION stations while parsing .prices ([`802e233`](https://github.com/eyeonus/Trade-Dangerous/commit/802e2335b8fd344d51b3624d5bc80e01ec7cb8f4))

* More dubug output ([`1479c75`](https://github.com/eyeonus/Trade-Dangerous/commit/1479c750f7f43cf8c4177f3260d464431d488d20))

* Added missing Added entries. The current export implementation does not
support outer joins. ([`1b51657`](https://github.com/eyeonus/Trade-Dangerous/commit/1b51657f9bddc415c2fa5baa82deac28788ee423))

* some words of advice ([`faf906a`](https://github.com/eyeonus/Trade-Dangerous/commit/faf906a53eb3facb4717c8a44a9423163ef8b125))

* separated script no longer needed ([`f23afd7`](https://github.com/eyeonus/Trade-Dangerous/commit/f23afd7aa279f44bbac7e227d789d6bd370a1d04))

* CSV Exporter for TD database ([`f8a11cd`](https://github.com/eyeonus/Trade-Dangerous/commit/f8a11cd0b38c8854c61b611a6270d26d425b8793))

* switch on FK because we need it ([`842c3ef`](https://github.com/eyeonus/Trade-Dangerous/commit/842c3ef43bdd70f2a252bf9e673106ac4a533621))

* reverted temporary dist=0 fix ([`313fc62`](https://github.com/eyeonus/Trade-Dangerous/commit/313fc62944dc52ad47057445b9d57bd243f418e5))

* Merge branch &#39;master&#39; into devel ([`f9eb3b9`](https://github.com/eyeonus/Trade-Dangerous/commit/f9eb3b9aec54938a006b46e97c4db3366b6d0b72))

* adapted to new db design ([`c51ab14`](https://github.com/eyeonus/Trade-Dangerous/commit/c51ab14b1cab231d09edc382ca387e80ae41aa77))

* v6.0.3 ([`04ff4fa`](https://github.com/eyeonus/Trade-Dangerous/commit/04ff4fade6d87e1adbebb79d8a95aa56f1321239))

* Fixed &#34;local&#34; command not showing stations with -v ([`6d77907`](https://github.com/eyeonus/Trade-Dangerous/commit/6d779076eed21902b41bad16403e7d66e9205217))

* Fix for error building cache with two stations in the same system ([`3d739de`](https://github.com/eyeonus/Trade-Dangerous/commit/3d739debad1730161db3808868ea7aa34532dfa9))

* Renamed buildcache.py -&gt; cache.py ([`17dc9b5`](https://github.com/eyeonus/Trade-Dangerous/commit/17dc9b577f89f3962ba71b5221a12cbf5d8a53b7))

* Made scrollwheel work in the update gui ([`9c7d867`](https://github.com/eyeonus/Trade-Dangerous/commit/9c7d867694de47d1b83fbc32dbd97ea095b77b69))

* Merge branch &#39;master&#39; of bitbucket.org:kfsone/tradedangerous ([`5faa448`](https://github.com/eyeonus/Trade-Dangerous/commit/5faa44852e60f89a6dfda77b6383ee4883f22b39))

* First pass of the update gui.

1. it forces demand columns to &#34;?&#34; when they aren&#39;t &#34;-&#34;,
2. Use tab/shift-tab to go horizontally between columns,
3. Use the enter key to move down to the first col of the next line, ([`56f37a1`](https://github.com/eyeonus/Trade-Dangerous/commit/56f37a1a90251df042b9aeab225fa31aee03a731))

* Better alignment with update requirements ([`c23efd3`](https://github.com/eyeonus/Trade-Dangerous/commit/c23efd3239647b50e7627dfe9938d1363a51553f))

* First, crappy, version of the update gui ([`96a8447`](https://github.com/eyeonus/Trade-Dangerous/commit/96a8447543d312ca7f063a801b609784eb30e4c7))

* Readme update ([`903a2b7`](https://github.com/eyeonus/Trade-Dangerous/commit/903a2b791f4b94411562f02b14c3f74c97e2bbe7))

* Don&#39;t try to sqrt(0) in buildCache ([`b4659be`](https://github.com/eyeonus/Trade-Dangerous/commit/b4659beb5e5a69547e71cf8661d68d43ed4aa033))

* Only link stations in different systems ([`ac0cd05`](https://github.com/eyeonus/Trade-Dangerous/commit/ac0cd0538b77525e7450c402a90c26d8e8057c47))

* made unique check case insensitive ([`8fdc4c9`](https://github.com/eyeonus/Trade-Dangerous/commit/8fdc4c9ceba00e22a56be73fd936e2bbe8080f80))

* removed trailing spaces ([`6029914`](https://github.com/eyeonus/Trade-Dangerous/commit/6029914056ae18f9379fbe8da85ccd598f38d83b))

* Stationname must be UNIQUE ([`415d1d3`](https://github.com/eyeonus/Trade-Dangerous/commit/415d1d3e0dbdc778f71bf97d2603a1622e5005bc))

* Merge branch &#39;master&#39; into devel

Conflicts:
	.gitignore ([`d40c83d`](https://github.com/eyeonus/Trade-Dangerous/commit/d40c83db239c87a568f7e626061cf9a7048ae661))

* Seperated change log into CHANGES.txt ([`188dafa`](https://github.com/eyeonus/Trade-Dangerous/commit/188dafa2ec35a0937dacea21acd302a877b5e3a0))

* v6.0.2 ([`5261e3b`](https://github.com/eyeonus/Trade-Dangerous/commit/5261e3be9ea981be5ac1be0eb173a0d3a58dc48a))

* Added --limit to buy command ([`3ec13d1`](https://github.com/eyeonus/Trade-Dangerous/commit/3ec13d11209e76ec59f01eb8faea243bdffb7d87))

* Styx/Chu Hub is Styx/Chu Hub not Chi Hub ([`16ec9d0`](https://github.com/eyeonus/Trade-Dangerous/commit/16ec9d03581c95b8907e702de0ef34d957c3d06a))

* Additional stations via Maddavo ([`bf5a9c0`](https://github.com/eyeonus/Trade-Dangerous/commit/bf5a9c06dc5f7c012cfa0587a6ff3fc75a6c76b5))

* Merge branch &#39;master&#39; into args-refactor

Conflicts:
	README.txt
	data/Station.csv ([`fd90fac`](https://github.com/eyeonus/Trade-Dangerous/commit/fd90fac3db09268b9806568c38af4a2881f72a3e))

* Don&#39;t consider non-trading destinations from getDestinations ([`400559f`](https://github.com/eyeonus/Trade-Dangerous/commit/400559f8be2f1952ea375cf5bd5742a71c2f4645))

* Tweaks to reduce allocation overhead in getDestinations

Small perf gain in a very tight loop = big win. ([`9e1e010`](https://github.com/eyeonus/Trade-Dangerous/commit/9e1e010ba0ba9efbe0da9c2443e82b96574d61a0))

* Made Destination and DestinationNode top level classes ([`dd94ecf`](https://github.com/eyeonus/Trade-Dangerous/commit/dd94ecfafdeeda4bf0834eb915b52e20c46c234a))

* Remember DB connection in load so we don&#39;t keep opening the db ([`c3f24ff`](https://github.com/eyeonus/Trade-Dangerous/commit/c3f24ff77fdff8cd264f90e981baed1b993f64ce))

* Minor tidy of getDestinations ([`fcfbf84`](https://github.com/eyeonus/Trade-Dangerous/commit/fcfbf84aa8cff92cc83309f3c6b77f8d90e0534f))

* &#39;unspecifiedHops&#39; wasn&#39;t very clear.

Changed it to &#39;adhocHops&#39; (the hops that don&#39;t have a predetermined destination), although
what we really care about are the points rathe than the edges.

Also improved the feedback given when you have too many --vias for the --hops you gave. ([`cdd2bcc`](https://github.com/eyeonus/Trade-Dangerous/commit/cdd2bcc5f75dab40dccba4556b172632cf9b10ba))

* Unbreak via stations ([`9c8a966`](https://github.com/eyeonus/Trade-Dangerous/commit/9c8a96631df0360080505bf7f9cf69c6561bdd43))

* README ([`7ed5d05`](https://github.com/eyeonus/Trade-Dangerous/commit/7ed5d056effc3cb0c3c2b40e3a0b22e2c0267b71))

* Boosted performance of run command for smaller data sets

We were spending upto 50s loading data from the database; the run command now works on a far lazier, on-demand basis. ([`9373c00`](https://github.com/eyeonus/Trade-Dangerous/commit/9373c003523225954df84253469334995f41b133))

* getBestHops now lazy loads trades

In the case where you are calling getBestHops without having fully loaded the trades set, if it encounters stations for which it does not yet have trades out of, it will load that data. Once it has loaded data for a station, it won&#39;t try to reload it. ([`9d93ee4`](https://github.com/eyeonus/Trade-Dangerous/commit/9d93ee4ace0b89468e95f6f512b484d61a26ceb0))

* TradeDB.loadStationTrades([stationIDs])

Loads profitable trades out of the specified station list. ([`f499e5c`](https://github.com/eyeonus/Trade-Dangerous/commit/f499e5cac30b2a7a7fcbc28a5bbc44daf55cabc6))

* Systems without links demoted to a level 2 debug message. ([`239e38c`](https://github.com/eyeonus/Trade-Dangerous/commit/239e38c0ed8a855e5967b536c93c7fbaa8127f5d))

* Load data from StationLink table, rather than building on the fly

With the indexes in-place, this is 100s of ms cheaper. ([`7196e64`](https://github.com/eyeonus/Trade-Dangerous/commit/7196e649e5c58c0c74d9a5b078c26757e6cd55d7))

* Use vProfits view to retrieve profitable items ([`6aebcb9`](https://github.com/eyeonus/Trade-Dangerous/commit/6aebcb9917565b356573612c73166b49acdde291))

* Track whether trades have been loaded per station

This may break some functionality that assumes tradingWith will always be a valid dictionary ([`0392552`](https://github.com/eyeonus/Trade-Dangerous/commit/039255210bc359fa754bf879e336f00ff0c46847))

* Index to optimize retrieving distinct system links ([`456a866`](https://github.com/eyeonus/Trade-Dangerous/commit/456a86649e73b523239f15476c391da57b50ca51))

* Moved big query from loadTrades to a view ([`a61eb84`](https://github.com/eyeonus/Trade-Dangerous/commit/a61eb84744bcd69c8107c5f46706ad2266a098ab))

* Fix non-profitable trades being selected ([`172e323`](https://github.com/eyeonus/Trade-Dangerous/commit/172e323b813cd4ccec6cd4bb41c00ab75bd36975))

* Make sure db connections have foreign key support enabled ([`398f502`](https://github.com/eyeonus/Trade-Dangerous/commit/398f502b24fb36e9f2fdb1b84017fbba1459ea5f))

* Prices object needs str() wrapper to be printable ([`65d3663`](https://github.com/eyeonus/Trade-Dangerous/commit/65d3663ddc87875f52197feeb0bdbc04e05e2cfe))

* Refactoring prices.py to use StationSelling etc ([`e493519`](https://github.com/eyeonus/Trade-Dangerous/commit/e49351943e5a71d6f899e76d8e59a8038bbe7c31))

* Make buy command use StationLink and StationSelling ([`4b05d02`](https://github.com/eyeonus/Trade-Dangerous/commit/4b05d02aa01ea2ee13c9fdc041c1e2cae006cf4a))

* Improved indexes on StationLink ([`06d8623`](https://github.com/eyeonus/Trade-Dangerous/commit/06d86234cd60271def8677f98bc1573dff0326e4))

* StationLink includes links in-system ([`6adcd71`](https://github.com/eyeonus/Trade-Dangerous/commit/6adcd7176cadb97abe2b9257778a73414aea168a))

* Multiple-destinations for run

&#39;--end&#39; allows you to specify a list of alternative
destinations; e.g if you want a route that ends at
EITHER Beagle2 or Freeport:
run --end beagle2 --end freeport ([`be0b964`](https://github.com/eyeonus/Trade-Dangerous/commit/be0b9641a60110b95cd1017786cd65e148457505))

* Fixes for StationLink ([`96040f7`](https://github.com/eyeonus/Trade-Dangerous/commit/96040f75313bd55fafd0f2e13fd391611c681e02))

* Merge branch &#39;master&#39; into devel ([`ef764cb`](https://github.com/eyeonus/Trade-Dangerous/commit/ef764cbb0141c6bc90d22997c085cd7801ef944a))

* Revert &#34;Removed backwards compatibility support for old .prices format, they were slowing down processing&#34;

This reverts commit 657872d93ccbefd4bc032fbc4c259e321dd2ddeb. ([`ad41e04`](https://github.com/eyeonus/Trade-Dangerous/commit/ad41e049dd57f7510d6ba6b0bcf3d71c7744dd44))

* Build db on disk rather than in memory

We were building the db as an in-memory db and then exporting it to an on-disk db; this
code now builds it on disk and simply swaps the files around once it&#39;s done. ([`8fb2c0b`](https://github.com/eyeonus/Trade-Dangerous/commit/8fb2c0b4c8746b8a36896fee701cf33ff4bc92f1))

* Removed backwards compatibility support for old .prices format, they were slowing down processing ([`657872d`](https://github.com/eyeonus/Trade-Dangerous/commit/657872d93ccbefd4bc032fbc4c259e321dd2ddeb))

* Instead of system links, station links are much more useful ([`b3ff475`](https://github.com/eyeonus/Trade-Dangerous/commit/b3ff475251c6ba5b66ce2b68fe56748adab1f40a))

* Reorganized SQL so that sell and buy prices are better distinguished ([`a9a933d`](https://github.com/eyeonus/Trade-Dangerous/commit/a9a933d0ec82334f9ab9f620998cfd8777850ba7))

* Some missing DEBUGs ([`04bfb6a`](https://github.com/eyeonus/Trade-Dangerous/commit/04bfb6abb2cce59b8f1a5d0cebaa28dc816d76e6))

* README.txt edited online with Bitbucket ([`f64a9aa`](https://github.com/eyeonus/Trade-Dangerous/commit/f64a9aa58da51642fe5b1b9fedbe91f6e174f00e))

* Merged in Smacker65/tradedangerous/Beta3NewStations (pull request #25)

Merge in new stations from Slopey ([`fa4ab8b`](https://github.com/eyeonus/Trade-Dangerous/commit/fa4ab8b70095961d8f9ef879c8d87ac7815cdd8c))

* Self-assembling replacement for DEBUG ([`9d980f1`](https://github.com/eyeonus/Trade-Dangerous/commit/9d980f1e763968e595bfc36a759ce8ab8ad0ba7a))

* Minor reorg of some tables to improve startup perf ([`8b21433`](https://github.com/eyeonus/Trade-Dangerous/commit/8b21433fec8c043dcac731f8434165706f4bb847))

* Have buildCache generate a SystemLinks table to reduce runtime calcs ([`58a27e8`](https://github.com/eyeonus/Trade-Dangerous/commit/58a27e84c12be8e02cf0f16ab5b5b8d9b98242ad))

* Return None by default for unknown TradeEnv attributes ([`8f088e1`](https://github.com/eyeonus/Trade-Dangerous/commit/8f088e1c3d6ad4b22247c81c3da174b1c575f0e8))

* Updated readme ([`5e7e52e`](https://github.com/eyeonus/Trade-Dangerous/commit/5e7e52e3f50cac75046a01910ee259b5bc6a5e4d))

* Version check at trade.py startup ([`b373f30`](https://github.com/eyeonus/Trade-Dangerous/commit/b373f3011794c4b55abfbf4a1ed9b81841b45941))

* Merge branch &#39;master&#39; into args-refactor

Conflicts:
	data/corrections.py ([`2fc5f8c`](https://github.com/eyeonus/Trade-Dangerous/commit/2fc5f8c925b25f079d2077d7dfc694ec06bb025e))

* Added unq: prefixes ([`dd3ffa5`](https://github.com/eyeonus/Trade-Dangerous/commit/dd3ffa51757bb581c62f3015b0df196b526ffba5))

* Unique index specification in .csv files

If you prefix as .csv column with &#34;unq:&#34; then the parser will apply a uniqueness constraint. This allows us to give users better feedback when something is doubled up rather than just presenting them with an internal error talking about referential integrity :) ([`4fc7863`](https://github.com/eyeonus/Trade-Dangerous/commit/4fc7863638aac5b5f9c48e3c49267d384e2810d7))

* Refactored buildCache for performance:

- placed new-format conditions ahead of old-format (makes new files faster),
- UnitsAndLevel was wasting a lot of time in new, replaced with a function,
- Broke some of the inline code out to functions for pycallgraph tracing ([`ed9d2bf`](https://github.com/eyeonus/Trade-Dangerous/commit/ed9d2bf984bbed2a48f5af00aec9713275bab01c))

* Move properties directly into tradeenv to reduce pass-through calls ([`520c621`](https://github.com/eyeonus/Trade-Dangerous/commit/520c621cdc6677f37b09ec5dae83f91d9fd6be2d))

* Fixes for run command. ([`17e1de9`](https://github.com/eyeonus/Trade-Dangerous/commit/17e1de93137b70f5850eb73daa0368369b9f593d))

* Code sanitation - python 2.7 proofing ([`32330ba`](https://github.com/eyeonus/Trade-Dangerous/commit/32330baea10748b08ae4b56efb09e14135e3d63a))

* More defaults for TradeEnv ([`7e5708b`](https://github.com/eyeonus/Trade-Dangerous/commit/7e5708b0a5cbe780e9ef2bdc4178f0759d5b4b9e))

* Removed Trade.describe() ([`40ec808`](https://github.com/eyeonus/Trade-Dangerous/commit/40ec808d02b5514dab6f4466be20874824e91e7e))

* Huxley Relay ([`e463f6f`](https://github.com/eyeonus/Trade-Dangerous/commit/e463f6f25ff1a0f53b16b907d086d42274cb4b4a))

* Removed use of localedNo and switched to .format formatting ([`aff887d`](https://github.com/eyeonus/Trade-Dangerous/commit/aff887dbc811aa63bb70f9f85eb786806edfd0a9))

* DEBUG note when loading links/trades ([`bc4d122`](https://github.com/eyeonus/Trade-Dangerous/commit/bc4d122e63af7f9c9436732f32e82e6ce29d6360))

* Don&#39;t repr the entire item when showing a trade

caused it to show the category etc which made Trade() reprs difficult to read ([`7edd516`](https://github.com/eyeonus/Trade-Dangerous/commit/7edd516ba2a8a78747f800e7c2b5a849ae0be46f))

* Indicate when importing data at import rather than outside ([`752f789`](https://github.com/eyeonus/Trade-Dangerous/commit/752f7896a8a5ee21835ea844f4ce1b8a1ee542c6))

* Prototype tools for generating persistent stellar IDs ([`2db26c6`](https://github.com/eyeonus/Trade-Dangerous/commit/2db26c6325d3e8f42536b256f55c5667a230bef0))

* Added new stations to corrections ([`bfb7aec`](https://github.com/eyeonus/Trade-Dangerous/commit/bfb7aec51c65cb2cffb288ae910f64fc971b2f7b))

* Merge in new stations from Slopey ([`bbc0bd4`](https://github.com/eyeonus/Trade-Dangerous/commit/bbc0bd49eb4a6823b2b1bc21981b716c4072f848))

* Added ROSS 130/Huxley Relay ([`dd59c96`](https://github.com/eyeonus/Trade-Dangerous/commit/dd59c966b60eeda66b468e70b84d3cc86f2e8985))

* Fixed syntax error in update_cmd.py ([`bb8bf1f`](https://github.com/eyeonus/Trade-Dangerous/commit/bb8bf1fa151943113a623120b9eccf9004486810))

* Don&#39;t barf so much debug text in run cmd ([`96b92be`](https://github.com/eyeonus/Trade-Dangerous/commit/96b92bebf3276fe25be86754865545c5edaa3ba0))

* Minor optimization tweaks for tradedb in regards to loading Trade objects ([`7d6d080`](https://github.com/eyeonus/Trade-Dangerous/commit/7d6d08085a84d108e501a4104540914df932678d))

* Brute force conversion of run command ([`12c1654`](https://github.com/eyeonus/Trade-Dangerous/commit/12c1654d75254bb2dc3cb62d4fc7e3cc97486e57))

* Assorted problems in tradecalc and tradedb ([`4f94ef6`](https://github.com/eyeonus/Trade-Dangerous/commit/4f94ef6a23c78a981d5eb74d889691c17980a7bc))

* Wasn&#39;t populating avoidPlaces in commandenv ([`dc1560b`](https://github.com/eyeonus/Trade-Dangerous/commit/dc1560b7bf39e9883c1f8e6a1a7d1a2fb6daa5b8))

* Typo ([`b0e8b0e`](https://github.com/eyeonus/Trade-Dangerous/commit/b0e8b0edca2e2cfdab05da59fabd3b0e749c908f))

* Merge branch &#39;master&#39; into args-refactor

* master:
  Station name changes added to corrections
  Only print deprecation warnings when debug is specified
  Catch name changes in buildcache and report deprecated names
  README.txt
  v5.0.1: Smacker&#39;s latest data import
  Merge RedWizzard&#39;s changes
  Removed bad system
  Not enough Wangs
  Latest from the forums
  Remove a few rogue systems
  Beta3 Systems with markets + preliminary station list

Conflicts:
	README.txt
	buildcache.py ([`0a886f8`](https://github.com/eyeonus/Trade-Dangerous/commit/0a886f85cf5a58d9c112f749c83439273e857d20))

* Station name changes added to corrections ([`e0f6c2d`](https://github.com/eyeonus/Trade-Dangerous/commit/e0f6c2d5be20fe9a73be16845ce02fd662b9aef8))

* Only print deprecation warnings when debug is specified ([`4921cfb`](https://github.com/eyeonus/Trade-Dangerous/commit/4921cfb20549116e7a52dc9760b79b5153e665fb))

* Catch name changes in buildcache and report deprecated names ([`575d386`](https://github.com/eyeonus/Trade-Dangerous/commit/575d386351cbe1789f99bf013392bb43470fa4f8))

* Merge branch &#39;master&#39; into devel ([`92740a5`](https://github.com/eyeonus/Trade-Dangerous/commit/92740a5c8fcfa773654e437b74ae8a7c37ec1fcd))

* README.txt ([`137d403`](https://github.com/eyeonus/Trade-Dangerous/commit/137d403371f8a929089c866155c74bf66cfb8646))

* v5.0.1: Smacker&#39;s latest data import ([`6c43e11`](https://github.com/eyeonus/Trade-Dangerous/commit/6c43e11db5afebf98635a1563c6d563b6c65ad24))

* Merged in Smacker65/tradedangerous/Beta3Systems (pull request #24)

Beta3 Systems with markets + preliminary station list ([`aed777b`](https://github.com/eyeonus/Trade-Dangerous/commit/aed777b26076262e3e8fb9ec490c0357cce3e4ea))

* Merge RedWizzard&#39;s changes ([`da4306e`](https://github.com/eyeonus/Trade-Dangerous/commit/da4306e9681a7efff898362d9b119dafed6b202e))

* Fix for renaming to prices.last

Have to delete the previous .last file before we can rename prices.tmp again. ([`4af930c`](https://github.com/eyeonus/Trade-Dangerous/commit/4af930c09a51d938dcd484ef7c963cfbff9d3ceb))

* Don&#39;t leave stray .last file around if the user made no changes ([`53b4fdd`](https://github.com/eyeonus/Trade-Dangerous/commit/53b4fddf22ab524a0cb3c1bb978f77094965533f))

* Added update to the command list ([`42c65f9`](https://github.com/eyeonus/Trade-Dangerous/commit/42c65f9f6a92350b7fc2a06d6a4966ddd6b239a8))

* README prep for 6.0 ([`e105f6d`](https://github.com/eyeonus/Trade-Dangerous/commit/e105f6d1aa941562c3ac412a5f59fadb77758fa6))

* Converted &#39;update&#39; ([`a9eef4f`](https://github.com/eyeonus/Trade-Dangerous/commit/a9eef4fe3ac59d14c7f2d96b8fecc23ba1d3ad2f))

* Merge branch &#39;master&#39; into args-refactor

* master:
  Better feedback when processImportFile fails

Conflicts:
	buildcache.py ([`60ea9d6`](https://github.com/eyeonus/Trade-Dangerous/commit/60ea9d681974be84aabe5150c891997b698195c4))

* Better feedback when processImportFile fails ([`8d2aa0c`](https://github.com/eyeonus/Trade-Dangerous/commit/8d2aa0c7b3eed3c807fb41a33a070ff074bd39a5))

* Converted nav cmd ([`a0c999c`](https://github.com/eyeonus/Trade-Dangerous/commit/a0c999cfb2daec19c7f8288681a5b56e312cb6db))

* Ignore .pyc files ([`effb6d9`](https://github.com/eyeonus/Trade-Dangerous/commit/effb6d95f0b6ec0ad5aec3ba37decaf0abe0052e))

* Convention: Hide headings with first -q ([`9df6828`](https://github.com/eyeonus/Trade-Dangerous/commit/9df6828a815f72b76d0b186ee9b2abefc5c99b45))

* Python3 shebang for trade.py ([`92daec8`](https://github.com/eyeonus/Trade-Dangerous/commit/92daec81a09e8d67b6740f2e597288299e240057))

* commands.ResultRow now takes default args ([`caafd57`](https://github.com/eyeonus/Trade-Dangerous/commit/caafd5763b34e47dc217268abd1bc9968953900d))

* Partial progress converting nav command (and using genSystemsInRange) ([`b0e8adc`](https://github.com/eyeonus/Trade-Dangerous/commit/b0e8adcb9da6285d93f6dc09f86962299de89e18))

* Removed buy.py from subcommands ([`2a9474c`](https://github.com/eyeonus/Trade-Dangerous/commit/2a9474ca2ad424e710ab7041d689af015a19817f))

* Added RowFormat.addColumn convenience function ([`8c79e15`](https://github.com/eyeonus/Trade-Dangerous/commit/8c79e151171514f4386020180d0cb2e1451e7f6a))

* Converted &#39;buy&#39; command ([`92426b9`](https://github.com/eyeonus/Trade-Dangerous/commit/92426b9c3d5b86a4630fe5bd00dc2414953b909e))

* Partial conversion of buy command ([`f59f449`](https://github.com/eyeonus/Trade-Dangerous/commit/f59f449fed58f3351ffcec65b38063ecf97369f5))

* Missing import ([`f3741ab`](https://github.com/eyeonus/Trade-Dangerous/commit/f3741abd4d22721b15746e761aa3da497db2d045))

* Added includeSelf flag to genSystemsInRange ([`fff2ccd`](https://github.com/eyeonus/Trade-Dangerous/commit/fff2ccd440daa285b4b2922da4c4434bcc0b8c3a))

* build cache fixes from merge ([`cce3309`](https://github.com/eyeonus/Trade-Dangerous/commit/cce3309a656eff7d90f69a98b2bf88be2bce95a2))

* Merge branch &#39;master&#39; into args-refactor

* master:
  Added mechanism for marking corrections as deletions ([`5a35fa3`](https://github.com/eyeonus/Trade-Dangerous/commit/5a35fa39853be85f5188a05fcd832aee6106a9d0))

* Made build cache a trade.py command proper ([`f032cd7`](https://github.com/eyeonus/Trade-Dangerous/commit/f032cd77e7e046aad69ee833b85a323d36474a39))

* Unqualified exceptions in commands/__init__.py ([`7dfba6b`](https://github.com/eyeonus/Trade-Dangerous/commit/7dfba6b43d3d185472b03a4bed53c9e2615db06a))

* Curbed some namespace pollution ([`604c647`](https://github.com/eyeonus/Trade-Dangerous/commit/604c647dedb82c81c17f4fb2e6a21b953d4edcd6))

* CommandLineEror fix ([`befc486`](https://github.com/eyeonus/Trade-Dangerous/commit/befc48620d291738a34d518208c946678b5157cd))

* LookupError handling in checkFromToNear ([`50bb820`](https://github.com/eyeonus/Trade-Dangerous/commit/50bb8208446f46b47265884521b7f05a8ab0d2e4))

* Handling an exception in trade.py should exit with an error code ([`5372d6b`](https://github.com/eyeonus/Trade-Dangerous/commit/5372d6bd1b2be8e72270169dfaed245acdb4b3a8))

* Don&#39;t render if Command.run returns None

This allows commands to say &#34;all done&#34; and exit silently without trying to render. ([`8363102`](https://github.com/eyeonus/Trade-Dangerous/commit/83631023a5a4ba65916acf0a29b3763ee216259a))

* Merge remote-tracking branch &#39;TheOneTrue/master&#39; into Beta3Systems

Conflicts:
	data/Station.csv ([`d89a677`](https://github.com/eyeonus/Trade-Dangerous/commit/d89a677db1fb40d58e90ab36f3fde811869946d3))

* Added mechanism for marking corrections as deletions ([`8f1e7a7`](https://github.com/eyeonus/Trade-Dangerous/commit/8f1e7a7cbf2d5fb382146baa515b153c1f330c3f))

* TradeDB.genSystemsInRange

As the database grows, the cost of populating System.links for every
star is going to become more and more significant in memory and cpu.

This functionality provides an on-demand spatial lookup with caching;
most of the time we&#39;re probably going to be interested in stars within,
say 60ly of Aulin.

Usage:

```
    import tradedb, math
    tdb = tradedb.TradeDB(buildLinks=False, includeTrades=False)
    aulin = tdb.lookupSystem(&#34;Aulin&#34;)
    for dst, distSq in tdb.genSystemsInRange(aulin, ly=8.0):
        print(&#34;{:&lt;30} {:&gt;6.2f}&#34;.format(dst.name(), math.sqrt(distSq)))
```

TODO: Remove System.links and use this instead. ([`d55a9fe`](https://github.com/eyeonus/Trade-Dangerous/commit/d55a9fec354ce4633c1ce8443202eee7f5944994))

* Fixes for minor regressions ([`30f36a5`](https://github.com/eyeonus/Trade-Dangerous/commit/30f36a55b96f40937f91e127b53ba1ec5d5c3e7f))

* TEMP: genSystemsInRange ([`885f6c4`](https://github.com/eyeonus/Trade-Dangerous/commit/885f6c4b5f9d3c911919378a5a7e6e4bf363cf00))

* Removed System.addStation - do it yourself. ([`bc23089`](https://github.com/eyeonus/Trade-Dangerous/commit/bc23089eaab768510d97855362b5d734af511eb5))

* Normalized use of namedtuple ([`4c05112`](https://github.com/eyeonus/Trade-Dangerous/commit/4c051128c4777ed51354e4468ec3fe47faf6ffcd))

* Ensure there&#39;s a &#34;debug&#34; property on default TradeEnvs ([`c1c5a56`](https://github.com/eyeonus/Trade-Dangerous/commit/c1c5a56134218e591b316e1a7616fd083154f7e1))

* Improved local_cmd ([`81ffe19`](https://github.com/eyeonus/Trade-Dangerous/commit/81ffe199090f87ecdcafab9e214b0ea08c8ac810))

* Provide a TradeEnv base for CommandEnv

This facilities the old &#34;t = TradeDB()&#34; behavior, e.g.

```

Meanwhile it also slightly simplified CommandEnv
   from tradedb import *
   tdb = TradeDB()

   # or specify arguments
   from tradeenv import *
   tenv = TradeEnv(debug=1, dbFilename=&#39;test.db&#39;)
   tdb = TradeDB(tenv)
``` ([`0fcd6c4`](https://github.com/eyeonus/Trade-Dangerous/commit/0fcd6c4d58e5650621c0e7e82fbad2841ee4a358))

* Added &#39;heading&#39; member to RowFmt ([`e74fa9d`](https://github.com/eyeonus/Trade-Dangerous/commit/e74fa9d1bbcbdcb564ead1ce5646d5f073c8a6ce))

* Merge branch &#39;master&#39; into args-refactor

Conflicts:
	buildcache.py
	data/corrections.py ([`0c9545a`](https://github.com/eyeonus/Trade-Dangerous/commit/0c9545a95ff318d6e1d98a8cb43a673fd0712323))

* Defer sub-command imports until usage

This way, if you&#39;re not using those modules, you won&#39;t waste time loading them. ([`bb6b8e5`](https://github.com/eyeonus/Trade-Dangerous/commit/bb6b8e5d9f0a6fec35ce99da5aa3b7f5685e6cc7))

* Remove Edit action helpers

I&#39;m not going to use them in v2 of update ([`2d338d5`](https://github.com/eyeonus/Trade-Dangerous/commit/2d338d5cc3e1ef83d85071c7f20e5bf08c9c78bd))

* Tweaking: HelpAction -&gt; commands/__init__

Nothing else should use it. ([`4864852`](https://github.com/eyeonus/Trade-Dangerous/commit/4864852cfc9f42d1fe864761e83774e1ec58c934))

* Ignore pycallgraph.py, because reasons ([`c9ab508`](https://github.com/eyeonus/Trade-Dangerous/commit/c9ab5082af92662e16ff60a4e34e27547324b68a))

* Ignore anything in wip/ ([`5b84618`](https://github.com/eyeonus/Trade-Dangerous/commit/5b84618b04e273ec556ed9e505ce7f868b62e824))

* Stray tabs to spaces for merge easing ([`43aa96b`](https://github.com/eyeonus/Trade-Dangerous/commit/43aa96b7595ce30182b47b6d95697212813a987f))

* tabs to spaces in corrections.py also ([`4f5a48c`](https://github.com/eyeonus/Trade-Dangerous/commit/4f5a48ccc6a40c4103344e30acfc15f92fb40a82))

* tabs to spaces ([`427ca15`](https://github.com/eyeonus/Trade-Dangerous/commit/427ca151d351358b74fb665c12e6168c2e254ed8))

* Forward cmdenv, tdb properly to render ([`0d8be5a`](https://github.com/eyeonus/Trade-Dangerous/commit/0d8be5ac05967c17d58d53c8d2d0918133071710))

* Added wantsTradeDB commandEnv variable ([`b8b7d56`](https://github.com/eyeonus/Trade-Dangerous/commit/b8b7d5612b7d679c71ca132b84c73d3d5b7bf07e))

* Normalized cmdenv in trade.py ([`36f8aca`](https://github.com/eyeonus/Trade-Dangerous/commit/36f8acae89e3edf757f751fc1fe58669ce3562ae))

* Issue #50 fix for the fast algorithm ([`c9833c3`](https://github.com/eyeonus/Trade-Dangerous/commit/c9833c35d8f1109d9c49553bd950fd923333e757))

* Minor cleanup ([`e71a0f4`](https://github.com/eyeonus/Trade-Dangerous/commit/e71a0f4230afa6f8c030a405a49c92a4c1ecf269))

* Removed bad system ([`2e4d5d2`](https://github.com/eyeonus/Trade-Dangerous/commit/2e4d5d269b5aebf38baedbb1467c115c18fa0ee6))

* Not enough Wangs ([`085dff0`](https://github.com/eyeonus/Trade-Dangerous/commit/085dff0c9ed63094d0d0e39ed9b7c8c7d4455923))

* Latest from the forums ([`0005146`](https://github.com/eyeonus/Trade-Dangerous/commit/000514697598ab4e93617576804b3e425b92fc30))

* Quote all non numeric fields execpt for the header line. ([`637e138`](https://github.com/eyeonus/Trade-Dangerous/commit/637e138b27b001e703956e7798e60084eb61b0dc))

* Use maxLyEmpty when there&#39;s a --full that is False ([`5983f08`](https://github.com/eyeonus/Trade-Dangerous/commit/5983f089be404ab4e35a6b8615137224a3aa80ca))

* Remove a few rogue systems ([`18eecbd`](https://github.com/eyeonus/Trade-Dangerous/commit/18eecbd5414da0a2391d652a621992eaca322071))

* Beta3 Systems with markets + preliminary station list ([`4618f6f`](https://github.com/eyeonus/Trade-Dangerous/commit/4618f6f928c107587dbbbaf7603b6b351dab4189))

* Issue #50 Interaction between -0 and demand for a sold item

Try to honor -0 a little more while trying to avoid the risk of users making items inaccessible.

This change means that -0 will be honored if the &#34;fromStn&#34; price is 0, but if the station is
buying an item (fromStn &gt; 0) then it will revert to using the default (unk) for the demand
field. ([`b5775e1`](https://github.com/eyeonus/Trade-Dangerous/commit/b5775e14a9b17b351f999e149b4c711b693271ec))

* Issue #51 L and ? items weren&#39;t honoring qty limits ([`159b15c`](https://github.com/eyeonus/Trade-Dangerous/commit/159b15cf3aaf5d839fb43e763764036a806c3eaa))

* &#34;TradeGitty&#34; work in-progress nav conversion&#34; ([`51630a6`](https://github.com/eyeonus/Trade-Dangerous/commit/51630a62a68587e13ce425fd8c509a45aa84c019))

* &#34;TradeGitty&#34; command template ([`bf48738`](https://github.com/eyeonus/Trade-Dangerous/commit/bf4873836a7475a67963b795e28539de0ba7c286))

* &#34;TradeGitty&#34;

Passing (results, cmdenv, tdb) to run and render actually lowers
the boilerplate threshold so I&#39;m going to go ahead and do that. ([`2daa3b5`](https://github.com/eyeonus/Trade-Dangerous/commit/2daa3b5cb210e51a4febd3a2607755b651cd5d59))

* Issue #49 AmbiguityError was generating a call stack

You can tell when I&#39;ve been working in C++, the &#39;self&#39;s dissapear. ([`0e935c2`](https://github.com/eyeonus/Trade-Dangerous/commit/0e935c2898d9d658e31744e37c7c7da976b596f1))

* &#34;TradeGitty&#34; NOT READY FOR PRODUCTION

Refactored the encapsulation of cmdenv a little to reduce boiler plate
and make it easier to use adn intercept.

Added some encapsulation of the results returned from the run() stuff
so that it&#39;s more structured and looks more like formal objects.

Restored local_cmd to basic working status. ([`111ba6a`](https://github.com/eyeonus/Trade-Dangerous/commit/111ba6a5abd5412cb632841c81728af960b83781))

* &#39;TradeGitty&#39;: NOT READY FOR PRODUCTION

More work on the big refactor to separate concerns.

This version introduces the commands subdirectory (to replace subcommands) and replaces &#39;TradeEnv&#39; with &#39;CommandEnv&#39;,
and it breaks out the functionality in the command modules into a &#39;run()&#39; and &#39;render()&#39; state.

(I might rename &#39;run&#39; to &#39;query&#39; or something)

A big part of the change is that we only load stuff for the current command unless you are using -h
or have generated a usage request somehow.

Should speed up loading a lot but this should also put us in a better standing to do lazy loading
etc.

One problem I don&#39;t yet feel I&#39;ve solved is how we&#39;re going to re-use the TradeDB between calls;
it&#39;s fine if you are just changing a few outlying parameters, but what if you do something
like change the db path? ([`0f7ac8a`](https://github.com/eyeonus/Trade-Dangerous/commit/0f7ac8aae284c24f36820707c5b8eb223ab95a38))

* Merge branch &#39;master&#39; into devel ([`a5f62c0`](https://github.com/eyeonus/Trade-Dangerous/commit/a5f62c001ff6a279d5e52317f1328101abb4051e))

* v5.0.0 ([`6cc6727`](https://github.com/eyeonus/Trade-Dangerous/commit/6cc67271b7ac53943e9c61ed4b9eacac8924fd84))

* Refactoring &#34;args&#34; to be &#34;TradeEnv&#34; -&gt; &#34;tdenv&#34;

This change breaks up &#39;trade.py&#39; into several smaller command
modules and provides an interface for supplying arguments to
them.

It needs more work to expose the functionality in each module
so that the presentation can be overloaded, but this is step 1. ([`6e36e23`](https://github.com/eyeonus/Trade-Dangerous/commit/6e36e23552ffaed5b3bf411373e833711b406ed5))

* Station name (Hopkins Hangar -&gt; Cori Terminal) ([`7f28279`](https://github.com/eyeonus/Trade-Dangerous/commit/7f282791eef5fd030c2a1c51270f9e48af109b33))

* Beta 3 item name changes ([`07d54f6`](https://github.com/eyeonus/Trade-Dangerous/commit/07d54f6a1645c141c5cf571683eb9d28cc7144a0))

* Drugs -&gt; Legal Drugs ([`a29fff5`](https://github.com/eyeonus/Trade-Dangerous/commit/a29fff5be06a0b78ca91a6db30c03724821007b2))

* Merge branch &#39;master&#39; into beta3 ([`a816c16`](https://github.com/eyeonus/Trade-Dangerous/commit/a816c1615c1ba2151932f0d3374fe5483c079c85))

* Expanded fuzzy matching for system lookup

lookupSystemRelaxed will match station names so long as all the station matches point to the same system. ([`9618748`](https://github.com/eyeonus/Trade-Dangerous/commit/9618748aeff838c23e7437f40900637efc4a8459))

* AmbiguityError now takes a list

This will allow capture of the list in-case you want to evaluate whether or not it really represents an ambiguity

(e.g. we can return all the things that match &#39;Azeban&#39; and then say &#39;wait, these are all the same system, ok, lets use the system) ([`06c7716`](https://github.com/eyeonus/Trade-Dangerous/commit/06c77168db4cca6e6f7955361112416b341b9253))

* .prices syntax touch-up

- &#34;?&#34; replaces &#34;unk&#34;, &#34;-&#34; replaces &#34;n/a&#34;,
- Default to &#34;?&#34; in the &#34;demand&#34; column for items with a sale price,
- Default to &#34;-&#34; in the &#34;stock&#34; column for items with no sale price. ([`f77dab7`](https://github.com/eyeonus/Trade-Dangerous/commit/f77dab78379f1cf0f156f0c5fd97a87d4b25b782))

* AltItems change to match. ([`41275b1`](https://github.com/eyeonus/Trade-Dangerous/commit/41275b16c7960d0e394852cc80e6b3bf44d81529))

* Data changes in support of Beta 3

- Corrections now supports Stars, Systems, Categories and Items,
- Added some new items I saw in Beta 3,
- Added some item and category changes I saw in beta 3, ([`e829b58`](https://github.com/eyeonus/Trade-Dangerous/commit/e829b5844cb95654dd6fa6b625d9f4d6129d59eb))

* Make assumed regeneration of stock levels less optimistic ([`e7301e7`](https://github.com/eyeonus/Trade-Dangerous/commit/e7301e7af5e7a17a584d22ec277c28263c325703))

* v4.7.0 Added &#34;buy&#34; sub-command ([`41b7e96`](https://github.com/eyeonus/Trade-Dangerous/commit/41b7e969f19152bfb8bc31ccbdbdd8e8191d3f62))

* Fix for distance calculations that broke in 4.6.2 ([`5414236`](https://github.com/eyeonus/Trade-Dangerous/commit/5414236552af811816929d9903c74efe9f20bad2))

* Merge branch &#39;master&#39; into devel ([`b08b739`](https://github.com/eyeonus/Trade-Dangerous/commit/b08b739235cce2aac06130ae90f9d6fbc2bf127d))

* Better feedback on unrecognized station in .prices ([`3892ff0`](https://github.com/eyeonus/Trade-Dangerous/commit/3892ff086974a3e817a2bac307151bac3da4054b))

* buildcache.py cleanup and repeat-data error reporting

Mostly a stylistic and performance tune up of buildcache.py but this also improves error reporting from
the cache builder and also checks for repeated instances of stations and item-by-station. ([`aa0a1e5`](https://github.com/eyeonus/Trade-Dangerous/commit/aa0a1e5c2107d5d3ae57198cf8d4ee47c40e7c32))

* Re-implemented sqrt&#39;d distances in System.links

Proved to be a sharp edge and while I could just wait until I&#39;ve
had my coffee and fix the bugs I introduced, I think it&#39;s better
to recognize I introduced a sharp edge and put it back how it
was :) ([`47c9dce`](https://github.com/eyeonus/Trade-Dangerous/commit/47c9dcea5f636bf2bb312c269381e5391f629274))

* Merge branch &#39;master&#39; into devel ([`77dcbe1`](https://github.com/eyeonus/Trade-Dangerous/commit/77dcbe17bd105685b1b9a946ef3a66604438ecda))

* v4.6.2 ([`a9b4dcb`](https://github.com/eyeonus/Trade-Dangerous/commit/a9b4dcbf87770302a3c06ab342e7e9d45b8452fc))

* Optimize building of links data by using squared values instead of roots.

This requires the consumer to perform their own math.sqrt() but it reduces the number of them done during loading, etc, and in most cases you can simply compare the square of your desired distance against the stored value. If you are limiting to a max of 5 lightyears, then you are limiting to a max of 5^2 lightyears^2. ([`9fe55e1`](https://github.com/eyeonus/Trade-Dangerous/commit/9fe55e1eb26acbf5ecc8c7e92ca4ecea81277554))

* Optimize population of trades data. ([`d57d794`](https://github.com/eyeonus/Trade-Dangerous/commit/d57d7940623175be4fc3a0eb2a0d583a7f22748b))

* Whitespace ([`77d67fc`](https://github.com/eyeonus/Trade-Dangerous/commit/77d67fcae344eb3531a59b539944dabb95bcea7a))

* Removed &#39;tdb&#39; variable from global namespace in trade.py ([`ce56a30`](https://github.com/eyeonus/Trade-Dangerous/commit/ce56a3026418c565186d4fe5b8fd36d34ba86caf))

* Avoid buildingLinks/loadingTrades when we don&#39;t need it. ([`0d8d9d3`](https://github.com/eyeonus/Trade-Dangerous/commit/0d8d9d3cb4dcde0f228db65302ebb999ce191a43))

* Better explanation of why nothing matches ([`3b78e05`](https://github.com/eyeonus/Trade-Dangerous/commit/3b78e0592e4cb14048a9b02e48cdbeb460be6445))

* TradeDB() now takes buildLinks and loadTrades arguments ([`eb130ba`](https://github.com/eyeonus/Trade-Dangerous/commit/eb130ba2635dcd4c2baf6ff4696c7fd32ac93dd9))

* TradeDB.load() now takes buildLinks and loadTrades arguments (default True) ([`fd64016`](https://github.com/eyeonus/Trade-Dangerous/commit/fd64016a2db02d780c8fe3eefd03431609264c20))

* Don&#39;t pass lightyears to buildLinks, use the TradeDB value instead ([`63e9fa3`](https://github.com/eyeonus/Trade-Dangerous/commit/63e9fa3a95045db2a73d269d0131528b4dbab248))

* Ensure links have been populated when calling loadTrades ([`2d6652d`](https://github.com/eyeonus/Trade-Dangerous/commit/2d6652d6e7f64ec1f9d1588a3484825fc713a235))

* Keep track of numLinks in the TradeDB object itself ([`a49b6e7`](https://github.com/eyeonus/Trade-Dangerous/commit/a49b6e787de82f6bad623de2de7eed388b64264f))

* default values for TradeDB.{numLinks,tradingCount} to None ([`78d059a`](https://github.com/eyeonus/Trade-Dangerous/commit/78d059a1bd1385e1692553879352864e36fd29bf))

* Added mechanism for supporting star/station name changes ([`62004d1`](https://github.com/eyeonus/Trade-Dangerous/commit/62004d1f597d5da44faa95416021b7069df48a6b))

* Fix for command-line buildcache ([`3971e19`](https://github.com/eyeonus/Trade-Dangerous/commit/3971e19552bbdeb9c9c8e60a3738015553fb5617))

* Trivial typo ([`16290f9`](https://github.com/eyeonus/Trade-Dangerous/commit/16290f9367d3cc4b32dac3c9f2487f88884af38f))

* Merge branch &#39;master&#39; into devel ([`04ab156`](https://github.com/eyeonus/Trade-Dangerous/commit/04ab15613b62cf71039bd62a0a46418bdcda0c84))

* Added defaultZero to buildCache and optimized processing of basic format .price lines

buildCache can now take a defaultZero argument which coerces unspecified values to &#39;n/a&#39; instead of &#39;unk&#39;.
Also, when no demand/supply string is specified, bypass UnitsAndLevels (reducing number of function calls) ([`facfcfb`](https://github.com/eyeonus/Trade-Dangerous/commit/facfcfb5f3f2ea6e45012a2233625ce1f65a0cde))

* Added prices.Element enumerations ([`adbad4e`](https://github.com/eyeonus/Trade-Dangerous/commit/adbad4ee114fb066b490df63af5010722ca25962))

* Unused global reference ([`18a8a99`](https://github.com/eyeonus/Trade-Dangerous/commit/18a8a99671b32de9eb17a6ed581cddb605535509))

* Moved checklist code into its own class, and moved mfd to args ([`0d6effa`](https://github.com/eyeonus/Trade-Dangerous/commit/0d6effa5790f2bbbe3e123504f24702b8f9e4177))

* Made the calling of the commandFunction from args easier to read ([`0740fcf`](https://github.com/eyeonus/Trade-Dangerous/commit/0740fcf24798ff265d92bd72781c8976411e7e71))

* Added printHeading helper, removed mfd check after main ([`1ede5ce`](https://github.com/eyeonus/Trade-Dangerous/commit/1ede5ce43d6217b6f09cbb9f5d16616c18e06763))

* Minor tweaks to the .prices format ([`e46bba0`](https://github.com/eyeonus/Trade-Dangerous/commit/e46bba04b11bc9865c6f979a249ec35be819bbed))

* Fixed lowercase support in prices ([`696fe33`](https://github.com/eyeonus/Trade-Dangerous/commit/696fe337934f227f5801f5b365a7a9a4a8100a42))

* Merge branch &#39;master&#39; of bitbucket.org:kfsone/tradedangerous into devel ([`6215b64`](https://github.com/eyeonus/Trade-Dangerous/commit/6215b64a51afbfc54a6e82ac5f31b7871ef92b83))

* Support lowercase unit levels ([`68a4a8e`](https://github.com/eyeonus/Trade-Dangerous/commit/68a4a8e5b30295a9e92b86dcb4c1ed7261f71b30))

* Fixes to the .prices parsed based on gazelle&#39;s observations ([`32c5c12`](https://github.com/eyeonus/Trade-Dangerous/commit/32c5c1250d3133d6a53d628fe932a514bff7970b))

* Additional README for 4.6.0 ([`261436e`](https://github.com/eyeonus/Trade-Dangerous/commit/261436e6a2a2ac29a2a5e4603f5b330604c0b8a6))

* v4.6.0 ([`8c219f9`](https://github.com/eyeonus/Trade-Dangerous/commit/8c219f91ea4c2245c8be738e90304d809438bd85))

* Merge branch &#39;new-prices-format&#39; ([`af2de50`](https://github.com/eyeonus/Trade-Dangerous/commit/af2de507d882091f832cd9706bb7222fec6e76fe))

* Renamed main function so it can be imported.
Added command line parser.
Added some options (db name, save path, table name for single export) ([`c7eab23`](https://github.com/eyeonus/Trade-Dangerous/commit/c7eab2394cdcafafb731bd1aeeb3ab9f8d6b793b))

* ignore generated csv files in misc ([`c4be750`](https://github.com/eyeonus/Trade-Dangerous/commit/c4be7506c089d48ea97e389699a8001d36b02167))

* Allow overload of max-ly range during TradeDB construction/load ([`ab5db59`](https://github.com/eyeonus/Trade-Dangerous/commit/ab5db59729df8f03990f54f3ca9f43dcde93bcd9))

* Better feedback on missing price data ([`7de3ac5`](https://github.com/eyeonus/Trade-Dangerous/commit/7de3ac53b7c4839e70e17df29cf551b889eccd76))

* Station name corrections (from Smacker) ([`36cd40c`](https://github.com/eyeonus/Trade-Dangerous/commit/36cd40c2168f23b385952f131b9d553d6d534b91))

* Make &#39;0&#39; an alias for n/a ([`2c0ce8b`](https://github.com/eyeonus/Trade-Dangerous/commit/2c0ce8b4fe76f5134b4b6ef7457e4da5c5d1025e))

* Removed the &#39;@&#39; signs from the new format, so now it&#39;s just &#39;unk&#39;, &#39;n/a&#39;, &#39;50L&#39;, &#39;100M&#39;, etc. ([`0c1cf05`](https://github.com/eyeonus/Trade-Dangerous/commit/0c1cf05647d64d72896ebde3ecf5775ed8090bfd))

* Fix for location of prices.py ([`e5729a0`](https://github.com/eyeonus/Trade-Dangerous/commit/e5729a0cad0fc4b306e8a28c9d79d148678295d3))

* Adding support for a cleaner extended .prices format while retaining backwards compatability.

This new format does several things:
1. Makes the timestamp optional in input data and makes it optional as well as accepting &#39;now&#39; as a value,
2. Removes the words &#39;demand&#39; and &#39;stock&#39; from the line,
3. Replaces &#34;-1L-1&#34; with &#34;unk&#34; (unknown),
4. Replaces &#34;0L0&#34; with &#34;n/a&#34; (not available),
5. Replaces &#39;nnnL1&#39; with &#34;nnn@L&#34; (for low),
6. Replaces &#39;nnnL2&#39; with &#34;nnn@M&#34; (for medium),
7. Replaces &#39;nnnL3&#39; with &#39;nnn@H&#34; (for high) ([`b8c64d9`](https://github.com/eyeonus/Trade-Dangerous/commit/b8c64d9f0d2ebfc7f7fbcb4bce3738c29be79e10))

* Merge branch &#39;master&#39; into devel ([`75d0965`](https://github.com/eyeonus/Trade-Dangerous/commit/75d096505c7cd6e670335adfaa6493c7addfacd3))

* First version of the CSV export generator. ([`dbbae49`](https://github.com/eyeonus/Trade-Dangerous/commit/dbbae4973296dc7766efaf02d191920aab84d921))

* added foreign key reference from AltItemNames to Item ([`e1f48ae`](https://github.com/eyeonus/Trade-Dangerous/commit/e1f48ae3093d9d358d0642d8c63cad817a5e4aee))

* Merged in Smacker65/tradedangerous/LatestSystems (pull request #21)

Latest Systems from RedWizzard + updated case to canonical FD + merged contributors ([`f06e8fe`](https://github.com/eyeonus/Trade-Dangerous/commit/f06e8fedc038ecee5ff4829c56198ac0a06df1fb))

* Merged in bgol/tradedangerous/devel (pull request #22)

Only default to 0 if both values (quantity and level) of stock or demand are -1 ([`963085b`](https://github.com/eyeonus/Trade-Dangerous/commit/963085b419c57f28c963f643791fa511ebb6aa2c))

* Merge branch &#39;master&#39; into devel ([`6eebe49`](https://github.com/eyeonus/Trade-Dangerous/commit/6eebe49f35b215be9ef87413acf9ef2866c4bcc9))

* Added a few more station distances ([`7d62c17`](https://github.com/eyeonus/Trade-Dangerous/commit/7d62c177f19cffe997515efe39d19f6838e2e728))

* Silly typo in .prices comment ([`e3124d3`](https://github.com/eyeonus/Trade-Dangerous/commit/e3124d39a18f00c6854b7e812025fc808649aa6c))

* only default to 0 if both values are -1 ([`956cfb6`](https://github.com/eyeonus/Trade-Dangerous/commit/956cfb64ffcfbd72ff47e8f5b494e12d21da938e))

* +1 System from Harbinger ([`d34074b`](https://github.com/eyeonus/Trade-Dangerous/commit/d34074bfb3ba1c6c1c4416bd2ec6a93014f17f71))

* Latest Systems from RedWizzard + updated case to canonical FD + merged contributors ([`178d81c`](https://github.com/eyeonus/Trade-Dangerous/commit/178d81cf78a72f4dfdc84b700038a78430bdff1e))

* Got rid of old, redundant clutter ([`875e2d6`](https://github.com/eyeonus/Trade-Dangerous/commit/875e2d6dbb3599348b80f156fad3bf8ee0c3c7ab))

* Fixed --dir functionality ([`ffd510d`](https://github.com/eyeonus/Trade-Dangerous/commit/ffd510dd249ce189f9363e1cbbb258547167d48e))

* v4.5.1 Issue #39 Use script path to locate data directory.

When starting up, change current directory to match the path of trade.py
- so if you do &#34;trade/trade.py&#34; it will look for &#34;trade/data/...&#34;

Also added --dir (aka -C) to change directory ([`e34d1d3`](https://github.com/eyeonus/Trade-Dangerous/commit/e34d1d396d276d9658022b39a63b18724f11868e))

* v4.5.0 README ([`dad8399`](https://github.com/eyeonus/Trade-Dangerous/commit/dad8399fd2465987e08f9f984e2aa1925184c50d))

* Merged in Smacker65/tradedangerous/NewSystems2 (pull request #20)

Regather all changes for clean merge ([`675b595`](https://github.com/eyeonus/Trade-Dangerous/commit/675b59593a0e50e64a95cfa794b2c13e13cfc188))

* Regather all changes for clean merge ([`d34d164`](https://github.com/eyeonus/Trade-Dangerous/commit/d34d164f29b2c84693c933207d6102ff7c2bcbca))

* Merged in bgol/tradedangerous/newdata (pull request #17)

new system data v2 ([`661151a`](https://github.com/eyeonus/Trade-Dangerous/commit/661151ae5b17670ccbbd15422e5c1fa757c8397e))

* four new systems from Harbinger ([`b77e2d8`](https://github.com/eyeonus/Trade-Dangerous/commit/b77e2d8affc3c4f5e32c84d65afb54dbda2ffc07))

* latest calculation run with all accumulated data ([`db9c100`](https://github.com/eyeonus/Trade-Dangerous/commit/db9c100417c26977e41e5811ef5ab00ea9b23b10))

* v4.4.0 ([`1cc3393`](https://github.com/eyeonus/Trade-Dangerous/commit/1cc33938c45042d22f098fbe113cf4ff8801e75c))

* Merged in bgol/tradedangerous/newdata (pull request #15)

some new system data ([`966d09e`](https://github.com/eyeonus/Trade-Dangerous/commit/966d09ef92acb56118460d8283b8dd3bb57b76ca))

* new calculation run ([`c459b1f`](https://github.com/eyeonus/Trade-Dangerous/commit/c459b1f6d4b4ea1127a3215c723e3ccbcc71e061))

* sim sala bim ([`a0d2d32`](https://github.com/eyeonus/Trade-Dangerous/commit/a0d2d32faf81658ae18b28e916a9b91bc3fb1812))

* update to follow smackers cheanges ([`78892af`](https://github.com/eyeonus/Trade-Dangerous/commit/78892af290fb80ea09d9e5562e219623d3371c52))

* sorting by name ([`f554dd3`](https://github.com/eyeonus/Trade-Dangerous/commit/f554dd3cdcb99a7f7a611b1d2cfdc1f6793f42ca))

* sort by name ([`b6c5d7a`](https://github.com/eyeonus/Trade-Dangerous/commit/b6c5d7ae2b54a1d2a5fbfd210a1f40ebd00c6d8a))

* latest calculation run ([`b90b259`](https://github.com/eyeonus/Trade-Dangerous/commit/b90b259875f83a79e7057d69821e6fb86256bbb1))

* I&#39;m using a combination of all gathered data to calculate systems ([`57839f5`](https://github.com/eyeonus/Trade-Dangerous/commit/57839f5a1d0e28bce95fe1162328bc9454c0a750))

* new station from SelectThis http://forums.frontier.co.uk/showpost.php?p=885489&amp;postcount=323 ([`1e34128`](https://github.com/eyeonus/Trade-Dangerous/commit/1e34128f0ae0facb757a77b4f1d1b0052fba5f1b))

* Typo in Harbinger&#39;s name, oops ([`32a06d2`](https://github.com/eyeonus/Trade-Dangerous/commit/32a06d2e82048c16f256b59b86f370ada11d2834))

* Minor tweaks to Gazelle&#39;s change, also added it to the README. ([`ece1a10`](https://github.com/eyeonus/Trade-Dangerous/commit/ece1a1011f0fb224f9cf4a79250e8cc694a63be2))

* Merged in bgol/tradedangerous/csvimport (pull request #14)

Removed INSERTs from the SQL file ([`de7b4d4`](https://github.com/eyeonus/Trade-Dangerous/commit/de7b4d44ba1304570926035a7e0d2fb28a1d4d61))

* Fixed description of gazelle&#39;s change ([`e519552`](https://github.com/eyeonus/Trade-Dangerous/commit/e51955263321a5536c4f961dd45112c2abf85a93))

* code simplified as per owner request ([`0f775ac`](https://github.com/eyeonus/Trade-Dangerous/commit/0f775acce56cee3991e224217606ec5a8261a986))

* v4.3.0 ([`2aab8ef`](https://github.com/eyeonus/Trade-Dangerous/commit/2aab8ef1b92843c53689e9d4ba8219d5a0a13ec9))

* Merged in bgol/tradedangerous (pull request #13)

default to zero for demand/stock ([`a1bbb28`](https://github.com/eyeonus/Trade-Dangerous/commit/a1bbb285a56f480179ef7d7fd01f542f03690479))

* 25 new systems from harbinger https://forums.frontier.co.uk/showpost.php?p=883906&amp;postcount=363 ([`3c27d37`](https://github.com/eyeonus/Trade-Dangerous/commit/3c27d3739070fb32fc53230784d526c39e1a4112))

* removed default to zero, shouldn&#39;t be in this branch ([`ca0d9ed`](https://github.com/eyeonus/Trade-Dangerous/commit/ca0d9ed7bcdf36e5f5677959d9ba62520e15e038))

* ups, station.csv was wrong ([`aaf6b97`](https://github.com/eyeonus/Trade-Dangerous/commit/aaf6b97d6bf4959f4b790b7034a53412a7d61d3d))

* Merge branch &#39;master&#39; of bitbucket.org:kfsone/tradedangerous into csvimport

Conflicts:
	data/TradeDangerous.sql ([`5e1b3a5`](https://github.com/eyeonus/Trade-Dangerous/commit/5e1b3a53f15235019653bfd9a0ea2e1aad8667c0))

* Merge branch &#39;master&#39; of bitbucket.org:kfsone/tradedangerous ([`c81e1ed`](https://github.com/eyeonus/Trade-Dangerous/commit/c81e1ed9f09124dfe246b543608b53ed0784b449))

* v4.2.3 ([`b0079b9`](https://github.com/eyeonus/Trade-Dangerous/commit/b0079b96c99466a01c69807d69061978ae755b1a))

* Merged in Smacker65/tradedangerous/SystemUpdate (pull request #12)

Add new systems from forums + new column indicating source of data + table to enumerate this ([`dc330e1`](https://github.com/eyeonus/Trade-Dangerous/commit/dc330e174697c06b0bf4c050060c09b73cca1d38))

* Fixed typo ([`53280df`](https://github.com/eyeonus/Trade-Dangerous/commit/53280dfa76ed4bb2c92b20bf174b2a9d3e0ff6ad))

* Latest set of new systems from Harbringer ([`4168dfb`](https://github.com/eyeonus/Trade-Dangerous/commit/4168dfb08c42e34c326d9eb73c217ade9e187ee6))

* more debug output ([`1894322`](https://github.com/eyeonus/Trade-Dangerous/commit/18943224e030545fc93795a21d5f3b7ac3e868af))

* set doublequote to True, better save than sorry ([`347a91c`](https://github.com/eyeonus/Trade-Dangerous/commit/347a91cdb0e0dadb12e053268e1bc2c68082a86d))

* change -1 to 0 if update is called with --zero ([`7dde501`](https://github.com/eyeonus/Trade-Dangerous/commit/7dde501996bb00fe79f1deb6ef2e07b7ec6900c2))

* two new stations ([`fe1325a`](https://github.com/eyeonus/Trade-Dangerous/commit/fe1325a5168fcacf5f0b08e9c1d2c1fd1c8846b0))

* some code cleanup ([`b140f90`](https://github.com/eyeonus/Trade-Dangerous/commit/b140f9085f359931d4748ef95e3c3b49719a235c))

* break out the loop if one file is newer, no reason to check the others ([`2f4fa10`](https://github.com/eyeonus/Trade-Dangerous/commit/2f4fa1021716bef427e3a26322a21cc6ae671dfc))

* no more inserts in the sql file ([`5c772f8`](https://github.com/eyeonus/Trade-Dangerous/commit/5c772f8d844fc1251459f3636e434e2d3a063397))

* Missed some Source values on new systems ([`0cd845c`](https://github.com/eyeonus/Trade-Dangerous/commit/0cd845cfe102068ab78e201b7664db4fcd280bd1))

* Merge remote-tracking branch &#39;Master/master&#39; into SystemUpdate ([`f61aff0`](https://github.com/eyeonus/Trade-Dangerous/commit/f61aff0fd0f22d42b519fff6403696495b2448d4))

* New systems from RedWizzard ([`b65934f`](https://github.com/eyeonus/Trade-Dangerous/commit/b65934f4bcef4758da342740eca289f4ece72492))

* Add new switch [--zero] to the update command to default to 0 values for demand/stock ([`c502ff5`](https://github.com/eyeonus/Trade-Dangerous/commit/c502ff598734dac995b68853737caffe08a99ea8))

* Merge branch &#39;master&#39; of https://bitbucket.org/kfsone/tradedangerous ([`a23543b`](https://github.com/eyeonus/Trade-Dangerous/commit/a23543b6bb7e638521b83b88ca53f3c4ca11e67c))

* v4.2.2 Added --npp and --vim options to &#39;update&#39; sub-command.

--npp tries to launch Notepad++, --vim tries to launch vim editor. ([`65f6646`](https://github.com/eyeonus/Trade-Dangerous/commit/65f664655646b3331ac1f0ec6dc11df45e3b8d02))

* Added tradeexcept.py ([`b494981`](https://github.com/eyeonus/Trade-Dangerous/commit/b4949817882ea286fc8994df85f21de363de28ce))

* Normalized error handling so more errors get the user-friendly treatment ([`9054cb0`](https://github.com/eyeonus/Trade-Dangerous/commit/9054cb0dc495713c27ba1955a029ad9a7bafe7f7))

* New systems from Harbringer ([`54ddd56`](https://github.com/eyeonus/Trade-Dangerous/commit/54ddd5684fdcc8980fddbdb9e53dca8455f3ffa0))

* print the real name of the system, not what the user typed ([`55bfac3`](https://github.com/eyeonus/Trade-Dangerous/commit/55bfac3aa77af73fc522b8fe63e349d948765fb5))

* Moved to correct contributor ([`7a2a4ac`](https://github.com/eyeonus/Trade-Dangerous/commit/7a2a4acc0d6785332adf47669b699514b35ed6ae))

* Merge remote-tracking branch &#39;Master/master&#39; into SystemUpdate ([`42b0d83`](https://github.com/eyeonus/Trade-Dangerous/commit/42b0d835a4c5e9d199154df24629bc36036cbdfb))

* One more system from Wolverine2710 ([`f2f189f`](https://github.com/eyeonus/Trade-Dangerous/commit/f2f189f70f2410c6f58e8b44ab8c0e4d9b2000e6))

* New coordinates from RedWizard ([`cb04e72`](https://github.com/eyeonus/Trade-Dangerous/commit/cb04e725729c39a55e756796ed0e6abcb4627752))

* Additional logging output to track down issue with finding the .sql file ([`93998f3`](https://github.com/eyeonus/Trade-Dangerous/commit/93998f3f0f5c4f9ef6f523b6e4b68ffc7b173815))

* Add new systems from forums + new column indicating source of data + table to enumerate this ([`0570212`](https://github.com/eyeonus/Trade-Dangerous/commit/0570212a0fe7caecf8433fea73cbdc9203fa8c78))

* Fixed failure in trade run ([`60d4e4f`](https://github.com/eyeonus/Trade-Dangerous/commit/60d4e4fa6802f32261d9e0e651549ae2e1427251))

* Added missing Battle Weapons item ([`3785b82`](https://github.com/eyeonus/Trade-Dangerous/commit/3785b826993bc9002b3bb8d4b17bb08f8aae9aa9))

* v4.2.1 ([`36e89b0`](https://github.com/eyeonus/Trade-Dangerous/commit/36e89b06772fbdf9037bc7a37ee2c92c8564c5c1))

* Removed spurious ,102,s from .sql file ([`a6e08af`](https://github.com/eyeonus/Trade-Dangerous/commit/a6e08af4084a70bb250d86459b7278dd535a6980))

* Merged in ShadowGar/tradedangerous (pull request #11)

Added more stars ([`656aa47`](https://github.com/eyeonus/Trade-Dangerous/commit/656aa471b2b697dcebba22eb5c1fad160a565363))

* Better instructions in the .prices file comments ([`b1e8bfd`](https://github.com/eyeonus/Trade-Dangerous/commit/b1e8bfd9871aca5c0d612bbc2c4e7841aedb0e87))

* updated readme with changes ([`b97b834`](https://github.com/eyeonus/Trade-Dangerous/commit/b97b834b80f744266e1ade3017c576e04c397916))

* Merge branch &#39;master&#39; of https://bitbucket.org/ShadowGar/tradedangerous ([`3f6c1d9`](https://github.com/eyeonus/Trade-Dangerous/commit/3f6c1d90f5a57a37f3c2845e42d9c639cb605cdf))

* Added more systems from https://forums.frontier.co.uk/showpost.php?p=878148&amp;postcount=223  Also corrected HAGALAZ&#39;s position as per https://bitbucket.org/kfsone/tradedangerous/issue/10/system-hagalaz-in-wrong-position ([`4ba4311`](https://github.com/eyeonus/Trade-Dangerous/commit/4ba4311d46670c414ce8b27ab0299e312fa229ce))

* Merged kfsone/tradedangerous into master ([`388ece7`](https://github.com/eyeonus/Trade-Dangerous/commit/388ece736e0d000d7aef3fb6889d2485636f8dca))

* v4.2.0
  Minor changes to the command line for &#34;local&#34; command,
  factoring in that the &#34;pill&#34; will eventually go away. ([`f44bbd5`](https://github.com/eyeonus/Trade-Dangerous/commit/f44bbd5a9a06f401c398dfd6b155332b015bc83b))

* Properly forward debug level so that build cache sees it ([`5e1188c`](https://github.com/eyeonus/Trade-Dangerous/commit/5e1188cf1a531e4dc42c8e7876685341b56ad7c2))

* Merged in Smacker65/tradedangerous/LocalForPull (pull request #9) ([`0a8e4ef`](https://github.com/eyeonus/Trade-Dangerous/commit/0a8e4efb7d7f54661d18b7dca7d1bd9b4a18f2f7))

* v4.1.0 ([`88fdcb4`](https://github.com/eyeonus/Trade-Dangerous/commit/88fdcb42674e2fd06b4dc18e55c2f06ccce4ddf8))

* Better feedback to the user when there is no data for the things they are querying ([`460d8fa`](https://github.com/eyeonus/Trade-Dangerous/commit/460d8fa5d5c54619551b358b7d52d9f374311351))

* Track number of Price entries for all stations so we can tell when there is actually no data ([`2df1d37`](https://github.com/eyeonus/Trade-Dangerous/commit/2df1d37e184d888f9930b2e1cb0c45e75aebcb64))

* Allow absence of .prices file ([`917d8fd`](https://github.com/eyeonus/Trade-Dangerous/commit/917d8fd6cadcce6fa79aaa744ceaa36ee41e24b5))

* Default values for demand/demandLevel/stock/stockLevel should be -1 ([`8bb5a09`](https://github.com/eyeonus/Trade-Dangerous/commit/8bb5a09456ead3706a56b88590c56db52c4131d5))

* Merged in bgol/tradedangerous (pull request #10) ([`da11e6f`](https://github.com/eyeonus/Trade-Dangerous/commit/da11e6f0ef6b2611c9c4052c8723e68e1ad94886))

* v4.0.4 README ([`c3e0b55`](https://github.com/eyeonus/Trade-Dangerous/commit/c3e0b5562990eccd2bab4ff032c837f80e5c05cf))

* Issue #20: Strange ambiguity supplying &#39;72&#39; as system name

To fix this, I&#39;m making listSearch use a more optimistic approach (assume that ambiguity is unlikely) with
separate queueing of word and partial matches so that we only check for ambiguity after we have considered
all candidates. ([`1246b4f`](https://github.com/eyeonus/Trade-Dangerous/commit/1246b4f526a4d8349643977ae5a70f8a23b03aa1))

* Executable permissions for trade.py ([`c00b5b8`](https://github.com/eyeonus/Trade-Dangerous/commit/c00b5b8096f30c38add20568554d7d298de4fa0f))

* Fixed references to Louis ([`f5f70e3`](https://github.com/eyeonus/Trade-Dangerous/commit/f5f70e3aa94e965b7ebfa3f5ba43578ce4457250))

* Fixed Lacaille Prospect station name for beta 2 ([`f269d4d`](https://github.com/eyeonus/Trade-Dangerous/commit/f269d4d73326144f01b6c5536f45c30de014de39))

* add the price file to the ignore list ([`b380337`](https://github.com/eyeonus/Trade-Dangerous/commit/b380337b9b1786729a8fdd72f9734d062b0f0b07))

* don&#39;t keep the price file in the repository ([`647cf36`](https://github.com/eyeonus/Trade-Dangerous/commit/647cf36d12be47c6bf2721168cfbde99344155d3))

* If a station is given and there are no prices, generate one with all known items. Also generate a new timestamp if there is a station. ([`e345713`](https://github.com/eyeonus/Trade-Dangerous/commit/e3457135f57561d593672a05eaca27fdaabc655f))

* added [--all] switch to update which will produce a temp file with all colums ([`e073d77`](https://github.com/eyeonus/Trade-Dangerous/commit/e073d77f85566f5295e7123902116594e015c24e))

* Merged kfsone/tradedangerous/master into LocalForPull ([`a19bb7f`](https://github.com/eyeonus/Trade-Dangerous/commit/a19bb7f5908653ccc2be7c0aa3c88c3259b368a9))

* Fix typo bugfixes ([`829208b`](https://github.com/eyeonus/Trade-Dangerous/commit/829208be27359c0086669a15395188fc9c304dcf))

* Merged kfsone/tradedangerous into master ([`7aa5e81`](https://github.com/eyeonus/Trade-Dangerous/commit/7aa5e816190cc0914dba55130b77cd1a46561d6c))

* v4.0.3 ([`f6579c6`](https://github.com/eyeonus/Trade-Dangerous/commit/f6579c673eb4a39d14d5fcf541273500580c2ef9))

* Issue #19 Beryllium and Gallium are incorrectly identified as Minerals

- Moved them to Metals
- Changed the cache builder to only require cat-qualified names if there is a conflict to be resolved ([`92e54c1`](https://github.com/eyeonus/Trade-Dangerous/commit/92e54c1dc428d8929b5b4c99b1561c20f94d43d6))

* Issue #11 Partial name matches weren&#39;t generating an ambiguity

For example, &#39;ra&#39; would match &#39;taran&#39; instead of complaining about &#34;26 draconis&#34;, &#34;CM Draco&#34;, etc. Also &#34;Ross&#34; would match the last Ross encountered. ([`a404374`](https://github.com/eyeonus/Trade-Dangerous/commit/a404374552f9ce780ddea693ae8fb4c6a1304d1a))

* Station name correction ([`968e6a0`](https://github.com/eyeonus/Trade-Dangerous/commit/968e6a0478c451fe2fc4514d760d0983703a4008))

* Catch whole-word matches in avoids ([`f6859ef`](https://github.com/eyeonus/Trade-Dangerous/commit/f6859eff428ff47d3e7d0fcc4a9cb4fc0ae8241e))

* Fix bad merge ([`f4a9c9a`](https://github.com/eyeonus/Trade-Dangerous/commit/f4a9c9a731baf35f3d7f614e8c566c8091ed53fa))

* Ignore merge tool temp file ([`8d8a5c4`](https://github.com/eyeonus/Trade-Dangerous/commit/8d8a5c48291e3fbc184a4417222961d4223f2c40))

* Merge remote-tracking branch &#39;origin/master&#39; into localsubcommand

Conflicts:
	data/TradeDangerous.sql ([`eb6219b`](https://github.com/eyeonus/Trade-Dangerous/commit/eb6219b9f424f36d70f7fd579af8e13768e2e38f))

* Merged kfsone/tradedangerous into master ([`2bf298f`](https://github.com/eyeonus/Trade-Dangerous/commit/2bf298f303470289f337bdf5465a924ece430238))

* Merged kfsone/tradedangerous into master ([`ff76716`](https://github.com/eyeonus/Trade-Dangerous/commit/ff76716682433771adbd6bd0e588a8aa618979fc))

* Merged in ShadowGar/tradedangerous (pull request #7)

Beta 2 Stars Final ([`1584f58`](https://github.com/eyeonus/Trade-Dangerous/commit/1584f5840b04374e0ab541a83a3cd92aebba9967))

* Merged kfsone/tradedangerous into master ([`317a41e`](https://github.com/eyeonus/Trade-Dangerous/commit/317a41e415c0ac7a202cf81bd6cc689dd25b2a9d))

* All BETA 2 Stars with Markets are now added. A list has been compiled of systems that SHOULD have markets but do not. I have sent a ticket on this issue. Also HALGAZ has been removed for the moment while we determine its proper coords. ([`be97b4c`](https://github.com/eyeonus/Trade-Dangerous/commit/be97b4c285a0f9aef213545d36acd1fc5c7a1bc5))

* Cleaned up debug output from previous commit ([`f8b623c`](https://github.com/eyeonus/Trade-Dangerous/commit/f8b623c543a298c5281c2f262988974038058368))

* Add &#34;local&#34; debug ([`9206284`](https://github.com/eyeonus/Trade-Dangerous/commit/9206284d3248286cb50a385777d1e311778c2c47))

* Add new station ([`17a95e0`](https://github.com/eyeonus/Trade-Dangerous/commit/17a95e0592134a64caacb4b3acfe89aa05a89721))

* Use HIP 107457 as second reference system ([`122b6f0`](https://github.com/eyeonus/Trade-Dangerous/commit/122b6f08e51d6a77ad15f7066bc956ae3620e3b5))

* Merged kfsone/tradedangerous into master ([`ac6e39a`](https://github.com/eyeonus/Trade-Dangerous/commit/ac6e39a24c8906d6a0393e081d44915199529863))

* Add percentage option for length along Pill ([`6551a28`](https://github.com/eyeonus/Trade-Dangerous/commit/6551a287b2a51af5611a1aa2b2516a9a4d0242dc))

* Update documentation for Pill length ([`8494eb6`](https://github.com/eyeonus/Trade-Dangerous/commit/8494eb684aa751d902cf1a8ba98d53e7af4163ec))

* Add length along pill calculation ([`12f4c06`](https://github.com/eyeonus/Trade-Dangerous/commit/12f4c06467de31457c292bacc4786d57100be2da))

* Added &#34;local&#34; sub-command ([`5a2672c`](https://github.com/eyeonus/Trade-Dangerous/commit/5a2672c597ae8f217788494a98f7d2d739833473))

* Made it so that word matches make for a reduction in ambiguity, so &#39;Aulin&#39; doesnt match PAULING ([`a643881`](https://github.com/eyeonus/Trade-Dangerous/commit/a643881b3ecf50e57908c3661dbe876e2bf1e050))

* Merged kfsone/tradedangerous into master ([`8e68ee8`](https://github.com/eyeonus/Trade-Dangerous/commit/8e68ee807b7627ed21229a65bdd7ee45ff465552))

* v4.0.2 ([`80aab11`](https://github.com/eyeonus/Trade-Dangerous/commit/80aab117f824d46fcf5b1efcc38e7c2caaf7d71d))

* Merged in ShadowGar/tradedangerous (pull request #6)

More Beta 2 Stars Added. ([`d9edcf8`](https://github.com/eyeonus/Trade-Dangerous/commit/d9edcf849f4479efa55f6ffc21003beabcefca1c))

* Mention sublime text 2 in addition to 3 ([`e93a6bf`](https://github.com/eyeonus/Trade-Dangerous/commit/e93a6bfb76b8f537268694f50778f68bed8f63bf))

* try container for the editor launch in update ([`056853d`](https://github.com/eyeonus/Trade-Dangerous/commit/056853d2067e909757cd7daac16ac3cb899f7b00))

* Added v4.0.1 readme ([`ddce31a`](https://github.com/eyeonus/Trade-Dangerous/commit/ddce31a0a7a7079c16b0980e992f0ebf092050f5))

* Fixed sublime under Windows ([`81ab99f`](https://github.com/eyeonus/Trade-Dangerous/commit/81ab99f8f1a6cc1a1591fed1072cbd70c6941fc3))

* Improved functionality for --subl, now capable of finding the editor on a Linux box/Mac ([`4c74621`](https://github.com/eyeonus/Trade-Dangerous/commit/4c74621f7f655c99bae3bf8fa67eb38a43a4fbc1))

* Added more systems and cleaned up the code. 113 Systems to go. :) ([`a220087`](https://github.com/eyeonus/Trade-Dangerous/commit/a22008781efc8f79453437c6a34c0b0bbcfd3fd9))

* Added systems from gazelle. Also some other system data. -Still working on adding the rest. ([`8cd89e3`](https://github.com/eyeonus/Trade-Dangerous/commit/8cd89e3bfd967fc2e753de6702852993a1d81591))

* Merged kfsone/tradedangerous into master ([`8c742f3`](https://github.com/eyeonus/Trade-Dangerous/commit/8c742f3ff47b29a71b614ea86a9d30b9b8fbae34))

* Updated README after importing ShadowGar&#39;s work. ([`494fa31`](https://github.com/eyeonus/Trade-Dangerous/commit/494fa31b4492e22ed3d7465bb9accb35801af2b8))

* Merged in ShadowGar/tradedangerous (pull request #5)

Beta 2 System/Stations Updates (partial) ([`78ab2fa`](https://github.com/eyeonus/Trade-Dangerous/commit/78ab2fadd0395958c6000c1cca9251ea186c4ad2))

* system ID conflict fixed. Typo,my bad. ([`bd587b8`](https://github.com/eyeonus/Trade-Dangerous/commit/bd587b8081005751fadd6700ab8c3db1df25e861))

* Added Beta 2 Stars provided by M.Brookes. ([`462a9e2`](https://github.com/eyeonus/Trade-Dangerous/commit/462a9e2854d8ae6681418ed0c0546b58dca551c7))

* Added a bunch of systems and stations. Stopped adding market data, this was taking way too long. I&#39;d rather get all markets in at least, then populate. ([`58bd409`](https://github.com/eyeonus/Trade-Dangerous/commit/58bd409456a35b99ab2f483a9f970c83f6b964ff))

* Added list so I can keep track of progress adding systems. ([`f704668`](https://github.com/eyeonus/Trade-Dangerous/commit/f704668589ebb022b7199976c6a920b703132f5f))

* Added four more stations and systems with trading information. Also added in initial navigation calculations by Codec for unknown stars. ([`1575173`](https://github.com/eyeonus/Trade-Dangerous/commit/1575173bda0a3dd2c24be9e6d696b09a54e19687))

* Added four more stations with trading information ([`234c6da`](https://github.com/eyeonus/Trade-Dangerous/commit/234c6dab938b1f0ae3f1c5c598ac245a1aba81ef))

* Added Beta 2 Stars ([`291249d`](https://github.com/eyeonus/Trade-Dangerous/commit/291249d421da520cb0775f8731b198a7d559c1ca))

* Added a bunch of new stations ([`d4d4863`](https://github.com/eyeonus/Trade-Dangerous/commit/d4d4863d2924b2c34b6561b1d78b1c568274efe5))

* Removed the EMDN module following Michael Brooke&#39;s post ([`d619523`](https://github.com/eyeonus/Trade-Dangerous/commit/d61952357a436560a36f8c8f46c3f096b510a576))

* Fix for TradeDB ignoring entries with a negative stock level (-1 is intended for &#39;unknown&#39;) ([`0025667`](https://github.com/eyeonus/Trade-Dangerous/commit/0025667667058b31cb55f82f8c7c4b274809057b))

* Made TradeDB also impose a locale, lets see how we like that. ([`adf5b38`](https://github.com/eyeonus/Trade-Dangerous/commit/adf5b38065bb19e81fc8e6978130fc6509220f4f))

* &#34;Whoopsie&#34; ([`66b4e38`](https://github.com/eyeonus/Trade-Dangerous/commit/66b4e38cc97382ca857a221c05a211227b2f1272))

* match stock/buying, demand/paying in forsale views ([`17e0046`](https://github.com/eyeonus/Trade-Dangerous/commit/17e0046bbc984ab956e9b190391c9c0e0259deba))

* Replaced &#39;getTrade&#39; with &#39;getTrades&#39; which now does what it describes. ([`c941e3e`](https://github.com/eyeonus/Trade-Dangerous/commit/c941e3eaa80a9e31d2f4a63330a439dec2879d90))

* Added some views for listing prices ([`a41b5e5`](https://github.com/eyeonus/Trade-Dangerous/commit/a41b5e561f1234d44a1bb1ed9d76a6cd364bc678))

* added lots of extra (level 9) verbosity debug messages to try and track down what&#39;s causing emdn-tap.py to hang sometimes. I suspect it&#39;s probably my home network crapping out and emdn-tap not noticing it. ([`5afedca`](https://github.com/eyeonus/Trade-Dangerous/commit/5afedca37b45d41a1836f4cbbe1502147fc1c6da))

* Fixed &#39;warning()&#39; in emdn-tap.py ([`1c92f55`](https://github.com/eyeonus/Trade-Dangerous/commit/1c92f5570019bcac5b7fab43d8831d77ee721afb))

* Fixed --seconds/--minutes in emdn-tap.py ([`024c518`](https://github.com/eyeonus/Trade-Dangerous/commit/024c51832e33ac0ce3e7876ebda79128e6feda55))

* Extra locations for hauler/sidewinder ([`fa513c9`](https://github.com/eyeonus/Trade-Dangerous/commit/fa513c9e3619e5c633dbc17026f8ceff6bf79988))

* Recent data ([`f4a4727`](https://github.com/eyeonus/Trade-Dangerous/commit/f4a47271b207f1689f4aa3d0b2081c2ad67b21d5))

* v3.9 with updated readme ([`936472b`](https://github.com/eyeonus/Trade-Dangerous/commit/936472bc3d2267c1633863e39966536a3a8ec7bf))

* Made &#39;nav&#39; use empty jump dist by default.

Added --full to use heavy distance instead. ([`0381921`](https://github.com/eyeonus/Trade-Dangerous/commit/0381921093d09c468d02e422c58cad6b89faddaf))

* Fix missing last via step in nav routes ([`52059c3`](https://github.com/eyeonus/Trade-Dangerous/commit/52059c3bdfbf823cc569e70b43463e1692f824d1))

* Much improved &#39;nav&#39; presentation options.

Default is slightly verbose, &#39;-v&#39; adds more info, &#39;-q&#39; takes more away.

Use &#39;-qq&#39; to just list the hops on the route. ([`09d9fb2`](https://github.com/eyeonus/Trade-Dangerous/commit/09d9fb2c0fe68f11e19282652a4f6168093007c2))

* Cleaned up presentation of &#39;cleanup&#39; command and made it support -q for ultra-quiet mode. ([`5c0d31e`](https://github.com/eyeonus/Trade-Dangerous/commit/5c0d31e11e30e3d5d84d3fdb853bc5ccf516dd22))

* Made &#39;--detail&#39; a common argument, added &#39;--quiet&#39; (-q)

Also tidied up how we present command line errors. ([`2d21b60`](https://github.com/eyeonus/Trade-Dangerous/commit/2d21b60b1025e3afd355d2fcf36c0ca445e64ddd))

* Check --minutes before claiming to take any action ([`a4c73da`](https://github.com/eyeonus/Trade-Dangerous/commit/a4c73dafb2dc44d5965ecedd9d6c6435676c0e8a))

* Improvements to &#39;nav&#39; command ([`09c953d`](https://github.com/eyeonus/Trade-Dangerous/commit/09c953dd196063870893f4d2f2018aa03e6803bc))

* Better presentation of price fluctuations in emdn-tap ([`cfb5b93`](https://github.com/eyeonus/Trade-Dangerous/commit/cfb5b938634f624ae888d2c93a1d5f81de7d1346))

* Adding &#39;nav&#39; command for plotting a route between two systems ([`09340f2`](https://github.com/eyeonus/Trade-Dangerous/commit/09340f23ffb5c2ab11b25af48b6049a5b76fe03c))

* Unbreak --via ([`a41a2e5`](https://github.com/eyeonus/Trade-Dangerous/commit/a41a2e529185751caa6fd5f77976f5374565211b))

* Presentation cleanup

Normalized str() and name() across station and system etc but I don&#39;t know that I like what they do; I think str() should probably be the fancy version (so that print(station) does the right thing) and name() returns just the dbname. But if I do that, there&#39;s not so much point in hiding dbname, is there? ([`8fedf3f`](https://github.com/eyeonus/Trade-Dangerous/commit/8fedf3f4a77b162c96cf4f1c6d52b1285726d2db))

* Updated prices - I have to stop doing this :) ([`22d141f`](https://github.com/eyeonus/Trade-Dangerous/commit/22d141f47edff7e379b626a35e4ee96f4d505a89))

* Version 3.8 README ([`677c3b4`](https://github.com/eyeonus/Trade-Dangerous/commit/677c3b47606259e3ef4e8032c3d3e0bcb56d046e))

* Fix for issue #7: --avoid doesn&#39;t handle systems with no stations.

Added TradeDB.lookupStationExplicitly which only tries to resolve a station name.
Added SystemNotStationError so that lookupStation can indicate that it found a matching system but could not reduce it to a station (len(system.stations) != 1). ([`37632c1`](https://github.com/eyeonus/Trade-Dangerous/commit/37632c1053577280a89db472c00fbf41b93b5b30))

* Also show price changes in emdn-tap.py, starting with -v ([`e278616`](https://github.com/eyeonus/Trade-Dangerous/commit/e278616699ed8986665febdbe6a314a246638488))

* Extra help ([`3eddcf5`](https://github.com/eyeonus/Trade-Dangerous/commit/3eddcf5796410e9c872ffdb74d3fe1c921f083c0))

* Put a slash between system and station when combining them as a name ([`8c1dad0`](https://github.com/eyeonus/Trade-Dangerous/commit/8c1dad0501aaa77b20ec819f7aa767af093dcc72))

* Actually, in 3.4 namedtuple uses __slots__ ([`17c6d6e`](https://github.com/eyeonus/Trade-Dangerous/commit/17c6d6e43a9e23c9ecedd01e386bed40f793363b))

* &#39;unspecified hops&#39; line was intended to be debugging ([`5e38b2e`](https://github.com/eyeonus/Trade-Dangerous/commit/5e38b2ed32200d5cde1d611fa3ea4116ffa63dd2))

* Ignore &#39;market&#39; directory (for now) ([`eecabdf`](https://github.com/eyeonus/Trade-Dangerous/commit/eecabdf90ac2c3e8c5464ac4d6ae5f82c054443c))

* Minor code cleanup ([`0385ed7`](https://github.com/eyeonus/Trade-Dangerous/commit/0385ed7fa193cb00b698b011d49fbc63dc5f51ee))

* Unused variable ([`350d832`](https://github.com/eyeonus/Trade-Dangerous/commit/350d83213b70454636eefca21335583f08daa8ee))

* v3.7 Added &#34;cleanup&#34; command to trade.py to prune dead records. ([`3bf6465`](https://github.com/eyeonus/Trade-Dangerous/commit/3bf64653db3e37ac049df89c95dfb0497f35da4f))

* emdn-tap now tries harder to honor --commit intervals ([`4ccd5db`](https://github.com/eyeonus/Trade-Dangerous/commit/4ccd5dbddbd257550fa3fbffe5c7b52f49d98086))

* Fix for excessive CPU usage in emdn-tap.py

pyzmq.poll wants &#39;None&#39; rather than &#39;0&#39; for &#39;until something happens&#39; ([`ca763a8`](https://github.com/eyeonus/Trade-Dangerous/commit/ca763a875ca03b35dceae2a34b48315a6da1026e))

* Data updates ([`5642267`](https://github.com/eyeonus/Trade-Dangerous/commit/56422671c9a0810476592c96e9ef4256d5a21680))

* Updated README ([`a4cae4d`](https://github.com/eyeonus/Trade-Dangerous/commit/a4cae4debe635000fbb4f76ce67a2fcc4876525f))

* Further price drill ([`866643d`](https://github.com/eyeonus/Trade-Dangerous/commit/866643d26d5c969bb46438584a10dcc3ebbf31e7))

* When stock numbers are available (&gt;= 0) use the stock levels to cap purchase quantities ([`2458f4a`](https://github.com/eyeonus/Trade-Dangerous/commit/2458f4ad9cb53ac2a2421f567e544bcf197efdd4))

* Load stock levels from the database and their age ([`8e925fe`](https://github.com/eyeonus/Trade-Dangerous/commit/8e925fe0215380fc45c757599388315576e80500))

* Fix: It was possible for TD to accept an empty cargo load as an option by mistake. ([`1f76202`](https://github.com/eyeonus/Trade-Dangerous/commit/1f762021af8c31c4799e57013fcc91a11f31376a))

* Cosmetic code cleanup ([`f3ee1bf`](https://github.com/eyeonus/Trade-Dangerous/commit/f3ee1bf959f2d0001cb34c547d80a45f5454b375))

* Improved warnings system in emdn-tap ([`b948335`](https://github.com/eyeonus/Trade-Dangerous/commit/b94833522de5fbb8adca32c6a7fe82cf9c085c40))

* Rid of more dead prices ([`8ad1505`](https://github.com/eyeonus/Trade-Dangerous/commit/8ad15055467eb9f6969a006847dea718d8d17f32))

* Long data trawl ([`cb78d77`](https://github.com/eyeonus/Trade-Dangerous/commit/cb78d77883c0331ff381158c1158431b861e7152))

* overnight ([`ddbb92b`](https://github.com/eyeonus/Trade-Dangerous/commit/ddbb92b042529e3ead8e73a7ee7649b5479b4999))

* Use __slots__ where possible ([`3f229bd`](https://github.com/eyeonus/Trade-Dangerous/commit/3f229bd68b6b8d5159ce30f1b6934cc49a3ab61c))

* One last clean for tonight ([`18775f0`](https://github.com/eyeonus/Trade-Dangerous/commit/18775f00cd00c3c6553c3c85f8630fad9ca512f1))

* removed some dead entries ([`f6f5260`](https://github.com/eyeonus/Trade-Dangerous/commit/f6f52605a06170df0eec22be2c04c75c43ce2c4f))

* support for demand/stock levels in emdn data and weeding out fake entries caused by the way UI shows mission items ([`80f185e`](https://github.com/eyeonus/Trade-Dangerous/commit/80f185e1a6e0542fa40e7bdd3c682dde23bb24f7))

* Added rows for demand/stock and level columns to prices ([`c3bd869`](https://github.com/eyeonus/Trade-Dangerous/commit/c3bd8698a6976345bbd1dd91ea7c8f0de1850d92))

* Made it possible to redirect warnings to a file (--warnings-to) in emdn-tap ([`4b4bf28`](https://github.com/eyeonus/Trade-Dangerous/commit/4b4bf282f0d1e1b0bc1060dae15075145e2456db))

* Cleanup of stale prices ([`eb82de5`](https://github.com/eyeonus/Trade-Dangerous/commit/eb82de530a620c26ec06554b8bcfb00a248cccb8))

* Price corrections ([`ef6d76e`](https://github.com/eyeonus/Trade-Dangerous/commit/ef6d76e2bc3f0d016da437c665a0dba712a1b9d5))

* Days data ([`dc72422`](https://github.com/eyeonus/Trade-Dangerous/commit/dc72422aee0f1a4731660d9614129045922e4e98))

* Don&#39;t barf on black market items and display cleanup ([`47f2be4`](https://github.com/eyeonus/Trade-Dangerous/commit/47f2be470283b31026f40619280f0780a8aeac63))

* Price updates ([`afa46e9`](https://github.com/eyeonus/Trade-Dangerous/commit/afa46e99864dd09a3e0bab58987d7e75018ecbe7))

* v3.5 Converted EMDN Tap to use compressed JSON stream. ([`34de92d`](https://github.com/eyeonus/Trade-Dangerous/commit/34de92da7ef2a076a305dea5bf1386392ca887bf))

* nightly data update ([`7ebea7f`](https://github.com/eyeonus/Trade-Dangerous/commit/7ebea7f038d55d8c1c77d9534cb7b277ae6fa1c2))

* Always display what we&#39;re doing regardless of verbosity, don&#39;t need to behave like an old unix tool right now ([`4230012`](https://github.com/eyeonus/Trade-Dangerous/commit/423001210530546f3800292620ae93775a59a1ad))

* Price catchup ([`2275447`](https://github.com/eyeonus/Trade-Dangerous/commit/22754473eec166ebf40280c722d284ac3dac19b1))

* Ok, auto-commit should be on by default. ([`93f154f`](https://github.com/eyeonus/Trade-Dangerous/commit/93f154fbc7086e889385f3d8578dd814a80c6170))

* v3.4 emdn-tap.py and multiple vias

- emdn-tap.py pulls prices from the EMDN network to update the price database,
- You can now list multiple --via destinations, e.g. &#34;--via aulin --via chango,freeport&#34; ([`b742ac5`](https://github.com/eyeonus/Trade-Dangerous/commit/b742ac596903709d14f8d8a8f4c7359a67f45d3a))

* minor code cleanup ([`a65e2d9`](https://github.com/eyeonus/Trade-Dangerous/commit/a65e2d9e994210b86f60a559a7848b6d9dc1e6a0))

* Cleaner error message when X52 is requested but not found ([`1b9a50a`](https://github.com/eyeonus/Trade-Dangerous/commit/1b9a50a5014ffdde509a1689b494cbf894a78e99))

* Overnight update of prices ([`c7713c8`](https://github.com/eyeonus/Trade-Dangerous/commit/c7713c8d0a571fe41ae5eaae917dc13c0a5db86e))

* Updated data ([`869c5f5`](https://github.com/eyeonus/Trade-Dangerous/commit/869c5f5fea56775ec85513a4f9a0d8124182fc99))

* Cleaned up ships.py ([`a5529f9`](https://github.com/eyeonus/Trade-Dangerous/commit/a5529f997cc0bb5ec83fa9e397c70d3dbba93848))

* API: Added views for finding older Price data in the database ([`740f19e`](https://github.com/eyeonus/Trade-Dangerous/commit/740f19e764b3a2d4f20006938270a26e4657de42))

* Ignore the journal, the journal is a lie. ([`873133a`](https://github.com/eyeonus/Trade-Dangerous/commit/873133a0a6d25b49566897d13cee0f20f9bf4d49))

* Firehose.read had lost its ability to be non-blocking. Now it found it, and you won&#39;t believe where it stuck it! ([`214e91d`](https://github.com/eyeonus/Trade-Dangerous/commit/214e91ddd96c79474f7bc4c7920fba3f37d6e3e5))

* Prices updated from EMDN ([`072f1b4`](https://github.com/eyeonus/Trade-Dangerous/commit/072f1b4a0346b1ee205c7f1911b7b4fddae78bc2))

* lookupStation will now take a system in which to search for said station ([`e4ba25e`](https://github.com/eyeonus/Trade-Dangerous/commit/e4ba25e5362f467ae0cae6662e3eb18a3ed90792))

* Fixed bug in lookupSystem ([`cab0110`](https://github.com/eyeonus/Trade-Dangerous/commit/cab01109d9e8a7ac5ad887eacb8c1a2ec5f81b4a))

* Fixed assorted station names, added Burbank Estate in Surya ([`a8eb94b`](https://github.com/eyeonus/Trade-Dangerous/commit/a8eb94b8294e630d65690ea305782bff84d78ccd))

* 20,000 lines of emdn sample data for testing ([`c7419eb`](https://github.com/eyeonus/Trade-Dangerous/commit/c7419eb1736b21926a8dcc65b747cf7753173d1b))

* script for capturing firehose data to a file ([`a14f1a3`](https://github.com/eyeonus/Trade-Dangerous/commit/a14f1a3b57634a989daf3c2d2a050fd82cea4a03))

* Fix for reading an empty string from the zmq firehose ([`e1b7c7a`](https://github.com/eyeonus/Trade-Dangerous/commit/e1b7c7a59bd188ea9b2b995a09203e009e64844a))

* Added file:/// uris for EMDN module ([`9627651`](https://github.com/eyeonus/Trade-Dangerous/commit/9627651cc5db3eaccad78b16bb026a92adf4d7f1))

* Reprt for Item ([`a4401ce`](https://github.com/eyeonus/Trade-Dangerous/commit/a4401ce9e8ea92478303778c60b1aa2a03d08de0))

* Updated README ([`3b305a6`](https://github.com/eyeonus/Trade-Dangerous/commit/3b305a65b4bcaf698681216371ecb6cce94f394e))

* Fix bug where two matches on the same object introduced an ambiguity

e.g. &#34;furnaces&#34; matched both &#34;hel-static furnaces&#34; and &#34;helio static furnaces&#34; ([`1df90f9`](https://github.com/eyeonus/Trade-Dangerous/commit/1df90f936442e7c20b97c2abb62bf343b1f3e79c))

* Added item aliases so that items can be looked up by the game&#39;s internal name for them.

e.g. &#34;helio static furnaces&#34;, &#34;helstaticf&#34; or &#34;furnaces&#34; all find the same thing.

Also did assorted cleanup on code:
 - order of definitions in tradedb.py,
 - Item is no-longer a namedtuple (fixed several cases where I was relying on the tuple behavior),
 - Fixed up several repr() implementations now that I know what repr is actually for,
 - Station.addTrade no-longer creates a dependency on Trade... ([`0927394`](https://github.com/eyeonus/Trade-Dangerous/commit/092739476adc6eaf8be82c66d1689ccb289f92a8))

* Added a &#39;val&#39; argument to listSearch

This allows you to pass dict.items(), e.g.: listSearch(&#39;Foo&#39;, &#39;bar&#39;, foo.items(), key=lambda kv: kv[0], val=lambda kv: kv[1]) ([`f4173b9`](https://github.com/eyeonus/Trade-Dangerous/commit/f4173b981443ed94010221cf44715cf7dc0c612a))

* Display names rather than objects when displaying the avoids list ([`91ff5fe`](https://github.com/eyeonus/Trade-Dangerous/commit/91ff5fea522f7ebfe4bfdd14d65fb70b37dfb438))

* Added a table with alternate item names so you can map Display &lt;-&gt; Game names for items ([`e0ea8a1`](https://github.com/eyeonus/Trade-Dangerous/commit/e0ea8a1f49ed72499577a462ac8520fc0463c08c))

* Better examples in the emdn.README ([`cb991ad`](https://github.com/eyeonus/Trade-Dangerous/commit/cb991ad3ceec937bce88e4ff9d28fc893e41aed3))

* Better examples in the emdn.README ([`b2cb3e3`](https://github.com/eyeonus/Trade-Dangerous/commit/b2cb3e3459c6a0c458c1a73cdc772218a0fc8d06))

* Improved emdn.ItemRecord docstring ([`d60b1bc`](https://github.com/eyeonus/Trade-Dangerous/commit/d60b1bcb09d4e05534a1d4e66ae3b0a456327470))

* Added examples to EMDN readme ([`469b5b8`](https://github.com/eyeonus/Trade-Dangerous/commit/469b5b86a2ed0a2bd488a273cbf25bb4b3bc0864))

* Created a python module for accessing Elite-Market-Data.net ([`f652f56`](https://github.com/eyeonus/Trade-Dangerous/commit/f652f56d8e87db8f8d6fe10e9854ef7316636124))

* Added category/metal nomenclature for avoiding items that appear in two category headings. e.g. --avoid metals/gold or --avoid gold ([`4a11dac`](https://github.com/eyeonus/Trade-Dangerous/commit/4a11dac7cebdd781f85a39417ff9dac5284d3dcd))

* Updated readme to 3.2 ([`da79ad7`](https://github.com/eyeonus/Trade-Dangerous/commit/da79ad78b8e2515913a6045b84aa949e0da4fcf9))

* Made it so you can list avoidances in a comma-separated list, e.g. --avoid chango,gold,anderson ([`49fffad`](https://github.com/eyeonus/Trade-Dangerous/commit/49fffadf43665543e7d55b62d8b6efed0624473d))

* Fix for file not found error when running without arguments ([`f46619c`](https://github.com/eyeonus/Trade-Dangerous/commit/f46619cb6ce9115da2ff3fba1c0d2c7d76cee494))

* Cleaning up how we build the argument lists.

Working on several new commands, it was getting tricky to add the new arguments and keep things consistent, so I added some wrapper classes to help make that easier to do while retaining as much of the original syntax as possible. ([`298942d`](https://github.com/eyeonus/Trade-Dangerous/commit/298942d6841a519dd0c42eb519f547ba4d581a41))

* Updated price data ([`3850db2`](https://github.com/eyeonus/Trade-Dangerous/commit/3850db24791e3dbee825102a15ad58dbd7c9db93))

* don&#39;t keep the database connection around unless we have to ([`dcc569d`](https://github.com/eyeonus/Trade-Dangerous/commit/dcc569d452484609f5142bce3209221e71716971))

* Made invocation string a debug line again ([`dbf7587`](https://github.com/eyeonus/Trade-Dangerous/commit/dbf7587b9108b6714897cd0addc61a6d9c240f2e))

* Unbroke sub-editor modes ([`cd3bc18`](https://github.com/eyeonus/Trade-Dangerous/commit/cd3bc1875fbf9f79a9b6aef74280c14761d77a16))

* Cosmetic internal change to simplify multiple editor options in future ([`226bc99`](https://github.com/eyeonus/Trade-Dangerous/commit/226bc99eb19002276af42d182cb334f128c84b12))

* Corrected Bradfield Orbital&#39;s name ([`6864fbc`](https://github.com/eyeonus/Trade-Dangerous/commit/6864fbcc9d70f2b0dab57fe87c9ff60f22b97130))

* Added modified times to .prices files and cache parser ([`06ee588`](https://github.com/eyeonus/Trade-Dangerous/commit/06ee5884a5df3f3dbb6cb0e211cd4738ccb20c5e))

* Updated abnett ([`31d03f1`](https://github.com/eyeonus/Trade-Dangerous/commit/31d03f1f8d80c4983a4797e6acb2158ef74dd0cb))

* code clenaup ([`f00e7a2`](https://github.com/eyeonus/Trade-Dangerous/commit/f00e7a21a4405be5dd5ae03ef3b83aa89e9d4660))

* Missing line between summary and detail ([`d3ffedc`](https://github.com/eyeonus/Trade-Dangerous/commit/d3ffedc25bd7059ef523f8740bd269ad7a7bb774))

* Fix for avoiding stations not working ([`f5383ab`](https://github.com/eyeonus/Trade-Dangerous/commit/f5383abb2a64ffa84ffa29db114b4897ab6e9bc7))

* Additional debug output ([`1251d01`](https://github.com/eyeonus/Trade-Dangerous/commit/1251d0120dcf4fcfbc46405e7afaf5b462760587))

* v3.1 Multiple Command mode and Update mode.

TradeDangerous now supports multiple &#39;commands&#39;, currently &#39;run&#39; and &#39;update&#39;. Run does what pre-3.1 trade.py used to do. Update provides a way for you to edit data.

  ./trade.py update aulin

will walk you through the prices at aulin (not implemented yet)

  ./trade.py --subl update aulin

will launch Sublime Text 3 (if installed) to edit a .prices list of aulin

  ./trade.py --notepad update aulin

will launch notepad to edit a .prices list for aulin

  ./trade.py --editor foo.exe update aulin

will use &#39;foo.exe&#39; as the editor. ([`6a2f0e2`](https://github.com/eyeonus/Trade-Dangerous/commit/6a2f0e26d3249bd02234a9fef56671c4430b52b6))

* Moved buildcache.py into data ([`65ecb86`](https://github.com/eyeonus/Trade-Dangerous/commit/65ecb86ce3fc28146eeaff3faf91462580a52d65))

* Cosmetic ([`aca7987`](https://github.com/eyeonus/Trade-Dangerous/commit/aca7987b60534087bfeaf9f05ce836ebed8cfd63))

* Cosmetic ([`180138c`](https://github.com/eyeonus/Trade-Dangerous/commit/180138c0b3891182d8bf8cde89a82bd8772c50e1))

* Unused imports ([`870836e`](https://github.com/eyeonus/Trade-Dangerous/commit/870836e6de131bc5ea45f91659c595b698b165a3))

* More saitek cleanup ([`cb51e30`](https://github.com/eyeonus/Trade-Dangerous/commit/cb51e307ad44178cebe37c797380e658695d5a1a))

* Cleaned up the MFD/Saitek directories. Cleaned up the Saitek X52 wrapper to verify that it&#39;s actually saitek&#39;s driver that&#39;s broken and not the wrapper.
You can confirm this by going to C:\Program Files\Saitek\DirectOutput\SDK\Examples\Test\ and running test.exe.
Double click the line for X52Pro, you should see a window that lets you poke with the MFD. Try pressing one of the soft buttons (the pg wheel or the reset button). And the &#39;buttons&#39; display in test.exe never changes.
WTG Saitek. ([`eebeab6`](https://github.com/eyeonus/Trade-Dangerous/commit/eebeab6b11aa5c447f38890c3d670b1881aed939))

* Xiaoguan prices ([`42edb72`](https://github.com/eyeonus/Trade-Dangerous/commit/42edb727ea1de42b1460cdff58e312ed5f8bffe1))

* Fixed Xiaoguan Hub name ([`2ae353c`](https://github.com/eyeonus/Trade-Dangerous/commit/2ae353c89bd2b034b9e1e33d0277824f91bd495c))

* Fixed error with MFD on termination ([`5ce9d57`](https://github.com/eyeonus/Trade-Dangerous/commit/5ce9d576ed09aee9480a6c976c3fc9fcaebccfa5))

* v3.0 -- Trade Dangerous now uses an SQLite database instead of a Microsoft Access Database. See data/TradeDangerous.prices if you want to edit prices.

Merge branch &#39;sqlite&#39;

Conflicts:
	TradeDangerous.accdb
	trade.py
	tradedb.py ([`752a511`](https://github.com/eyeonus/Trade-Dangerous/commit/752a511d7fc39d5ad3f336269460538e6ff1d09b))

* Minor cleanup ([`6436480`](https://github.com/eyeonus/Trade-Dangerous/commit/64364805ca7b60f9990ccee2d21e0f868e812875))

* Show --detail and --debug instead of -v and -w ([`c614742`](https://github.com/eyeonus/Trade-Dangerous/commit/c614742b97491d1ec4f35044be42de090f21fa63))

* Cleaned up argument list ordering for --help ([`7330c68`](https://github.com/eyeonus/Trade-Dangerous/commit/7330c68aa90c09857741ee736902ec104a20beb9))

* 3.0alpha -- First version of 3.0 that I hope is fully working.
- Data is now sourced from data/TradeDangerous.sql and data/TradeDangerous.prices
- Processed data is stored into an SQlite db as a cache: data/TradeDangerous.db
- On startup, if the .sql or .prices files are more recent than the .db file, we rebuild the .db
- Normalized function names, copyrights, etc
- Cleaned up lots of comments and documentation,
- Renamed the &#34;getSystem&#34;, &#34;getStation&#34; etc functions to &#34;lookupSystem&#34;,
- Provided TradeDB accessors for systems, stations and items: tdb.stations()
Lots of other changes. ([`e5a424d`](https://github.com/eyeonus/Trade-Dangerous/commit/e5a424d159a308296e4317e3151682c9d45f1606))

* Removed ui order column from .prices data; it&#39;s redundant. use the line order instead... duh ([`6335276`](https://github.com/eyeonus/Trade-Dangerous/commit/63352769a07e246fa7243bb8f1065d4b53500a25))

* Initial version of the .prices loader ([`1e9a36d`](https://github.com/eyeonus/Trade-Dangerous/commit/1e9a36d512f86712c555ab4d2ec06a98be4a518c))

* Don&#39;t output UI Order into .prices file ([`94b2ea7`](https://github.com/eyeonus/Trade-Dangerous/commit/94b2ea7cb131832d8d929007b958d82e32bbb5e6))

* On the way to supporting the SQLite DB as a cache for text-based source data. Next step is to make tradedb check if the SQLite file exists or is out of date and re-generate it, if it can. ([`f08de3e`](https://github.com/eyeonus/Trade-Dangerous/commit/f08de3e6ebf250ed74b84e57bad677fa27bff8fe))

* Removing the view ([`ffe4029`](https://github.com/eyeonus/Trade-Dangerous/commit/ffe4029ab253fc2fa8fb82f210b14e4bb9902c76))

* Indentation failure, now fixed ([`a2fc0b7`](https://github.com/eyeonus/Trade-Dangerous/commit/a2fc0b74d02e590a26405d4283e4c0d5dd7ce88a))

* First workable version of SQLite database implementation ([`efcf1c4`](https://github.com/eyeonus/Trade-Dangerous/commit/efcf1c4270874571055bd321f0f11188118fb892))

* Assorted runtime fixes introduced in conversion ([`42413d1`](https://github.com/eyeonus/Trade-Dangerous/commit/42413d1a281251df3d4a5ec59589d84c1b63eff2))

* Price corrections ([`c752fd9`](https://github.com/eyeonus/Trade-Dangerous/commit/c752fd944fdee407b71fd09d116fb489e072a73d))

* Big push towards the sqlite conversion ([`de08492`](https://github.com/eyeonus/Trade-Dangerous/commit/de084922352a95851b1416464f28d7c2aa301d14))

* Changed the sq3 file name to TradeDangerous.sq3 ([`13e6906`](https://github.com/eyeonus/Trade-Dangerous/commit/13e690639c22578aadd19500c8a9475e52eef952))

* Debug formatting change, meh ([`7ae3458`](https://github.com/eyeonus/Trade-Dangerous/commit/7ae34582c0198465f786330dd88df0b4e7544fc7))

* [BROKEN] Work in progress adaptation of tradedb to use the new sq3 format. ([`d5be7c8`](https://github.com/eyeonus/Trade-Dangerous/commit/d5be7c8e12b92b7444b21445ad80c5ad4387b00a))

* Test loading link data from the sq3 file and see how it performs. ([`ec79a3a`](https://github.com/eyeonus/Trade-Dangerous/commit/ec79a3a94e162b2170c1aede972815655920bb2d))

* Populate prices table ([`7cca7bf`](https://github.com/eyeonus/Trade-Dangerous/commit/7cca7bf28f82b8f21efc0bcc32ac1a977e0e7851))

* tell sqlite about calc_distance_sq function ([`3809571`](https://github.com/eyeonus/Trade-Dangerous/commit/3809571e94b209f5feb38c12c121bfc0b1651b3e))

* debug annotations ([`2700bd6`](https://github.com/eyeonus/Trade-Dangerous/commit/2700bd63d49181f0431b12b97232c57380274a42))

* Track systems by their new system ID for later lookups ([`9f3b1ef`](https://github.com/eyeonus/Trade-Dangerous/commit/9f3b1ef76f882be51fc33eed713d9e318ed5681c))

* debug_log helper ([`b56fc86`](https://github.com/eyeonus/Trade-Dangerous/commit/b56fc8673c685ec763f13e4b9507bc21b262728a))

* Ignore fake stations we&#39;re supposed to be ignoring ([`3550c06`](https://github.com/eyeonus/Trade-Dangerous/commit/3550c06e84ca3fa6747f95eda89fad9a5c6a36ec))

* Track the maximum distance any ship can jump during import ([`b2b3972`](https://github.com/eyeonus/Trade-Dangerous/commit/b2b3972151cff35bc18d0f1476d6f4233237c5a2))

* Added an SQL View for calculating links between stars ([`0185c28`](https://github.com/eyeonus/Trade-Dangerous/commit/0185c28ecf9353a0cbd04f2d6c8347f1c3a1e6d9))

* System was describing itself as Station ([`08b7c23`](https://github.com/eyeonus/Trade-Dangerous/commit/08b7c2385603cd90f0adeb966a29731c62f0142a))

* Fix for wrong stationID mapping during import. ([`5d3260a`](https://github.com/eyeonus/Trade-Dangerous/commit/5d3260ae664d3930393a52861a004a865e954622))

* Hopefully more meaningful names for the sell/buy columns in the Price table. ([`2f23dc9`](https://github.com/eyeonus/Trade-Dangerous/commit/2f23dc9c61be2d07af5dd5124c069ea9fb16129c))

* Added static getDistanceSq to TradeDB ([`3d969f8`](https://github.com/eyeonus/Trade-Dangerous/commit/3d969f8a8e8032c40d17fd05891fac31d4bc56d6))

* Populate item table with dbimport ([`600a0c0`](https://github.com/eyeonus/Trade-Dangerous/commit/600a0c06cec2abc407760e11a855eedb687b62de))

* Populate category table with dbimport ([`9c6ad50`](https://github.com/eyeonus/Trade-Dangerous/commit/9c6ad50c8b73576a8acebaccefcc127dae2a36de))

* Added placeholders for Update and UpgradeVendor to dbimport ([`437ef70`](https://github.com/eyeonus/Trade-Dangerous/commit/437ef7036d4dadca2b05787a9226e09d3943798c))

* dbimport presentation and no-op support ([`2124b16`](https://github.com/eyeonus/Trade-Dangerous/commit/2124b160691dd4070e6790ef9a13731bcc127126))

* dbimport now populates System, Station, Ship and ShipVendor ([`d9b7f1a`](https://github.com/eyeonus/Trade-Dangerous/commit/d9b7f1a2d7951d7c370d39dc812081c274a34236))

* TradeDB cleanup

Docnote and comment cleanup, made normalized_str and list_search static methods ([`926c8cc`](https://github.com/eyeonus/Trade-Dangerous/commit/926c8cc3a07c6858fed81f47e080503f278fc34f))

* Missing import for ships.py ([`64f63eb`](https://github.com/eyeonus/Trade-Dangerous/commit/64f63ebc7b3bf3b3fa30935594a3c60bc1a81143))

* Made SQ3 table names singular so that statements read a little better:
  SELECT Ship.name FROM Ship where Ship.ID = 5
etc ([`3d508f8`](https://github.com/eyeonus/Trade-Dangerous/commit/3d508f83e370da3e9d225490a35f1bb3fdeeb35e))

* Import script to build an SQ3 db from scratch along with data from an ACCDB ([`41b85fb`](https://github.com/eyeonus/Trade-Dangerous/commit/41b85fbc3cec0434553213613e61138404afd6f9))

* Table of stars ([`a2631c5`](https://github.com/eyeonus/Trade-Dangerous/commit/a2631c5903410d460ba7b3363a91bf6c5fe822e3))

* Moved dbdef.sql to dataseed ([`b2ff13c`](https://github.com/eyeonus/Trade-Dangerous/commit/b2ff13c39bfb12c7e4324c632c9c8ec19b8d215e))

* Added ships source table and expanded the list of fields ([`cc986d9`](https://github.com/eyeonus/Trade-Dangerous/commit/cc986d93c1d0fe6e1f833a5a174979f67d9cae89))

* Cleaned up the dbdef ([`dd4ca0e`](https://github.com/eyeonus/Trade-Dangerous/commit/dd4ca0e7aba83d2a34c7d4ae1fedbee64438311a))

* Make x52 initialization errors clearer ([`7c637f0`](https://github.com/eyeonus/Trade-Dangerous/commit/7c637f07e1e77eb7a139911ef5fe68042cfc3b8c))

* Cleanup ([`6623d74`](https://github.com/eyeonus/Trade-Dangerous/commit/6623d740b0a29a8616c8eb1eaa4b38606fe9e4e8))

* dbsource.sql -&gt; dbdef.sql because it&#39;s definition not data ([`be351af`](https://github.com/eyeonus/Trade-Dangerous/commit/be351af3f08e2d4b14fce4dec16d555da3c74df8))

* Now with functional SQL ([`582e0d9`](https://github.com/eyeonus/Trade-Dangerous/commit/582e0d9eb45eda783fae97dd0d611748ec8f1bca))

* Better layout of the mfd - not wasting an entire line on the step/hop no. ([`a45b2d6`](https://github.com/eyeonus/Trade-Dangerous/commit/a45b2d6899efbc2838fdb863354e6b296d412c59))

* Added &#39;attention&#39; method to MFDs for drawing the users attention to the device.

Because who doesn&#39;t want their X52 to flash at them? ([`0e6c71c`](https://github.com/eyeonus/Trade-Dangerous/commit/0e6c71ccfb818f41d212154f521051b72afea6c6))

* Added more stations to ship locations ([`e6f8141`](https://github.com/eyeonus/Trade-Dangerous/commit/e6f81413a19da36f5e8c57be4fbc96a29b4cb0f4))

* Prices ([`391ab65`](https://github.com/eyeonus/Trade-Dangerous/commit/391ab65e2cf7fdef8df6519b2728258d177550e2))

* initial database script ([`d52761b`](https://github.com/eyeonus/Trade-Dangerous/commit/d52761b54ac4c0060f91d484db2c55b0306f7706))

* Fixed README and capacity defaulting to 4 even with a --ship ([`ed5b35a`](https://github.com/eyeonus/Trade-Dangerous/commit/ed5b35a1192c14c744a327e8d580abdfd10f462e))

* Fix for occasional backtrace during shutdown ([`249fbb2`](https://github.com/eyeonus/Trade-Dangerous/commit/249fbb28106c6d9ba7bedd4818d81e55c1f13ff0))

* Make cli avg/bestCost/Sale a little more readable ([`1586e00`](https://github.com/eyeonus/Trade-Dangerous/commit/1586e00ab735549e516fbbaa0b889f33fc7c1997))

* Same applied to avgPrice (-&gt; avgSale). Also added avgCost and bestCost ([`d8fc110`](https://github.com/eyeonus/Trade-Dangerous/commit/d8fc11079977a245fe412e656e5db9a81ac521b8))

* Ok, bestPrice was a lousy name, bestSale is better. ([`8f0a19c`](https://github.com/eyeonus/Trade-Dangerous/commit/8f0a19c11070721e523cbd39477258a4b6092f7e))

* added avgPrice and bestPrice functions to cli.py ([`b89c52d`](https://github.com/eyeonus/Trade-Dangerous/commit/b89c52d60604a2793ac15edcb351cf0c683369e5))

* Added station list to ships ([`3b2a0d1`](https://github.com/eyeonus/Trade-Dangerous/commit/3b2a0d1a8abf06e1b97cf1e41b76f10cb3f5cb0b))

* Removed --jump to make abbreviations more obvious. ([`b54b9fa`](https://github.com/eyeonus/Trade-Dangerous/commit/b54b9fa6a80f045bd24f276c253fdb0faa97897c))

* Version 2.09 ([`278eff1`](https://github.com/eyeonus/Trade-Dangerous/commit/278eff193cee5dfb5b1f16aa3d29ad74863edb8e))

* Latest price updates (Aulin, Eranin, Chango, Freeport) ([`15c3e2b`](https://github.com/eyeonus/Trade-Dangerous/commit/15c3e2b2741d473c8a00f30ff5ef9bfe172b9f6a))

* Error handling cleanup #2

Made the argument parsing throw CommandLineErrors so that it&#39;s easier for non-programmers to understand WTF JUST WENT WRONG. ([`eb5a465`](https://github.com/eyeonus/Trade-Dangerous/commit/eb5a465428a01ee1d53d6f1bf5d5f98606c2bc2e))

* Default --ly-per and --capacity to ship but allow user overrides

Previously, --ship and --capacity/--ly-per were mutually exclusive. Now you can use --ship to fill out fields but make corrections, e.g. &#34;--ship sidewinder --capacity 2&#34; ([`56ddb15`](https://github.com/eyeonus/Trade-Dangerous/commit/56ddb15a875d7f6995b96d8fc840d9e52f7ed513))

* Error handling cleanup #1

Added CommandLineError exception type
Added catch for CommandLineError and AmbiguityError that turns them into simple error messages rather than backtraces. ([`a50549a`](https://github.com/eyeonus/Trade-Dangerous/commit/a50549a33454625e2c9cb60fa0bf46853bf03a9c))

* Price update ([`00c8c70`](https://github.com/eyeonus/Trade-Dangerous/commit/00c8c70741dd0517e5cdae9eeaf4005b1f8ffeb1))

* Presentation tidy ([`7832506`](https://github.com/eyeonus/Trade-Dangerous/commit/7832506af88ca3bffbb52bf63304b06a20b1a4b2))

* Another pass of presentation. ([`81f343f`](https://github.com/eyeonus/Trade-Dangerous/commit/81f343f178bad65a14aa2fe26c3a47a3acef98d7))

* Comment cleanup ([`770ee80`](https://github.com/eyeonus/Trade-Dangerous/commit/770ee80da22ea64517bd2b699550fc5f630c66b1))

* Presentation pass.

Basic output is roughly the same, added more output with &#34;--detail&#34; and lots more output with &#34;--detail --detail&#34;, along with breaking the detail up onto additional lines with detail=2+ ([`4dedb27`](https://github.com/eyeonus/Trade-Dangerous/commit/4dedb27f20b5c478248b0d4dd97389c8128f6fd4))

* Added TradeDB.getTrade(srcStn, dstStn, item)

Returns the Trade, if one exists, describing a transaction between stations. ([`c06f94a`](https://github.com/eyeonus/Trade-Dangerous/commit/c06f94adb0c00e59d95f8e22d14a32bf316ca426))

* Added --ship argument

You can now tell TD what ship you have and it will fill out --ly-per and --capacity for you. This doesn&#39;t take into account the weight of extras you&#39;re carrying. ([`ed44b1a`](https://github.com/eyeonus/Trade-Dangerous/commit/ed44b1addddcab2c2ea71b24d2753c86d06ead63))

* Route detail/summary reporting

- &#39;-v&#39; as alias for --detail
- Moved the route summary report from the checklist system to TradeDB.Route.summary()
- Added credits/ton line
- Added additional detail to the detail report when detail &gt; 1 (i.e. --detail --detail)
- Include credits/ton for each hop in detail output ([`bba4434`](https://github.com/eyeonus/Trade-Dangerous/commit/bba443473d521481bae7d7d4de48f1dfb918432b))

* Made --debug and --detail counts rather than bools so you can do --detail --detail. ([`eaee908`](https://github.com/eyeonus/Trade-Dangerous/commit/eaee908c64018e637c8281ed4704deeee9328be2))

* Cleaned up how we do TradeDB startup, slightly faster. ([`78419e3`](https://github.com/eyeonus/Trade-Dangerous/commit/78419e351f0cc4d9a4014000ca30dc478a7b4c22))

* Gave TradeDB a way to lookup a ship by name: TradeDB.getShip(&#34;Type 9&#34;) ([`9e702bc`](https://github.com/eyeonus/Trade-Dangerous/commit/9e702bcbc6388579b2eae1641284048396b255d7))

* Add list of ship types with minor details to TradeDB base class (access as TradeDB.ships) ([`650570b`](https://github.com/eyeonus/Trade-Dangerous/commit/650570b5da36c31a52ea3109b764bf199bf888e7))

* Add Ship class to TradeDB ([`a830a66`](https://github.com/eyeonus/Trade-Dangerous/commit/a830a665f5d1b956f93c415616c4a2b83d9ad870))

* Removing blank lines ([`9ceba7e`](https://github.com/eyeonus/Trade-Dangerous/commit/9ceba7e5ceca8c57f7e967d6cc5512a624ebfcb7))

* TradeDB.list_search will now take a key= parameter so you can use non-trivial enumerables ([`1d5087d`](https://github.com/eyeonus/Trade-Dangerous/commit/1d5087d3e0fc3e439c5264c0abc92398da93242e))

* Updated prices ([`1d14a72`](https://github.com/eyeonus/Trade-Dangerous/commit/1d14a7286639f7aba7e10462bd3ba65c41bba995))

* Made it easier to trace what the saitek driver is doing ([`7c4967f`](https://github.com/eyeonus/Trade-Dangerous/commit/7c4967f0918eacd4c61af4359ef094adf6e48ec7))

* Pricing updates ([`9241a72`](https://github.com/eyeonus/Trade-Dangerous/commit/9241a7211ef6e7d9294f5fb8651587852c3edfce))

* More updated prices ([`f004e0c`](https://github.com/eyeonus/Trade-Dangerous/commit/f004e0c956d8f0e3b1157d53b9efcc6af455e259))

* Because it looks prettier there. ([`dbb428e`](https://github.com/eyeonus/Trade-Dangerous/commit/dbb428e114a6c48653dc1cd7c31eba1853466a37))

* Some fairly significant price adjustments ([`69701bd`](https://github.com/eyeonus/Trade-Dangerous/commit/69701bd5c8a099c5188271e71f5a57574b4bc6a1))

* Fix for X52 mfd ([`2cb1485`](https://github.com/eyeonus/Trade-Dangerous/commit/2cb148593edf49906f56b2ec2beb25ec5f6f7ed0))

* Ooops, indentation ([`387ae06`](https://github.com/eyeonus/Trade-Dangerous/commit/387ae06d7eb0ec18c29a33085e9598b659e12f06))

* Merge branch &#39;anothermindbomb/tradedangerous/master&#39;

Conflicts:
	trade.py ([`a9e9aec`](https://github.com/eyeonus/Trade-Dangerous/commit/a9e9aec13472a849cdd1b323934cdd79f4d2aefe))

* Cleanup ([`42bee80`](https://github.com/eyeonus/Trade-Dangerous/commit/42bee8075b815139145491e0609f509b8f2bcc04))

* Dead code ([`61f90a1`](https://github.com/eyeonus/Trade-Dangerous/commit/61f90a1432322ceaa4eab9aadbbc738dfd61bb62))

* Call mfd.display instead of .update ([`f8eee99`](https://github.com/eyeonus/Trade-Dangerous/commit/f8eee998671c9d2a771dfee2d68af634e50cad24))

* Normalized add_argument strings.

Since &#39;&#39; strings are faster than &#34;&#34;, and most of them were &#39;&#39;, I went with the apostrophe version. ([`c83588d`](https://github.com/eyeonus/Trade-Dangerous/commit/c83588d6b7b29a74cafa8fcbe3d289910ae16d1f))

* Cleaned up the MFD section. Should probably be moved to a separate module. ([`6c29b8c`](https://github.com/eyeonus/Trade-Dangerous/commit/6c29b8cd5286b562fd3feb8bbffd49b36c2d5d05))

* Import AmbiguityError into trade ([`f64fcef`](https://github.com/eyeonus/Trade-Dangerous/commit/f64fceff55d832b2bb6e3dd1dc1e2166adbd7c4b))

* Comments and readability for the fast_fit algorithm ([`bcc2fc6`](https://github.com/eyeonus/Trade-Dangerous/commit/bcc2fc6a7471883610c62ed2521b5cf0be086ccc))

* Added AmbiguityError exception class ([`61ab576`](https://github.com/eyeonus/Trade-Dangerous/commit/61ab5760f998d4f07af7a6fe6edc9b2f517a9d0b))

* Removed redefinition of emptyLoad ([`d043221`](https://github.com/eyeonus/Trade-Dangerous/commit/d043221e86084c0d820dd06ecc173cd6218e9b21))

* Orgnaise imports + comment. ([`0fecc9f`](https://github.com/eyeonus/Trade-Dangerous/commit/0fecc9f96750b218f945bd15a8261dd0f427998e))

* Remove a mixture of tabs and spaces.
Remove unnecessary trailing semi-colons ([`bcd4794`](https://github.com/eyeonus/Trade-Dangerous/commit/bcd4794095c6fa7f548f42ed03da626f04b9d399))

* Add a call to the superlass initiator when we init X52ProMFD

Change refresh() to refer to self.page_id rather than just page_id.
Please note I cannot test this, as my X52 is still in a warehouse
somewhere. ([`3b155b0`](https://github.com/eyeonus/Trade-Dangerous/commit/3b155b02b7d76cfc5214cba34f2905f169d8a3d0))

* Add a call to the superlass initiator when we init X52ProMFD

Change refresh() to refer to self.page_id rather than just page_id.
Please note I cannot test this, as my X52 is still in a warehouse
somewhere. ([`b5196a8`](https://github.com/eyeonus/Trade-Dangerous/commit/b5196a89c8ab78165b9764ec6d6d802ee41ef726))

* Clarify why we might not be able to open the database.
Change load to not have mutable default values ([`f8d6a37`](https://github.com/eyeonus/Trade-Dangerous/commit/f8d6a37fe2bd31d02bacea8ca4fab12771cc2d01))

* Change the call to next to continue, as it&#39;s within a for loop
rather than an iterator. ([`66283db`](https://github.com/eyeonus/Trade-Dangerous/commit/66283db488f03e48afa75924cffdbbfc94126be5))

* Merged kfsone/tradedangerous into master ([`da3861e`](https://github.com/eyeonus/Trade-Dangerous/commit/da3861e874c768b6275a966879c1d4cb6ae1a3f2))

* Grrr, forgot to save the accdb ([`468bd63`](https://github.com/eyeonus/Trade-Dangerous/commit/468bd63c83e8fc1bd1401152a56a901ccd370579))

* Minor corrections to various prices ([`55313d0`](https://github.com/eyeonus/Trade-Dangerous/commit/55313d0c6e477ec26487eddefa22310e4fc02867))

* Some name corrections, price removals and updates ([`f3280a4`](https://github.com/eyeonus/Trade-Dangerous/commit/f3280a4801f78f4cb606040905366255a9d88ae2))

* Merged kfsone/tradedangerous into master ([`740454a`](https://github.com/eyeonus/Trade-Dangerous/commit/740454adfc6d5c61240b7db351d1399b07bd65ac))

* Fixup spacing in the checklist instructions. Missing space. ([`f03f9b4`](https://github.com/eyeonus/Trade-Dangerous/commit/f03f9b4f5b3672d011890851736481145f927e3d))

* Several station updates ([`9c935ac`](https://github.com/eyeonus/Trade-Dangerous/commit/9c935ac1db6eea7aa93d2a4c1f2d3d6e9652f81e))

* Fix --avoid not handling station names correctly.

Also minor cleanup. ([`16fe4b5`](https://github.com/eyeonus/Trade-Dangerous/commit/16fe4b5af4d446fb341d0d61bfc06c64c04d82bd))

* Direct the user to the Microsoft site if we can&#39;t open the database
file. Despite having Access 2013 installed, I still had to install
the ODBC drivers manually. ([`b0aaa79`](https://github.com/eyeonus/Trade-Dangerous/commit/b0aaa7917d58e73dc535b45a375ae49fa3a3ff9f))

* Merge branch &#39;master&#39; of https://bitbucket.org/anothermindbomb/tradedangerous ([`eed03aa`](https://github.com/eyeonus/Trade-Dangerous/commit/eed03aa9fbcacd0255b696399e2cd3cb9855df32))

* Merged kfsone/tradedangerous into master ([`ff32ef9`](https://github.com/eyeonus/Trade-Dangerous/commit/ff32ef94ed6660de9a491dff5b01f1198207c7ed))

* Merge branch &#39;master&#39; of https://bitbucket.org/anothermindbomb/tradedangerous

Conflicts:
	trade.py ([`e638964`](https://github.com/eyeonus/Trade-Dangerous/commit/e638964392208faf5ea95504506c8f9b98e2a384))

* Merge branch &#39;master&#39; of bitbucket.org:kfsone/tradedangerous ([`fad8efb`](https://github.com/eyeonus/Trade-Dangerous/commit/fad8efb9f98eb6207cc3cdfd05971ea574380f59))

* Show hop number on the MFD ([`e1ed24c`](https://github.com/eyeonus/Trade-Dangerous/commit/e1ed24c55857ad08b3fdaf181f09b16e3fb46cd3))

* Presentation cleanup:

- blank line after routes,
- show routes before checklist so you know what you&#39;re checklisting. ([`787f2b4`](https://github.com/eyeonus/Trade-Dangerous/commit/787f2b4db7ad191f4dedb031f1e867ed31f99860))

* Merged in anothermindbomb/tradedangerous (pull request #1)

Assorted cleanup ([`30cd5e1`](https://github.com/eyeonus/Trade-Dangerous/commit/30cd5e1091b5bb9376aff94a570a1b99dbf2f613))

* Sigh - undo my push of &#34;here&#39;s me typing in the CLI and smacking it
into the code instead&#34; ([`beb41d6`](https://github.com/eyeonus/Trade-Dangerous/commit/beb41d63058589125766c106eb2be9f99f2b1429))

* Merge in changes from tidying distances code. ([`7d837d2`](https://github.com/eyeonus/Trade-Dangerous/commit/7d837d2fe175262c727651eeb0f052a580b8b9ca))

* Removed unused import for namedtuple
Remove trailing spaces ([`d267f0e`](https://github.com/eyeonus/Trade-Dangerous/commit/d267f0e593104eea208b6678f5d0bfe653d84a5e))

* More tidying.

Remove mutable default arguments and replace them with none ([`790eae7`](https://github.com/eyeonus/Trade-Dangerous/commit/790eae7a09279942a5d8ccb693dde8ee249bca0f))

* Tidy up importer. Nothing interesting

Remove extraneous imports &amp; variables.
Correct typo
Change &#34;== None&#34; to &#34;is None&#34; as it&#39;s faster and more idiomatic. ([`e5be21c`](https://github.com/eyeonus/Trade-Dangerous/commit/e5be21c2b53703b5b998f567dc46782bcb41e1c8))

* Tidy up a little indentation on some very long calcBestHops calls. ([`820594f`](https://github.com/eyeonus/Trade-Dangerous/commit/820594f3837ce3ed7cb72f38b1c283ce1432a8fb))

* Tidy up the trade module. Remove unused variables and fix
a comma in a call to &#34;notes&#34;, which meant we&#39;d pass a string rather
than a bool. ([`f102724`](https://github.com/eyeonus/Trade-Dangerous/commit/f102724b3014a8984cbf837a295e930171bff9f4))

* Remove unused classes from importing tradedb. ([`6376450`](https://github.com/eyeonus/Trade-Dangerous/commit/637645026094f8f6d820bf11c860845a3ae19aad))

* Remove self.value from the Trade object. It was never defined
and it was never referenced, other than in the &#34;describe&#34; method. ([`5490901`](https://github.com/eyeonus/Trade-Dangerous/commit/5490901ca7230b58ddd6d03578ac80a73436107e))

* Remove maxinst in favour of maxsize. Code works ok so long as maxLyPer was a value. Short-circuit for the win. ([`de1db8c`](https://github.com/eyeonus/Trade-Dangerous/commit/de1db8cf1121186bdab5837c18ea8011fa30c015))

* Merged kfsone/tradedangerous into master ([`975b6e4`](https://github.com/eyeonus/Trade-Dangerous/commit/975b6e4be51f04159c6fc56c336e2fb2dafa8054))

* Latest price updates ([`a4146ef`](https://github.com/eyeonus/Trade-Dangerous/commit/a4146efbcdab7a0e2eda3c3e6e4c8285c84a6836))

* Price updates ([`b4b6d2a`](https://github.com/eyeonus/Trade-Dangerous/commit/b4b6d2a826f9b24945807746b40c7393764e87d5))

* Fixed DummyFD (unexpected keyword argument error) ([`28f3b72`](https://github.com/eyeonus/Trade-Dangerous/commit/28f3b722c305b336c4b26b9c4fae018c889c954d))

* v2.06 - Added experiment X52 Pro MFD support

Because having a checklist just wasn&#39;t enough, I want to see it on my MFD so I don&#39;t have to alt-tab out ([`0f24081`](https://github.com/eyeonus/Trade-Dangerous/commit/0f24081092ee8b892ccd06bfaf34bd2b94cae67c))

* Price updates ([`b6ff48d`](https://github.com/eyeonus/Trade-Dangerous/commit/b6ff48d160c30818896496261f3b0652482ef9e7))

* Fixed a shutdown error with the saitek code ([`1dddd35`](https://github.com/eyeonus/Trade-Dangerous/commit/1dddd35494dff51f51f78b7ff72813626304e62e))

* Minor tweaks to DirectOutput and X52 Pro wrapper ([`6578257`](https://github.com/eyeonus/Trade-Dangerous/commit/65782572a8ccde2afaffbb5d38f13870275f0851))

* Initial, horribly mangled, attempt to salvage Frazzle&#39;s X52 Pro MFD wapper ([`eaa2b14`](https://github.com/eyeonus/Trade-Dangerous/commit/eaa2b1448e07d36e30f50812f1f63586d0c8245a))

* Updated prices ([`aff7db9`](https://github.com/eyeonus/Trade-Dangerous/commit/aff7db9a591c69e0ffeb68f8a6d0ebf865ac440a))

* v2.05 Cleanup and avoidance refactor, fixed --via ([`cf7ebfd`](https://github.com/eyeonus/Trade-Dangerous/commit/cf7ebfd67a3b2c95571ced843e8be6dd6afbe05f))

* Merge branch &#39;master&#39; of https://bitbucket.org/anothermindbomb/tradedangerous ([`73d39aa`](https://github.com/eyeonus/Trade-Dangerous/commit/73d39aafe20fcc193f949630538a8091f3e9edc4))

* Point the .accdb file somewhere local ([`2e5f76b`](https://github.com/eyeonus/Trade-Dangerous/commit/2e5f76b679de01535367a28a8c2f3f718f49cfd2))

* Merged kfsone/tradedangerous into master ([`2a7e3eb`](https://github.com/eyeonus/Trade-Dangerous/commit/2a7e3eb3198a89ff9f3aef74c773a1c137e20848))

* v2.04 adding &#34;--checklist&#34;

Added &#34;--checklist&#34; argument which walks you through the calculated route rather than just printing it,
Exposed &#34;localedNo()&#34; in TradeCalc to print locally formatted numbers, e.g. &#34;2,134,542&#34; ([`c1404c2`](https://github.com/eyeonus/Trade-Dangerous/commit/c1404c27fec4cc920f00ae09cc78eb7f2705adcb))

* Merged kfsone/tradedangerous into master ([`bc5e114`](https://github.com/eyeonus/Trade-Dangerous/commit/bc5e114cb6772ca78336580fc36b1d74369e757d))

* Updated prices at various stations ([`11c3736`](https://github.com/eyeonus/Trade-Dangerous/commit/11c3736bf9c8626d60e02f16e4553c40f9c9e913))

* Updates ([`10524a6`](https://github.com/eyeonus/Trade-Dangerous/commit/10524a6eeff5a17d33f601bf3a642c4060158110))

* Exact match is an exacth match: Freeport forever! ([`955056e`](https://github.com/eyeonus/Trade-Dangerous/commit/955056ed01110086a21a42e1752e6990b7e5defd))

* Updated Keries ([`cc06279`](https://github.com/eyeonus/Trade-Dangerous/commit/cc062797ab38b30a9bf592da3654a90d46e74ebc))

* Corrected Derrickson&#39;s ([`629a6f5`](https://github.com/eyeonus/Trade-Dangerous/commit/629a6f569f416317f6ff8998f76603487b111bfc))

* h Draconis ([`87cf7bc`](https://github.com/eyeonus/Trade-Dangerous/commit/87cf7bcd86370f7de0822f15bfc9abe46e4556c1))

* CM Draco ([`254b8d6`](https://github.com/eyeonus/Trade-Dangerous/commit/254b8d61f6240215d6b1e6b6b2e7b7c492e44f34))

* Added LHS 2819 ([`3d73497`](https://github.com/eyeonus/Trade-Dangerous/commit/3d73497377a98eae8d047495306dccfb7fec708d))

* LP 64-194 ([`671aaa2`](https://github.com/eyeonus/Trade-Dangerous/commit/671aaa2df2df9cdcbc83d52935bb67591c03aa19))

* Baker platform ([`bb70970`](https://github.com/eyeonus/Trade-Dangerous/commit/bb7097094f23f47f887bb61bfc14c22f5209f25a))

* Szulkin. What a shit hole that is. ([`e13e9c0`](https://github.com/eyeonus/Trade-Dangerous/commit/e13e9c0568f254f7cf811e5af5e0baf841d263d8))

* Hume ([`5aece94`](https://github.com/eyeonus/Trade-Dangerous/commit/5aece94117d7bb3231bb854f3740b3fb12c8db00))

* Fix for off-by-one error with jumps-per ([`a6e9262`](https://github.com/eyeonus/Trade-Dangerous/commit/a6e92621f1529193f2b20ff9596e03666ec341c7))

* Added aulis ([`08d3034`](https://github.com/eyeonus/Trade-Dangerous/commit/08d3034ad855383f32a2e0e9b0db433772b4423e))

* Added McArthur&#39;s Reach ([`a5a90e9`](https://github.com/eyeonus/Trade-Dangerous/commit/a5a90e9646863a8e2ba8ad36fe49e6c75a2c277e))

* Use bind params for insert into stations so names with apostrophes work. ([`9dc9b98`](https://github.com/eyeonus/Trade-Dangerous/commit/9dc9b98ca04b91eebbb0cc751b2c54367832d027))

* Modify tdb.query to allow bind parameters ([`f435846`](https://github.com/eyeonus/Trade-Dangerous/commit/f4358467a8ce7bb45a1ac87e9e11c2f1189b3097))

* Load wasn&#39;t considering that destinations might be avoided ([`c635e86`](https://github.com/eyeonus/Trade-Dangerous/commit/c635e867a22269063abe7b22f67c3e5678d61c8e))

* Added distances and lhs 2884 ([`728d775`](https://github.com/eyeonus/Trade-Dangerous/commit/728d77565b8e089d3a6cbc343ecbed2f77efa9a3))

* Added Meliae and Aganippe ([`126de60`](https://github.com/eyeonus/Trade-Dangerous/commit/126de60f56123fdd7eeb3de5eb3d3f1e528a9346))

* And just to prove it, here are some station names with spaces in them ([`5bdf6de`](https://github.com/eyeonus/Trade-Dangerous/commit/5bdf6dee0b2ed68952f56bca5bb375e15e56fcbd))

* When spaces don&#39;t get removed from station names, what happens next will make you cry for joy. ([`0c47602`](https://github.com/eyeonus/Trade-Dangerous/commit/0c47602e5667f7ddf82a7038773ebc45288578e6))

* Fixed some Beagle2 price errors ([`25a406a`](https://github.com/eyeonus/Trade-Dangerous/commit/25a406a27c99957df6e9e1d1d7978265cd37b64a))

* Merged kfsone/tradedangerous into master ([`293407a`](https://github.com/eyeonus/Trade-Dangerous/commit/293407aa84660d6ac0729121c572ad19d687b9f4))

* v2.03 imported wtbw&#39;s star position data to create links table

Note: I still need to add a handful of stations for this to complete the data set ([`42be685`](https://github.com/eyeonus/Trade-Dangerous/commit/42be685c798bb679ddeb17be5440ae1c3205c414))

* Updates ([`300d34d`](https://github.com/eyeonus/Trade-Dangerous/commit/300d34d9e04d107963ccc0c5ea7a8f559cc51d52))

* Updated prices ([`705fb57`](https://github.com/eyeonus/Trade-Dangerous/commit/705fb576e27735de6192a0e593d06dd38831de65))

* Made --via accept routes with the via station as the first hop if the user doesn&#39;t specify a --from
Updated readme, added change log ([`b1fb681`](https://github.com/eyeonus/Trade-Dangerous/commit/b1fb6815f4d16da1c8d32d09f138d02840920db0))

* This guy had no idea what main was for, but when he found out, you&#39;ll never believe what he did with it! ([`f7e2bb1`](https://github.com/eyeonus/Trade-Dangerous/commit/f7e2bb1965e6d5e05d2c806190768563b01da480))

* Made * and @ do the same things in import.py ([`f745d24`](https://github.com/eyeonus/Trade-Dangerous/commit/f745d24cbb195e3ce7461f0efaa638a678125b0a))

* Fixed getStation behavior ([`6d57be7`](https://github.com/eyeonus/Trade-Dangerous/commit/6d57be73e582fb29b25ba76210d0acfa13133d86))

* Cope with more characters when normalizing (hyphens, apostrophes, etc) ([`1665dbb`](https://github.com/eyeonus/Trade-Dangerous/commit/1665dbb095968d4fa06268244573646f47d1c912))

* Updated readme to describe --avoid ([`01f3a4a`](https://github.com/eyeonus/Trade-Dangerous/commit/01f3a4a4daf513a3ae7b41d2ccb78e164999a33f))

* v2.01 - --avoid accepts items, systems and stations

All of which perform partial matching and ambiguity checking. So &#34;--avoid pal&#34; will detect &#34;palladium&#34; and &#34;opala&#34;.

I&#39;ll probably split them to separate options as the galaxy expands and it becomes hard to find unambiguous snippets. ([`2b9de54`](https://github.com/eyeonus/Trade-Dangerous/commit/2b9de5472d7fabf94dd02007d85adab2b58a5fd7))

* Forget getSystem(), the all new &#34;normalized_str&#34; will truly amaze you! ([`1c9a6ad`](https://github.com/eyeonus/Trade-Dangerous/commit/1c9a6ad6e6c635f280e759231323e7f500f01b4f))

* You won&#39;t believe what I fixed here! ([`819d1e2`](https://github.com/eyeonus/Trade-Dangerous/commit/819d1e2eca1b417a7a41081040581a8ea71e89f2))

* After you see what getSystem does not, you&#39;ll never use the old version again!

[Fixed it returning a name instead of a System] ([`fa59b6f`](https://github.com/eyeonus/Trade-Dangerous/commit/fa59b6f093e95a7746d31c86f034a7fc12c6e6ae))

* TradeDB.Station got a str() and you won&#39;t believe what it does! ([`f3898a4`](https://github.com/eyeonus/Trade-Dangerous/commit/f3898a4567c932fc1df95089b0ae30472800efcb))

* Fixed getSystem ([`015a5ba`](https://github.com/eyeonus/Trade-Dangerous/commit/015a5bab1fdfc5fae189582da5c22fa50d0b9a4c))

* Little tidy up of import.py ([`c320c29`](https://github.com/eyeonus/Trade-Dangerous/commit/c320c2907f2629ad5c21e252b40d13c481d216fe))

* TradeDB.getSystem improvements

It now uses list_search to allow partial matches with ambiguity detection, it&#39;s also able to resolve a station from a system. ([`39fc046`](https://github.com/eyeonus/Trade-Dangerous/commit/39fc046c62f27710ece36449b09cd926bf856ea8))

* Added TradeDB.getSystem ([`f3d9904`](https://github.com/eyeonus/Trade-Dangerous/commit/f3d9904b3b3e1deeb5904da1313b3ffd273ea697))

* TradeDB.list_search is now whitespace agnostic.

This allows &#39;dom. appliances&#39; to match &#39;dom.appl&#39;, &#39;i Bootis&#39; to match &#39;IBOOTIS&#39; etc. ([`b6bde7e`](https://github.com/eyeonus/Trade-Dangerous/commit/b6bde7e0e217c256ad2f01d4fa74f8da0797b083))

* Use LookupError for key lookup failures rather than ValueError ([`de0d8c7`](https://github.com/eyeonus/Trade-Dangerous/commit/de0d8c7fb035155dc587c770dcd8d0e4697f385d))

* Updated prices ([`a041595`](https://github.com/eyeonus/Trade-Dangerous/commit/a0415955dd051c3037ff2cfbaf8f9e502db3618b))

* Some missing middle-links ([`7e5a916`](https://github.com/eyeonus/Trade-Dangerous/commit/7e5a916107ad6c1d10b7736831941ae3e652bb0a))

* More trade links ([`abde74d`](https://github.com/eyeonus/Trade-Dangerous/commit/abde74d04d2f3f97dceb4d8a9008bd38a9d5265f))

* Added PiFang ([`57fd7d4`](https://github.com/eyeonus/Trade-Dangerous/commit/57fd7d4ab88f0113dff937cae6b91892f528f4c1))

* Added &#39;#stop&#39; and &#39;#echo&#39; commands to import.py ([`a869794`](https://github.com/eyeonus/Trade-Dangerous/commit/a86979441f554f297917a0ffff95ce1eb0f81cd7))

* Added Tilian ([`b921504`](https://github.com/eyeonus/Trade-Dangerous/commit/b921504e32cc87de07d9a0f30cbd268e4461df3d))

* Fix for fast_fit visiting the same item multiple times.

fast_fit iterates across all items from offset but it wasn&#39;t taking this into account when it was determining the sub load. ([`ead5617`](https://github.com/eyeonus/Trade-Dangerous/commit/ead5617e445fced2dce40bc9733888cbd90cf3bd))

* Revised documentation ([`a096590`](https://github.com/eyeonus/Trade-Dangerous/commit/a09659076b5d343f2e1c23f5009f61fbb51738b6))

* Cleaned up command line option help ([`f276cc2`](https://github.com/eyeonus/Trade-Dangerous/commit/f276cc2351e4a3f0586f3d50dd406962cbf7e6c9))

* allowUnkown -&gt; rejectUnknown

Made allowing unknown systems in new-star lines the default behavior and instead require you to specify &#39;#rejectUnknown&#39; if you want unknown systems to be an error condition. ([`3009518`](https://github.com/eyeonus/Trade-Dangerous/commit/30095183332878d0c3a0d2cd8d3b6e1e327c1d4f))

* Cleaned up fit system.

Added and cleaned up comments, made the fitFunction a member of the tradeCalc, normalized the generator inside each fit function. ([`e4350a4`](https://github.com/eyeonus/Trade-Dangerous/commit/e4350a46cc1d7be92b7b61d88bf64c31f350732b))

* List items in descending profit order. ([`af15b01`](https://github.com/eyeonus/Trade-Dangerous/commit/af15b01d2f0ca8a72feafe5aac908b5888275d56))

* Optimization

Replaced the tryCombinations function with a stub that can invoke either a fast_fit knapsack based solver or a very slow brute-force solver for validating results. Default is to use the knapsack method. The current getBestTrade also culls the item list of items that are worth less than the cheapest item. This may be a premature optimization. ([`1514a64`](https://github.com/eyeonus/Trade-Dangerous/commit/1514a649e055274cc6936f54e1dcc2b0809af391))

* More stars, more distances ([`26d25b9`](https://github.com/eyeonus/Trade-Dangerous/commit/26d25b9eceb538eb264f3e829f9365a3e491fceb))

* Dahan prices and links ([`4ab1c57`](https://github.com/eyeonus/Trade-Dangerous/commit/4ab1c57d3cb46bb47e5e9b1b11822ca146c716b9))

* More systems, distances, price updates and renamed empty-system stations to SYSTEM* ([`1c81875`](https://github.com/eyeonus/Trade-Dangerous/commit/1c81875a92610f13199786a16106c48f7f78db6e))

* Made station names in empty systems = {SYSTEMNAME}* ([`56c0181`](https://github.com/eyeonus/Trade-Dangerous/commit/56c018115a474594b99b45855fc20d093af7d07a))

* Fixed bug with --detail ([`1324a32`](https://github.com/eyeonus/Trade-Dangerous/commit/1324a32fe0de9cb5d499a0ae724af597dd5c4c8f))

* Typo correction (Styx) ([`a434be2`](https://github.com/eyeonus/Trade-Dangerous/commit/a434be28365c3f537e2891e0564f03afe9c544f7))

* Present --detail for all hops ([`0eec970`](https://github.com/eyeonus/Trade-Dangerous/commit/0eec97023d57ebcd835b8f5c73260a00c2c02f70))

* Fix for --ly-per ([`1e8b695`](https://github.com/eyeonus/Trade-Dangerous/commit/1e8b695d75580fd4800b44647eb85157da2484cb))

* Azeban prices ([`9b6812a`](https://github.com/eyeonus/Trade-Dangerous/commit/9b6812aa940b611d88411a753f26153afb4840e7))

* Fixed cobalt double up ([`a3718b5`](https://github.com/eyeonus/Trade-Dangerous/commit/a3718b5b4d6e75e22007f54c28b06890dc22b67f))

* Fixes, cleanup and --detail

--detail will show jumps on a multi-jump hop,
Moved several output items to --debug and increased --debug reporting,
Added code to validate data such as links between systems,
Fixed a problem with tdb.itemIDs being populated with { name: name } ([`4697912`](https://github.com/eyeonus/Trade-Dangerous/commit/469791226aa35936a2e24e97b4d71ef6c2b144f4))

* --via improvement

When specifying via with no destination, allow via to be the destination. E.g. via B could produce A-&gt;B-&gt;C or A-&gt;C-&gt;B depending on which route is most profitable. ([`aa49676`](https://github.com/eyeonus/Trade-Dangerous/commit/aa4967612392fbce001862d1f7b1a68aa2cc32a8))

* Updated prices, more systems ([`2f64d5c`](https://github.com/eyeonus/Trade-Dangerous/commit/2f64d5c881bd21cc0370623768016e63d6c900b5))

* Lots more distances and stars ([`8f82865`](https://github.com/eyeonus/Trade-Dangerous/commit/8f828657f9bf021f85fd89658dedf50f9f426336))

* Made ly-per float ([`2f5bb6e`](https://github.com/eyeonus/Trade-Dangerous/commit/2f5bb6eecf5dec6ed53e8a255736160c9309a2fe))

* Price changes ([`836d21f`](https://github.com/eyeonus/Trade-Dangerous/commit/836d21f38f4f373d87dc7270337005a59743ede2))

* Distances and newer prices ([`d73fc99`](https://github.com/eyeonus/Trade-Dangerous/commit/d73fc9904f88beb0f1313f6bbafdcf20720ad372))

* Allow unknown star systems if &#39;#allowUnknown&#39; is specified ([`98fc67c`](https://github.com/eyeonus/Trade-Dangerous/commit/98fc67c9b2bf921ed2ddc9a185a404b105e7dfeb))

* Ignore access lock file ([`61e625e`](https://github.com/eyeonus/Trade-Dangerous/commit/61e625e8a75b28a32f4542e691bd729cd3bc7170))

* Read distances from the db ([`2fca72c`](https://github.com/eyeonus/Trade-Dangerous/commit/2fca72c1a91251440be0088a65d7246663764803))

* Distances and Dahan ([`2d64e7e`](https://github.com/eyeonus/Trade-Dangerous/commit/2d64e7e821b7c4c572195be766b7b5d2fa276a16))

* Distances and Dahan ([`167c83c`](https://github.com/eyeonus/Trade-Dangerous/commit/167c83ce014f4c17fb85a9d47c3f133337ca8cf1))

* Beagle2 prices ([`352a425`](https://github.com/eyeonus/Trade-Dangerous/commit/352a4252a0a2882c879eebb680d1a62a11774c16))

* Typo fix ([`c79bede`](https://github.com/eyeonus/Trade-Dangerous/commit/c79bededaf9cc18459e4b5616ab6c3c7064292b1))

* Oops ([`ffe061d`](https://github.com/eyeonus/Trade-Dangerous/commit/ffe061d2c3385faa1cd6a678c57f0e1b5aa46780))

* Adding maxLyPer ([`0198730`](https://github.com/eyeonus/Trade-Dangerous/commit/0198730efe9e9caea43eda09b0ddfbcdabfea5ba))

* Updated ignore ([`0e6790d`](https://github.com/eyeonus/Trade-Dangerous/commit/0e6790dcf846845cb9ecf578eac4f863339276b1))

* Distances ([`76a28ea`](https://github.com/eyeonus/Trade-Dangerous/commit/76a28ea3b18aeed49357df088a2c4c20fef78fcf))

* Distances ([`9629404`](https://github.com/eyeonus/Trade-Dangerous/commit/9629404466de219f1a1b7569cab774dce115bb4f))

* Minor fixes ([`f52b7b3`](https://github.com/eyeonus/Trade-Dangerous/commit/f52b7b3ed4e4e3a191e11f5aeae5e2b80c6d5761))

* Updated various data ([`a88deed`](https://github.com/eyeonus/Trade-Dangerous/commit/a88deed7e7f1ce231a808fef98c8c87ac379d0d6))

* Moved list_search ([`7b9ba9a`](https://github.com/eyeonus/Trade-Dangerous/commit/7b9ba9a37e8b5e0a0d9b0cad388113c710f9e00c))

* Increment hops improvements ([`81539fd`](https://github.com/eyeonus/Trade-Dangerous/commit/81539fdaa1609dc0d9104ceb9f3f95d60e2931e8))

* Incremental enhancements to jump limits ([`1569462`](https://github.com/eyeonus/Trade-Dangerous/commit/156946249ea4f3dab08fb44caa21b2e17717f4e9))

* Added distances support to the database ([`71c84bd`](https://github.com/eyeonus/Trade-Dangerous/commit/71c84bd64820d8aa7359daa84f53e3df2301c6a0))

* Updated Data ([`a3cd1a1`](https://github.com/eyeonus/Trade-Dangerous/commit/a3cd1a17672c3fc7d350c9a8cc15186132447077))

* Incremental addition of --jumps and --jumps-per ([`ac81dbf`](https://github.com/eyeonus/Trade-Dangerous/commit/ac81dbf61d16fcb18edf4931412a1b2c466224e9))

* Updated data ([`e2a06df`](https://github.com/eyeonus/Trade-Dangerous/commit/e2a06df13038516569dc49d97b4779a7aa6cc3a7))

* Incremental introduction of max jumps/light years code ([`489d80e`](https://github.com/eyeonus/Trade-Dangerous/commit/489d80ebe122f38d8012d04737d65d1e21392965))

* shebang ([`7029a1f`](https://github.com/eyeonus/Trade-Dangerous/commit/7029a1f4f5a276959ba1275b6d5f7aade7a19fa8))

* Updated numbers ([`3393494`](https://github.com/eyeonus/Trade-Dangerous/commit/3393494fe32e3a5af59ea0960a0466137933bc71))

* Added systems and initial jumps/distance code.

Added a separate notion of systems in preparation for supporting multiple stations per system. Partial.

Added preliminary &#39;getDestinations&#39; code to Station which tells you how many stations it can reach and how many light years it takes to get there and how many jumps. This can then be used for best trade calculations at run time rather than limiting the data we load based on direct links. Thus you&#39;ll be able to find trades that require more than one jump. ([`1c56a80`](https://github.com/eyeonus/Trade-Dangerous/commit/1c56a80853d3a073be4b90ecb46bd5bf40c88522))

* Fixed handling of the case where no links are available in getBestTrade ([`4e5d6fd`](https://github.com/eyeonus/Trade-Dangerous/commit/4e5d6fde44dbdd4d3b421fd39b98ea71bf2ceed4))

* Trivial CLI for driving TradeCalc ([`ef363ac`](https://github.com/eyeonus/Trade-Dangerous/commit/ef363ac14b7b7e8c5c65fa39e2753fc449c1e939))

* Updated values ([`c7565f5`](https://github.com/eyeonus/Trade-Dangerous/commit/c7565f5983b01eb8b470d7fee519f97b444ecee9))

* Added optional capcaity parameter to getBestHopFrom ([`a6803b5`](https://github.com/eyeonus/Trade-Dangerous/commit/a6803b5a9148a720f31301a6410d87f509d890bc))

* TradeCalc.getProfits renamed getBestTrade. Added optional capacity parameter to getBestHopFrom ([`ced8c73`](https://github.com/eyeonus/Trade-Dangerous/commit/ced8c73094f3dcaf4d59c451c2a56fe015775aa1))

* Updates ([`8654bbc`](https://github.com/eyeonus/Trade-Dangerous/commit/8654bbcde353aec00dbe86c6438231d2682b0ff5))

* Adding TradeCalc

Moved trade calculation code into TradeCalc and moved TradeCalc and Route into their own file, tradecalc.py

I&#39;ve also added a TradeCalc.getBestHopFrom function to make it easier to use the DB for single hop checks. This function will take a station or a station name, so

   calc.getBestHopFrom(&#34;Aulin&#34;)
will work as well as
   calc.getBestHopFrom(tdb.getStation(&#34;Aulin&#34;)) ([`6573806`](https://github.com/eyeonus/Trade-Dangerous/commit/6573806e4c8ef0a844d6d29422f3faabdf99b618))

* Added method for adding new stars in import ([`ccad866`](https://github.com/eyeonus/Trade-Dangerous/commit/ccad8667da6bd0b96b710bbd8d4e75995ecb9553))

* Added Ovid/Bradfield ([`b14a48d`](https://github.com/eyeonus/Trade-Dangerous/commit/b14a48de9c5a4fef6520838135ecd5dc962e0434))

* Added Ovid/Bradfield ([`4bcb548`](https://github.com/eyeonus/Trade-Dangerous/commit/4bcb5483167572e273a54980b38b24309923d82e))

* Changed query to return and added fetch_all generator

query() now returns a cursor for you to work with, while fetch_all now has the behavior that query() used to have ([`aa04c40`](https://github.com/eyeonus/Trade-Dangerous/commit/aa04c40fdad29b734f4253e6ffbb4a13102c856b))

* Added --links

Allows you to ignore links between stations, treating all stations as linked,
so you can find the best possible sale regardless of distance. ([`78edc32`](https://github.com/eyeonus/Trade-Dangerous/commit/78edc3286085dff00be7f35754f03bd04b225493))

* Fixed report of ambiguous matches ([`7556600`](https://github.com/eyeonus/Trade-Dangerous/commit/7556600069b400d75b59617a18fdbba18959fe49))

* Added 1.0.3 romanek ([`4a8b982`](https://github.com/eyeonus/Trade-Dangerous/commit/4a8b9825138a3889bda9c9901ede7d93251962b8))

* Crappy script for importing new stations ([`7be9544`](https://github.com/eyeonus/Trade-Dangerous/commit/7be95447cee2997356bd1e6b3e15c4f7d11c615b))

* Added 1.0.3 freeport ([`f7bbb39`](https://github.com/eyeonus/Trade-Dangerous/commit/f7bbb3962d4a195487d764255a0cd7c4181c22f3))

* Made station+item primary key for prices ([`f6e5ca4`](https://github.com/eyeonus/Trade-Dangerous/commit/f6e5ca4fa27819ac0c5055b1855210bcd9f6da91))

* Fixed itemIDs table ([`8a94a88`](https://github.com/eyeonus/Trade-Dangerous/commit/8a94a88a5ba4ea3ee1e7c8b65d1cf9b0af2374fd))

* Updated 1.0.3 database ([`3e459a4`](https://github.com/eyeonus/Trade-Dangerous/commit/3e459a4fd2b53c8e7c762e651269857c8940068c))

* Added query() generator and itemIDs item lookup to TradeDB ([`c9134a0`](https://github.com/eyeonus/Trade-Dangerous/commit/c9134a061e5f89f59e92c93aab79313b112c21f5))

* Fresh database for 1.0.3 ([`954e9fb`](https://github.com/eyeonus/Trade-Dangerous/commit/954e9fb4bbe1f63112d0554eef76d6f6df54730e))

* Prices ([`d14854b`](https://github.com/eyeonus/Trade-Dangerous/commit/d14854ba21b2ccb9b1bcb5afaea67818d911744f))

* This code tried to access a variable I&#39;d removed in a previous patch. You&#39;ll never guess what happened next. ([`d3ea873`](https://github.com/eyeonus/Trade-Dangerous/commit/d3ea873118aec80cc1833bb3ecbdbdcad22b531e))

* Performance improvements.

For each hop out of each station:

Discard items which produce less gain than the previous,
When multiple items have the same gain, only keep the cheapest. ([`4efeee7`](https://github.com/eyeonus/Trade-Dangerous/commit/4efeee7381ff5ab856d12768c334e4fcfa066c26))

* DB Update 7/12/2014 ([`4bd0be6`](https://github.com/eyeonus/Trade-Dangerous/commit/4bd0be6adf6fd0e6dc3ab9fec422fde240ca6dae))

* Apply avoidItems to best-gain shortcut ([`ba095fa`](https://github.com/eyeonus/Trade-Dangerous/commit/ba095fa2aa4f1040c59b3c912f5f72287783dcee))

* Fixed origin/dest/via always showing &#39;any&#39; ([`3fa7a4f`](https://github.com/eyeonus/Trade-Dangerous/commit/3fa7a4f2d4b70cd5695da4b20cdf9d8630678afe))

* Added README ([`a146d06`](https://github.com/eyeonus/Trade-Dangerous/commit/a146d061ae2237cfaa397a35889c9338b5f21a76))

* New features

Added --limit for limiting the number of units you buy at a time,
Added --avoid for avoiding certain items (case sensitive right now),
Added --unique for limiting each station to one visit per route ([`feee694`](https://github.com/eyeonus/Trade-Dangerous/commit/feee6946dcada5770b9c52e2258341d09fa8fc81))

* Updated database ([`221e1fd`](https://github.com/eyeonus/Trade-Dangerous/commit/221e1fdce62578f7385991f0a8199ec2407b32ed))

* Go direct to the source for trade items from the list ([`0e3dde2`](https://github.com/eyeonus/Trade-Dangerous/commit/0e3dde2be2fa1beadc078100ed63a31278111704))

* Best match handicap

The handicap ensures that we try lower quantities of higher-value items so that instead of saying &#34;33 Gold + 3 scrap&#34; it can detect that you could afford &#34;31 Gold + 5 Tantalum&#34; for a better profit margin ([`e5674df`](https://github.com/eyeonus/Trade-Dangerous/commit/e5674df7a1d393de28ef3fd22a40cdd109906fb8))

* Per-hop iteration rather than per-route.
This allows pruning of routes which under perform which greatly improves performance on 8+ hops ([`3061c49`](https://github.com/eyeonus/Trade-Dangerous/commit/3061c49f61e615e903fa9618846c7a7217779292))

* Another indirection removed ([`9ea35f2`](https://github.com/eyeonus/Trade-Dangerous/commit/9ea35f2f0598ef7b636f0d109e15194481754179))

* Use station references directly ([`2f17e06`](https://github.com/eyeonus/Trade-Dangerous/commit/2f17e0620ea22471211cf1950ca969ccb8a1b543))

* Use station references directly ([`6070fce`](https://github.com/eyeonus/Trade-Dangerous/commit/6070fcec7111dfe77abcdd17c102085e20c3d3f2))

* List routes in descending order of value again ([`263a878`](https://github.com/eyeonus/Trade-Dangerous/commit/263a878a4d4307a78050eb470da69a6061da8242))

* Multiply gain by amount bought, duh ([`1a40cf8`](https://github.com/eyeonus/Trade-Dangerous/commit/1a40cf8b81067b2359626d0501dc6f0f085d7564))

* Minor changes ([`6e40e91`](https://github.com/eyeonus/Trade-Dangerous/commit/6e40e91278fe802f92e895ed05e57a8dd2c9870b))

* Early working version ([`2458f81`](https://github.com/eyeonus/Trade-Dangerous/commit/2458f81d13942f622f0959262b0dc74f981ef0e5))
