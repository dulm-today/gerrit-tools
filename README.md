# Gerrit tools

Tools that can list commits cherry-picked from one branch to another base on Gerrit HTTP API.

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


## Configure file

Configure file search paths:

* `./gerrit.config.json`
* `./.gerrit.config.json`
* `~/gerrit.config.json`
* `~/.gerrit.config.json`

Configure file schema:

```json
{
    "host": "192.168.120.246",
    "user": "user",
    "passwd": "gerrit api password",
    "verbose": 0,
    "insecure": true
}
```

> Password generated in `http://<gerrit server address>/#/settings/http-password`
