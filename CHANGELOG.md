# CHANGELOG



## v11.1.3 (2024-04-29)

### Fix

* fix: eddblink retrieval (progress, bandwidth) (#144)

 - reduce the amount of data transferred to determine if there is new eddblink data, previously we were downloading each file twice roughly,
 - capture the uncompressed file-length during the probe, so we can show the user an accurate progress bar 
 ([`af5b993`](https://github.com/eyeonus/Trade-Dangerous/commit/af5b9938b6b15334f6539a94b32d7db216a050df))

* fix: Assume stations with unknown type are Fleet Carriers ([`aa9cad1`](https://github.com/eyeonus/Trade-Dangerous/commit/aa9cad12b0b77e0cf5291f8eab4ed9e4658f6b95))


## v11.1.2 (2024-04-29)

## Fix

* fix: locale-dependant strptime() ([`aee07ef`](https://github.com/eyeonus/Trade-Dangerous/commit/8fac2bafa23f0a1a5b1715d47b2a8f775f1b0770))

Some people speak a language other than English, and have their computer set to be in that language. This messes up the timestamp parser when trying to check for new downloads in eddblink, because the timestamp is in  English.


## v11.1.1 (2024-04-28)

### Fix

* fix: commit before processPrices, only close tempDB if no prices file ([`5a421bd`](https://github.com/eyeonus/Trade-Dangerous/commit/5a421bda45d43b33eeec0c33bf921dccf396e6c9))

* fix: Don&#39;t assume machine has &#39;en_US.UTF-8&#39; installed. ([`b3a1e29`](https://github.com/eyeonus/Trade-Dangerous/commit/b3a1e291b6bf7f5648a81b375fc7cdd80ede184c))

* fix: locale-dependant strptime() ([`8cd5ede`](https://github.com/eyeonus/Trade-Dangerous/commit/8cd5edef43621ace16f9e2cc850952c9a9ab0a4f))


## v11.1.0 (2024-04-27)

### Feature

* feat: add --age to buy command

fixes #136 ([`fbf6c47`](https://github.com/eyeonus/Trade-Dangerous/commit/fbf6c476bf6ea7f2d187099f56d3b7152a68d1c3))


## v11.0.6 (2024-04-27)

### Fix

* fix: linter errors in jsonprices.py ([`193b34e`](https://github.com/eyeonus/Trade-Dangerous/commit/193b34eab862f915f1d737f633e5d7ab8eb46e97))

* fix: missing f-string prefix

running build-cache without force printed the mustached text rather than the path it was supposed to ([`390e00a`](https://github.com/eyeonus/Trade-Dangerous/commit/390e00a8604ad8d5f7a63021bbe1a2205c49c887))

### Refactor

* refactor: mark scripts as deprecated

jsonprices.py and submit-distances.py appear to be unused and unworkable, so mark them as deprecated in order to remove them soon. ([`b976088`](https://github.com/eyeonus/Trade-Dangerous/commit/b976088573b393855261bb6ccfaf21999bf865f5))

### Revert

* revert: 'feat: &#39;prices&#39; option in eddblink'

Sorry Tromador, it just causes too many problems. ([`d344e2e`](https://github.com/eyeonus/Trade-Dangerous/commit/d344e2eba2c81955033916e6beab154a8000cfe6))


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

* feat: &#39;prices&#39; option in eddblink

spansh and eddblink plugins no longer regenerate the
`TradeDangerous.prices` cache file by default

The cache file is used to rebuild the database in the event it is lost,
corrupted or otherwise damaged.

Users can manually perform a backup by running eddblink with the
&#39;prices&#39; option. If not other options are specified, eddblink will only
perform the backup

If any other options are specified, eg. `-O listings,prices`, eddblink
will perform the backup after the import process has completed. ([`257428a`](https://github.com/eyeonus/Trade-Dangerous/commit/257428aded8962b2a85920188e14525aa0d72863))

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

### Refactor

* refactor: enable rich text

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


## v10.14.3 (2024-04-15)

### Fix

* fix: Don&#39;t overwrite TradeDangerous.prices

spansh import plugin now writes to `&lt;TD_path&gt;/tmp/spansh.prices` rather
than overwriting the cache file, and automatically imports the resulting
spansh.prices file when processing has completed, rather than asking the
user to import it via the import dialog box.

Also added the `listener` option to the spansh plugin to forego the
import when run from TD-listener. ([`2c5080b`](https://github.com/eyeonus/Trade-Dangerous/commit/2c5080b76d5e5c497a56fbb0de60f3e4ae204f93))


## v10.14.2 (2024-03-23)

### Fix

* fix: Update pyproject.toml ([`c25e778`](https://github.com/eyeonus/Trade-Dangerous/commit/c25e778df27540420d40909831f3baf4e6012794))

* fix: Create pyproject.toml ([`bd54be8`](https://github.com/eyeonus/Trade-Dangerous/commit/bd54be86cbe0a967f8fee06a0e9b16b4d77f4ee8))


### Refactor

* refactor: Update publish.txt ([`d8ae0b7`](https://github.com/eyeonus/Trade-Dangerous/commit/d8ae0b76409d77bec68069080bba90bcc798e337))


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


## v10.13.10 (2023-02-13)

### Fix

* fix: make gui work again ([`f0a95c3`](https://github.com/eyeonus/Trade-Dangerous/commit/f0a95c3950783c6377df0c0ef3fce0f24769c4c9))

### Refactor

* refactor: use raw strings for regex

Fixes #107 ([`74a4c31`](https://github.com/eyeonus/Trade-Dangerous/commit/74a4c3190eb300981d5c578fe3105c7edaf8f122))


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


## v10.13.8 (2022-12-27)

### Chore

* chore: Remove Windows testing until it stops being broken

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

* chore: Update python-app.yml ([`188a592`](https://github.com/eyeonus/Trade-Dangerous/commit/188a592c6c265de6c1d2c693d1b136ad52507dd2))

* chore: Fix tox-travis breaking publish testing ([`3c00ea0`](https://github.com/eyeonus/Trade-Dangerous/commit/3c00ea0fed76ac7e0ea5db4b35d9ee27dd8c7391))

### Fix

* fix: Fix #104 ([`4b90222`](https://github.com/eyeonus/Trade-Dangerous/commit/4b90222a7f7f38cd7061bf879dc1c9751dc8e387))

### Refactor

* refactor: Update ship index message.

Minor comment changes as well. ([`6f63d4d`](https://github.com/eyeonus/Trade-Dangerous/commit/6f63d4dde6de10aeca9b80aee3dcfcf0a95ef2ed))


## v10.13.7 (2022-06-15)

### Fix

* fix: Forgot to remove some debug code. ([`8b1b889`](https://github.com/eyeonus/Trade-Dangerous/commit/8b1b889823365b337ac9657cfbf034c0373ee76c))

* fix: nav errors when no route found

Still errors, but now it&#39;s the TD-specific error that&#39;s intended to be
thrown rather than the Python error. ([`5f8e95a`](https://github.com/eyeonus/Trade-Dangerous/commit/5f8e95abd5b49a53bb2015dadf35dd6cc372655d))


## v10.13.6 (2022-06-09)

### Fix

* fix: strip microseconds off timestamps which have them ([`17b603d`](https://github.com/eyeonus/Trade-Dangerous/commit/17b603d52517d1bfdf9956993bec656a3e8b6673))


## v10.13.5 (2022-06-01)

### Fix

* fix: set default argv to None ([`4b44458`](https://github.com/eyeonus/Trade-Dangerous/commit/4b444581844a356c7cf65c1d4301bac83cf93436))


## v10.13.4 (2022-06-01)

### Chore

* chore: Pypi authentication error

Added PYPI_TOKEN to Actions workflow ([`87e2c82`](https://github.com/eyeonus/Trade-Dangerous/commit/87e2c82a3deee9f0679f76723f420c24b79ff8b9))


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

* refactor: split gui into own console command &#39;tradegui&#39;

Can no longer launch TD GUI by passing the &#39;gui&#39; argument to trade as in
&#39;&gt;python trade.py gui&#39;

Good news is this means users not using the GUI won&#39;t get any tk related
errors when running the CLI.

### Documentation

docs: updated gui.py with development roadmap ([`5e4d272`](https://github.com/eyeonus/Trade-Dangerous/commit/5e4d2725d3086a9868733397a4dbdf778a29f9bc))


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


## v10.13.1 (2022-01-31)

### Fix

* fix: make semantic tell me what&#39;s broke ([`0c328ca`](https://github.com/eyeonus/Trade-Dangerous/commit/0c328ca49556958438621f5ff84aba7cde39dbdd))


## v10.13.0 (2022-01-31)

### Feature

* feat: add TD_CSV environment variable detection to csv export

Allows saving the the TD cache in a location other than TD_DATA ([`9537082`](https://github.com/eyeonus/Trade-Dangerous/commit/95370829da9b25e3d6aba0e9161c92716be82633))

### Fix

* fix: (maybe) remove test that travis keeps failing on

Possibly revert later once I figure out how this works ([`9e23361`](https://github.com/eyeonus/Trade-Dangerous/commit/9e23361b43d5068c0ef2c5ce13489a74275d653a))


## v10.12.0 (2021-11-20)

### Feature

* feat: Added --max-ls parameter to the buy command. (#96)

Here&#39;s hoping TravisCL doesn&#39;t break. Again. ([`ff371eb`](https://github.com/eyeonus/Trade-Dangerous/commit/ff371eb25b91f745e872dce953001c3644a4db2c))

### Fix

* fix: buy command var &#34;maxLS&#34; not named consistently (&#34;maxLS&#34;, &#34;maxLs&#34;)

All instances have been changed to &#34;mls&#34; to match other commands. ([`1f4989a`](https://github.com/eyeonus/Trade-Dangerous/commit/1f4989a8280702110b68f8b52c08b60a27c41e33))


## v10.11.3 (2021-10-04)

### Chore

* chore: hopefully fix semantic-release not publishing ([`d3b4485`](https://github.com/eyeonus/Trade-Dangerous/commit/d3b44856600b8974d0fb9e77a8470268f4cc21ee))

### Fix

* fix: publish the new version! ([`d8f0dd7`](https://github.com/eyeonus/Trade-Dangerous/commit/d8f0dd700f46c73ba9505ce0dbb6fa726ebd931b))

### Refactor

* refactor: Add TODO, hopefully make Travis publish again. ([`2946b9c`](https://github.com/eyeonus/Trade-Dangerous/commit/2946b9c559a84a604d46aac8c8395c78af0b5d42))


## v10.11.2 (2021-10-03)

### Documentation

* docs: Update README.md

Update copyright dates. ([`d38a096`](https://github.com/eyeonus/Trade-Dangerous/commit/d38a09641eac6ab5f25fa59e9b8187c686267b47))

### Fix

* fix: Correct typo in olddata.

Fixes #94. ([`8cd12c5`](https://github.com/eyeonus/Trade-Dangerous/commit/8cd12c5875566728c0ff79299004b6f19406ebfe))


## v10.11.1 (2021-06-28)

### Performance

* perf: Avoid excessive loops (#93)

Evaluate all filter conditions instead of looping over all stations separately for condition provided.
This leads to a quite substantial speedup if multiple filter conditions are provided. ([`f457db5`](https://github.com/eyeonus/Trade-Dangerous/commit/f457db5c9a6b46ce3610d993ff629d2a579e7ce8))


## v10.11.0 (2021-06-22)

### Feature

* feat: Add switch to filter Odyssey Settlements [&#39;--odyssey&#39;|&#39;--od&#39;].

Fixes #91 ([`396d9f0`](https://github.com/eyeonus/Trade-Dangerous/commit/396d9f0876bcb2c1c4cf7ecb7e164c5139df5c8c))

### Fix

* fix: mfd module not found.

Fixes #92 ([`e5b01b7`](https://github.com/eyeonus/Trade-Dangerous/commit/e5b01b728bcce6eb784a2c8a720d1a1311ccac9d))

### Refactor

* refactor: missing comma ([`87d53ff`](https://github.com/eyeonus/Trade-Dangerous/commit/87d53ffbec3c32ba6613b406d55e360cc32bdb47))

* refactor: broke a test case ([`f7a4a32`](https://github.com/eyeonus/Trade-Dangerous/commit/f7a4a32ded2c75e06d9eefaa01f121a523db0a61))


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

### Fix

* fix: update MFD (PR#88)

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


## v10.9.7 (2021-02-05)

### Fix

* fix: add &#39;VOID OPAL&#39; to corrections

fixes #84 ([`f208023`](https://github.com/eyeonus/Trade-Dangerous/commit/f20802319a503f569d836c8d46ca7231779f5024))

* fix: supposed to be Name Case, not lower case. ([`3da326e`](https://github.com/eyeonus/Trade-Dangerous/commit/3da326e1f5556623e7a3b6b6b4fa78a373e035ce))


## v10.9.6 (2021-01-18)

### Fix

* fix: edmc_batch_plug Path issues (#83)

This fixed two bugs in the EDMC Batch set_environment method.
The method used `pathlib.Path` while `pathlib` was not imported as a
module which threw a NameError. Secondly, the method set the
environments filename to a Path object when it should be a string. ([`ef06684`](https://github.com/eyeonus/Trade-Dangerous/commit/ef06684e0534d1d969658e9b55f3a752c502475e))


## v10.9.5 (2021-01-09)

### Fix

* fix: MaxGainPerTon shouldn&#39;t be set by default. ([`00c558c`](https://github.com/eyeonus/Trade-Dangerous/commit/00c558cf7f31fb82deb4ca176b43ca16db130559))


## v10.9.4 (2020-12-19)

### Fix

* fix: Galactic Travel Guides are not deleted, just rare. ([`b20b9d0`](https://github.com/eyeonus/Trade-Dangerous/commit/b20b9d0abbcf4fb1d371715bc47da2e625a2cb23))


## v10.9.3 (2020-12-16)

### Chore

* chore: Update dev.txt ([`3fe11f7`](https://github.com/eyeonus/Trade-Dangerous/commit/3fe11f756a40328b44cac912264342db30e35a9b))

* chore: Update .travis.yml ([`8348b0a`](https://github.com/eyeonus/Trade-Dangerous/commit/8348b0aa19d1f383e517f7b7df18df49c8e1befe))

### Fix

* fix: Hopefully actually fix Travis this time. ([`970d721`](https://github.com/eyeonus/Trade-Dangerous/commit/970d721c2b512fff096f4bc76c15716f35a03633))

* fix: Make Travis work again.

Also add new 3.8 and remove soon to be unsupported 3.4 python versions ([`13addad`](https://github.com/eyeonus/Trade-Dangerous/commit/13addad48d2bb5f58b7e5c09c0ebdd5eedd74bd0))

* fix: ensure folder exists before attempting to write file

fixes #78 ([`2de883f`](https://github.com/eyeonus/Trade-Dangerous/commit/2de883f62b1460c28da006d972da6225a9bd882f))


## v10.9.0 (2020-07-17)

### Fix

* fix: one more go at properly fixing required arguments. ([`79ba4f3`](https://github.com/eyeonus/Trade-Dangerous/commit/79ba4f3b65925098f5160e6042dd4e7336a15e69))

### Refactor

* refactor: remove redundant code. ([`bf27c3e`](https://github.com/eyeonus/Trade-Dangerous/commit/bf27c3e43f0644dbb572de3cd467766595d79790))


## v10.8.2 (2020-07-17)

### Fix

* fix: make certain hopRoute is a list. ([`27eba0d`](https://github.com/eyeonus/Trade-Dangerous/commit/27eba0d61895380058628fd0eeb6cdebe304fce6))


## v10.8.1 (2020-07-17)

### Feature

* feat: add &#39;--fleet-carrier&#39; (&#39;--fc&#39;) option

Functions exactly like &#39;--planetary&#39;, but for fleet carriers.

Allowed values are &#39;YN?&#39;

Fixes 74. ([`339b2af`](https://github.com/eyeonus/Trade-Dangerous/commit/339b2af4e58ef9296a84548605359517511425be))

### Fix

* fix: required args now pass correctly in gui ([`b21aba8`](https://github.com/eyeonus/Trade-Dangerous/commit/b21aba84766e9a7377875e89227eccd418f8814a))


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


## v10.7.1 (2020-06-30)

### Fix

* fix: always check for new populated systems dump. ([`cce11af`](https://github.com/eyeonus/Trade-Dangerous/commit/cce11afd8f7c398767efa9a29d4bd093ac3e95ac))

### Refactor

* refactor: don&#39;t turn off &#39;system&#39; when &#39;systemfull&#39; is on. ([`a2b9153`](https://github.com/eyeonus/Trade-Dangerous/commit/a2b9153d6e41cba97950fdd9187d22b0d64eef03))


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


## v10.6.3 (2020-06-30)

### Fix

* fix: Fleet Carriers can be in an unpopulated system.

Added &#34;Unknown Space&#34; system for FCs in a system not in the DB.
&#34;Unknown Space&#34; systems are added with x,y, and z pos of 0. ([`27ab8b3`](https://github.com/eyeonus/Trade-Dangerous/commit/27ab8b397b1276732f1b915cc956792b03bd47ea))

### Refactor

* refactor: Updated server address to use https. ([`9a77295`](https://github.com/eyeonus/Trade-Dangerous/commit/9a77295b39d9368f2ff824a814c701020a3d3ca9))


## v10.6.2 (2020-06-30)

### Documentation

* docs: Update README.md (#71)

http://elite.tromador.com/ ([`192502d`](https://github.com/eyeonus/Trade-Dangerous/commit/192502d6d9a443b6e6cee90faf24f24f3d61404e))

* docs: pyenv/pyenv#1375 with Mojave (#67)

Document fix for Mac users who use pyenv Python installation, to get the latest
tcl/tk version working on Mac OS 10.14.6 (Mojave). ([`2edbdf4`](https://github.com/eyeonus/Trade-Dangerous/commit/2edbdf4eec37e605d71a7e88fd4afd818c25e7d8))

### Performance

* perf: Raise warning rather than exiting. ([`3f0b6ff`](https://github.com/eyeonus/Trade-Dangerous/commit/3f0b6ff24982560fb8ccaf5e74d0dad1b2b28fdf))


## v10.6.1 (2019-09-01)

### Fix

* fix: Only run the color command on Windows machines.

It&#39;s not needed on *nix or OSX and throws shell errors when int&#39;s run on
OSX. ([`7538e98`](https://github.com/eyeonus/Trade-Dangerous/commit/7538e9869a225f0e94857900eea77fbe9cc0731a))


## v10.6.0 (2019-08-31)

### Feature

* feat: Color output (only implemented in &#39;run&#39; command thus far.)

When running TD in terminal (command prompt/ powershell for windows users), adding the &#39;--color&#39;  argument to the run command will output the text in color. Color output will be enabled for the other commands as time permits.

(Thanks go to skorn for idea and initial coding.) ([`3cf1dc8`](https://github.com/eyeonus/Trade-Dangerous/commit/3cf1dc8eb623f3a9776243ce38b6fc5405f5e9ea))

### Fix

* fix: missing argument in method call ([`004a6d8`](https://github.com/eyeonus/Trade-Dangerous/commit/004a6d853f89b1b605bd34e78fe2431e65d6f555))


## v10.5.7 (2019-08-31)

### Fix

* fix: Properly implement options with multiple choices.

Was comparing against the wrong var. ([`ba9a940`](https://github.com/eyeonus/Trade-Dangerous/commit/ba9a940dc102de7c0a0438106a83a967f972583b))

### Refactor

* refactor: Formatting fixes. (Indentation) ([`9da641b`](https://github.com/eyeonus/Trade-Dangerous/commit/9da641b38203ad44ba5d87a58d84b9372bc536cd))


## v10.5.6 (2019-08-31)

### Fix

* fix: append the argnames for required arguments

Don&#39;t know why I did that, but it was the wrong thing to do. ([`0617187`](https://github.com/eyeonus/Trade-Dangerous/commit/0617187874670630d32791ed7dce930362890f7d))


## v10.5.5 (2019-06-21)

### Fix

* fix: Remove unused imports ([`4049f57`](https://github.com/eyeonus/Trade-Dangerous/commit/4049f573e1d7c6e9f311582badf177ef7e60742c))


## v10.5.4 (2019-06-21)

### Fix

* fix: Use 127.0.0.1, not 127.2.0.1, Because Apple computers are evil.

Fixes #63 ([`1dacb3b`](https://github.com/eyeonus/Trade-Dangerous/commit/1dacb3b6816b6480c3360f8abea7bbb4bf2511c4))


## v10.5.3 (2019-06-20)

### Fix

* fix: Implement plugin options subwindow

Now you don&#39;t need to type in every option. Push the button, and a
window will pop up allowing you to simply select which options you&#39;d
like.

Plugin options which require a value, such as the filename to test json
importing with in the case of the edapi plugin&#39;s &#39;test&#39; option, will
show as a text field for typing that parameter in. ([`a471b7a`](https://github.com/eyeonus/Trade-Dangerous/commit/a471b7a107880c915f1ff14f8db63c829ab1217d))


## v10.5.2 (2019-06-17)

### Fix

* fix: Set width of tab fields, no more output weirdness.

Hooray. Figured it out. ([`dfca779`](https://github.com/eyeonus/Trade-Dangerous/commit/dfca7791a40c4e70b21a4a6cfc8aa4225c960b3e))


## v10.5.1 (2019-06-17)

### Fix

* fix: Make the gui actually work when TD is pip installed. ([`5c36944`](https://github.com/eyeonus/Trade-Dangerous/commit/5c3694442e5cbf977e5235dcb4b9345c320ef98b))


## v10.5.0 (2019-06-17)

### Documentation

* docs: Update copyright notices with current year.

Man there are a lot. I&#39;m considering removing all but the one on
trade.py and README.md ([`1cf29ad`](https://github.com/eyeonus/Trade-Dangerous/commit/1cf29ad183eaab61f4d417f09b2f26bc6c7e5237))

### Feature

* feat: Beta release of GUI

Just run &#34;trade gui&#34; and tell me what you think. ([`4d56509`](https://github.com/eyeonus/Trade-Dangerous/commit/4d565091aa081eebca1bcc5ccab941cdd0b75b3c))

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


## v10.4.7 (2019-05-28)

### Fix

* fix: Stop always using the template ship index when fallback enabled

Check to see if the attempt to download the ship index was successful,
and if so, do not use the template, even if the fallback option is
enabled. ([`54897cb`](https://github.com/eyeonus/Trade-Dangerous/commit/54897cb0e8ffb20c0fc6455f4bcdca482ff1f5ed))

### Refactor

* refactor: Update ship index to not use the beta site. ([`49ce095`](https://github.com/eyeonus/Trade-Dangerous/commit/49ce095416be1e505307f3bac14b4b5867c38c13))


## v10.4.6 (2019-05-23)

### Fix

* fix: Give TD web requests a User-Agent header.

Fixes #61 ([`0a10cec`](https://github.com/eyeonus/Trade-Dangerous/commit/0a10ceceebc4228b39494310d88b6997f8a36028))


## v10.4.5 (2019-05-23)

### Fix

* fix: Update ship index URL. ([`c455594`](https://github.com/eyeonus/Trade-Dangerous/commit/c4555942c2cca0da8a49a470f2165402f50e5457))


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


## v10.4.3 (2019-02-26)

### Fix

* fix: properly set profile save path

Need to make sure it works correctly with non-TDH profile saving too,
Jon.

Fixes #57 ([`55274fe`](https://github.com/eyeonus/Trade-Dangerous/commit/55274fefda798124714015f89d6dc803ce24544d))


## v10.4.2 (2019-02-26)

### Fix

* fix: unable to save tdh profile

Reverts change introduced unintentionally by
fca7f2698a5ac83dd4011c4dcd3379d9cbed0274 ([`248a4fb`](https://github.com/eyeonus/Trade-Dangerous/commit/248a4fba804e7ac99e279a678d622ce5acbc4577))


## v10.4.1 (2019-02-26)

### Fix

* fix: error when trying to insert rare items that already exist in table

In this case, I don&#39;t think &#34;INSERT OR REPLACE&#34; is a horrible idea. ([`20d64c6`](https://github.com/eyeonus/Trade-Dangerous/commit/20d64c6f999e0108f4f1e4e56f6ac92facc08a52))


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


## v10.3.1 (2019-02-25)

### Fix

* fix: skip stations that are not in the DB when importing listings

Thanks go to Bernd for the code work.

Fixes #56 ([`34220dc`](https://github.com/eyeonus/Trade-Dangerous/commit/34220dc3b201c4471f117a091944c0884f670c22))


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


## v10.2.2 (2019-02-15)

### Fix

* fix: Correctly check for $TD_EDDB

In python&#39;s &#39;x if true else y&#39;, x is evaluated first, then the if
statement is evaluated, and only when the if statement is false does y
get evaluated.

Path(os.environ.get(&#39;TD_EDDB&#39;) = NoneType) will cause the program to
error before even getting to the if statement. ([`1c4d186`](https://github.com/eyeonus/Trade-Dangerous/commit/1c4d186be29379217eab1d27cf72915c5c74e5c0))


## v10.2.1 (2019-02-15)

### Fix

* fix: avoid TypeError if TD_EDDB is not set

Path(None) raises a TypeError.
Test for missing TD_EDDB as well as set.

fixes #51 ([`cd41144`](https://github.com/eyeonus/Trade-Dangerous/commit/cd41144a1f875dda2fea189dc97831c5edd762ad))

### Style

* style: Restore whitespace to eddblink_plug.py ([`6d0de5f`](https://github.com/eyeonus/Trade-Dangerous/commit/6d0de5faba85dbe51f47f8e888b16d2c39a844ac))


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
```
([`d509fda`](https://github.com/eyeonus/Trade-Dangerous/commit/d509fda783970ee0754752a79369b4d36c346258))


## v10.1.2 (2019-02-14)

### Fix

* fix: Unable to save profile.&lt;current_time&gt;.json&#34; ([`fca7f26`](https://github.com/eyeonus/Trade-Dangerous/commit/fca7f2698a5ac83dd4011c4dcd3379d9cbed0274))


## v10.1.1 (2019-02-14)

### Fix

* fix: Unable to save tdh_profile.json ([`a2abe01`](https://github.com/eyeonus/Trade-Dangerous/commit/a2abe01ec25347191ac792f56ac966ff8533dfdc))


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

* Update .travis.yml ([`06c5adb`](https://github.com/eyeonus/Trade-Dangerous/commit/06c5adb47870d6df9c3ce4f5ab9d7de9126f7194))

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

### Pre-Semantic changes

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

* Fix #22 ([`80cdae9`](https://github.com/eyeonus/Trade-Dangerous/commit/80cdae94fef7a3af35acf1e66f225db9856c7b45))

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

### Legacy: (i.e., pre-eyeonus takeover)

See CHANGELOG.legacy.md