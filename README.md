# Gerrit tools

Tools that can list commits cherry-picked from one branch to another base on Gerrit HTTP API.

## Tutorial

* Config [`gerrit.json5`](#gerrit_config)
* Config [`branch.json5`](#branch_config)
* Run `gerrit.py` to list the commits that in **branch_from**, or cherry-picked to **branch_to** in markdown format.

  ```shell
  ./gerrit.py cherry-pick-list <repo> <branch_from> <branch_to> > markdown.md
  ```

* Use `markdownConverter` convert markdown to html.

  ```shell
  markdownConverter --html markdown.md
  ```

## Usage

Run `./gerrit.py -h` to show help messages:

```
usage: gerrit.py [-h] [-c CONF] [-l LOG] [-C CACHE] [--only_cache] [-H HOST] [-U USER] [-P PASSWD] [-I] [-V] [-VV] {cherry-pick-list,update-cache} ...

positional arguments:
  {cherry-pick-list,update-cache}
    cherry-pick-list    Get cherry-pick list
    update-cache        Update cache

optional arguments:
  -h, --help            show this help message and exit
  -c CONF, --conf CONF  Config file
  -l LOG, --log LOG     Log config file
  -C CACHE, --cache CACHE
                        Cache database
  --only_cache          Read data from cache only
  -H HOST, --host HOST  Gerrit host address
  -U USER, --user USER  User name for gerrit
  -P PASSWD, --passwd PASSWD
                        Password for gerrit
  -I, --insecure        Insecure https
  -V, --verbose         Show debug log
  -VV, --verbose_http   Show http log
```

Supported subcommands:

* cherry-pick-list
* update-cache

Run `./gerrit.py cherry-pick-list -h` to show subcommand help information.



Examples:

`./gerrit.py cherry-pick-list 'GRP260X/grp_system' master GRP260X_FP2_GA '2021-06-03 10:16:00' > grp_system.md`

This will list all commits since **2021-06-03 10:16:00** in branch **master**, and all commits **cherry-picked** to branch **GRP260X_FP2_GA**(Not all commits in branch GRP260X_FP2_GA).


## Config file

### <span id='gerrit_config'>Gerrit config file</span>

Config file search paths:

* `./gerrit.json5`
* `./config/gerrit.json5`
* `{Path of gerrit.py}/gerrit.json5`
* `{Path of gerrit.py}/config/gerrit.json5`
* `~/.config/gerrit-tools/gerrit.json5`

Config file example:

```json
[
{
    "host": "192.168.120.246",
    "user": "user",
    "passwd": "gerrit api password",
    "verbose": 0,
    "insecure": true
}
]
```

> **Password generated in `https://<gerrit server address>/#/settings/http-password`**

### <span id='branch_config'>Branch config file</span>

Config file search paths:

* `./branch.json5`
* `./config/branch.json5`
* `{Path of gerrit.py}/branch.json5`
* `{Path of gerrit.py}/config/branch.json5`
* `~/.config/gerrit-tools/branch.json5`

Config file example:

```json
{
    "master": {
        "parent": "",
        "create_time": "2019-10-08 00:00:00"
    },
    "GRP260X_FP2_GA": {
        "parent": "master",
        "create_time": "2021-06-03 00:00:00"
    },
    "GRP260X_FP3_GA": {
        "parent": "master",
        "create_time": "2023-01-03 00:00:00"
    },
    "GHP6XX_master": {
        "parent": "GRP260X_FP2_GA",
        "create_time": "2022-01-21 00:00:00"
    },
    "GHP6XX_FP1_GA": {
        "parent": "GHP6XX_master",
        "create_time": "2022-06-28 00:00:00"
    },
    "GSC": {
        "parent": "GRP260X_FP2_GA",
        "create_time": "2022-01-21 00:00::00"
    },
    "GSC_FP1_GA": {
        "parent": "GSC",
        "create_time": "2022-08-19 00:00:00"
    },
    "GSC_FP2_GA": {
        "parent": "GSC",
        "create_time": "2022-12-22 00:00:00"
    }
}
```
