#!/usr/bin/env python3

import os
import sys
import time
import json
import sqlite3
import ssl
import html
import http
import requests
from urllib import request
from urllib import parse
from typing import List, Dict, Any

import argparse
import logging
import logging.config


class Gerrit:
    context = None
    host: str = None
    auth: None
    auth_basic: None
    auth_digest: None

    def __init__(self,
                 host,
                 user,
                 password,
                 insecure: bool = True,
                 verbose: bool = False):
        if not insecure:
            self.context = ssl._create_default_https_context()
        else:
            self.context = ssl._create_unverified_context()
        self.host = host
        self.auth = request.HTTPPasswordMgrWithDefaultRealm()
        self.auth.add_password(None, host, user, password)

        self.auth_basic = request.HTTPBasicAuthHandler(self.auth)
        self.auth_digest = request.HTTPDigestAuthHandler(self.auth)

        request.install_opener(
            request.build_opener(
                self.auth_basic, self.auth_digest,
                request.HTTPSHandler(debuglevel=verbose,
                                     context=self.context)))

    def url_for_change(self, number: str):
        return 'https://%s/#/c/%s/' % (self.host, number)

    def __get_url(self, path: str):
        path = path.replace(' ', '+').replace('"', "%22")
        if path.startswith("/"):
            url = 'https://%s/a%s' % (self.host, path)
        else:
            url = 'https://%s/a/%s' % (self.host, path)
        return url

    def __get_content(self, res):
        if res.getcode() == requests.codes.ok:
            return res.read().decode('utf-8').replace(")]}'\n", "")
        else:
            res.raise_for_status()

    def __get_json(self, res):
        content = self.__get_content(res)
        return json.loads(content)

    def get(self, url):
        url = self.__get_url(url)
        logging.debug('GET %s' % (url))
        req = request.Request(url, method="GET")
        return request.urlopen(req)

    def get_json(self, url):
        res = self.get(url)
        return self.__get_json(res)

    def search(self, path, search: List[str], queries: List[str] = []):
        q = ['q=%s' % ('+'.join(search))] + queries
        url = '%s?%s' % (path, '&'.join(q))
        return self.get_json(url)

    def query_changes(self, search: List[str], queries: List[str] = []):
        return self.search('/changes/', search, queries)

    def query_changes_between(self,
                              search: List[str],
                              queries: List[str],
                              since: str = None,
                              until: str = None):
        changes = []
        while True:
            range = []
            if since is not None and since != '':
                range.append('since:"%s"' % since)
            if until is not None and until != '':
                range.append('until:"%s"' % until)
            res = self.query_changes(search + range, queries)

            def change_exist(id):
                for ch in changes:
                    if ch['id'] == id:
                        return True
                return False

            for chg in res:
                if change_exist(chg['id']):
                    continue
                changes.append(chg)

            if len(res) < 500:
                break
            until = res[500 - 1]['updated']
        return changes

    def get_change(self, id: str):
        url = '/changes/%s' % (id)
        res = self.get(url)
        return self.__get_json(res)

    def get_change_detail(self, id: str):
        url = '/changes/%s/detail' % (id)
        res = self.get(url)
        return self.__get_json(res)

    def get_change_cherry_pick(self, change, branch_to: str = None):
        searches = [
            'project:%s' % (change['project']),
            'change:%s' % (change['change_id']),
            '-change:%d' % (change['_number']), '-is:abandoned'
        ]
        if branch_to is not None and branch_to != '':
            searches.append('branch:%s' % (branch_to))
        return self.query_changes(searches, ['O=a'])

    def get_change_cherry_pick_by_id(self, id: str, branch_to: str = None):
        change = self.get_change(id)
        return self.get_change_cherry_pick(change, branch_to)


class GerritCache:
    conn: sqlite3.Connection = None

    def __init__(self, db: str):
        dir = os.path.dirname(os.path.realpath(__file__))
        if db is None or db == "":
            db = os.path.join(dir, '.cache.db')
        self.conn = sqlite3.connect(db)
        with open(os.path.join(dir, "schema/tbl_changes.sql")) as f:
            self.conn.executescript(f.read())
        self.conn.commit()

    @staticmethod
    def __timestamp(value: str):
        if value is not None:
            return time.mktime(
                time.strptime(value.split('.')[0], '%Y-%m-%d %H:%M:%S'))
        return None

    def insert(self, change):
        cur = self.conn.cursor()

        current_revision = change['revisions'][change['current_revision']]
        parent = None
        parent2 = None
        if len(current_revision['commit']['parents']) > 0:
            parent = current_revision['commit']['parents'][0]['commit']
        if len(current_revision['commit']['parents']) > 1:
            parent2 = current_revision['commit']['parents'][1]['commit']

        cur.execute(
            '''INSERT OR REPLACE INTO tbl_changes
                (number, project, branch, change_id, status, update_time,
                 parent, parent2, author, author_date, committer, committer_date,
                 data)
                values (?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?,
                        ?)''',
            (int(change['_number']), change['project'], change['branch'],
             change['change_id'], change['status'],
             self.__timestamp(change['updated']), parent, parent2,
             current_revision['commit']['author']['name'],
             self.__timestamp(current_revision['commit']['author']['date']),
             current_revision['commit']['committer']['name'],
             self.__timestamp(current_revision['commit']['committer']['date']),
             json.dumps(change)))

    def update(self, change, commit: bool = True):
        cur = self.conn.cursor()
        cur.execute('''SELECT status from tbl_changes where number = ?''',
                    (int(change['_number']), ))
        row = cur.fetchone()
        if row is None or row[0] != 'MERGED':
            self.insert(change)
            if commit:
                self.conn.commit()

    def update_list(self, changes):
        for chg in changes:
            self.update(chg, False)
        self.conn.commit()

    def get(self, project: str, branch: str, change_id: str):
        cur = self.conn.cursor()
        cur.execute(
            '''SELECT data from tbl_changes where
                       project = ? and branch = ? and change_id = ?''', (
                project,
                branch,
                change_id,
            ))
        row = cur.fetchone()
        return json.loads(row[0]) if row else None

    def get_by_number(self, number: str):
        cur = self.conn.cursor()
        cur.execute(
            'SELECT data from tbl_changes where number = ?',
            (int(number)),
        )
        row = cur.fetchone()
        return json.loads(row[0]) if row else None

    def get_by_id(self, id: str):
        items = id.split("~")
        return self.get(items[0].replace("%2F", "/"), items[1], items[2])

    def get_cherry_pick(self, project: str, change_id: str, number: str):
        cur = self.conn.cursor()
        cur.execute(
            '''SELECT data from tbl_changes where
                       project = ? and change_id = ? and number != ?
                       and status != 'ABANDONED' ''', (
                project,
                change_id,
                int(number),
            ))
        changes = []
        for row in cur.fetchall():
            changes.append(json.loads(row[0]))
        return changes

    def get_cherry_pick_to(self, project: str, change_id: str, number: str,
                           branch_to: str):
        cur = self.conn.cursor()
        cur.execute(
            '''SELECT data from tbl_changes where
                       project = ? and change_id = ? and number != ?
                       and status != 'ABANDONED'
                       and branch = ? ''',
            (project, change_id, int(number), branch_to))
        changes = []
        for row in cur.fetchall():
            changes.append(json.loads(row[0]))
        return changes


class GerritCached(Gerrit):
    cache: GerritCache = None
    cache_match: int = None
    cache_miss: int = None
    only_cache: bool = None

    def __init__(self,
                 cache,
                 host,
                 user,
                 password,
                 insecure: bool = True,
                 verbose: bool = False,
                 only_cache: bool = False):
        super().__init__(host, user, password, insecure, verbose)
        self.cache = cache
        self.cache_match = 0
        self.cache_miss = 0
        self.only_cache = only_cache

    def __update_cache(self, changes):
        if not isinstance(changes, list):
            self.cache.update(changes)
        else:
            self.cache.update_list(changes)

    def __cache__(func):
        def __decorated_update_cache(self, *args, **kwargs):
            match = self.cache_match
            changes = func(self, *args, **kwargs)
            if match != self.cache_miss:
                self.__update_cache(changes)
            return changes

        return __decorated_update_cache

    def search(self, path, search: List[str], queries: List[str] = []):
        return super().search(path, search, queries + ['O=a'])

    @__cache__
    def query_changes(self, search: List[str], queries: List[str] = []):
        return self.search('/changes/', search, queries)

    @__cache__
    def get_change(self, id: str):
        res = self.cache.get_by_id(id)
        if res:
            self.cache_match += 1
            return res
        self.cache_miss += 1
        return super().get_change(id)

    def get_change_cherry_pick(self, change, branch_to: str = None):
        if branch_to:
            changes = self.cache.get_cherry_pick_to(change['project'],
                                                    change['change_id'],
                                                    change['_number'],
                                                    branch_to)
        else:
            changes = self.cache.get_cherry_pick(change['project'],
                                                 change['change_id'],
                                                 change['_number'])
        if len(changes) > 0 or self.only_cache:
            self.cache_match += 1
            return changes
        self.cache_miss += 1
        return super().get_change_cherry_pick(change, branch_to)


class BranchGraph:
    config = None

    def __init__(self, config):
        self.config = config

    def get_since(self, branch: str):
        time = ''
        if branch in self.config:
            if create_time in self.config[branch]:
                time = self.config[branch]['create_time']
        if time != '':
            return time
        return '1970-01-01 00:00:00'

    def find_since(self, branch: str, branch_to: str):
        graph_1: List = self.__build_graph(branch)
        graph_2: List = self.__build_graph(branch_to)

        index = 0
        while index < len(graph_1) and index < len(graph_2):
            if graph_1[index]['name'] == graph_2[index]['name'] and \
                graph_1[index]['time'] == graph_2[index]['time']:
                index += 1
            else:
                break

        if index < len(graph_1):
            return graph_1[index]['time']
        elif index < len(graph_2):
            return graph_2[index]['time']
        return None

    def __build_graph(self, branch: str):
        graph = []
        while branch != '':
            if branch in self.config:
                graph.insert(0, { 'name': branch, 'time': self.config[branch]['create_time'] })
                branch = self.config[branch]['parent']
            else:
                break
        return graph

class GerritTools:
    cache: GerritCache = None
    gerrit: GerritCached = None
    branches: BranchGraph = None

    def __init__(self, config, branch_config):
        self.cache = GerritCache(config.get('cache'))
        self.gerrit = GerritCached(self.cache, config['host'], config['user'],
                                   config['passwd'], config['insecure'],
                                   config['verbose_http'],
                                   config.get('only_cache'))
        self.branches = BranchGraph(branch_config)

    def __md_escape(self, s: str):
        return s.replace("[", "\\[").replace("]", "\\]").replace(
            "(", "\\(").replace(")", "\\)")

    def cherry_pick_list(self,
                         project: str,
                         branch: str,
                         branch_to: str,
                         since: str = None,
                         until: str = None):
        searches = ['project:%s' % project, 'branch:%s' % branch, 'is:merged']

        if since is None or since == '':
            since = self.branches.find_since(branch, branch_to)

        logging.debug('Since %s, until %s' %(since, until))
        changes = self.gerrit.query_changes_between(searches, [], since, until)

        logging.debug('Got %d commits' % (len(changes)))

        print("# %s commits cherry pick list" % (project))
        print("| %s | %s | " % (branch, branch_to))
        print("|----|----|")

        for change in changes:
            print("| ", end="")
            print(
                '<a href="%s">%s</a> - **%s**/%s' %
                (self.gerrit.url_for_change(change['_number']),
                 self.__md_escape(html.escape(change['subject'])),
                 change['revisions'][change['current_revision']]['commit']
                 ['author']['name'], change['revisions']
                 [change['current_revision']]['commit']['committer']['date']),
                end='')
            print(" | ", end='')

            cherries = self.gerrit.get_change_cherry_pick(change, branch_to)
            for cherry in cherries:
                if cherry['branch'] != branch_to:
                    continue
                print('<a href="%s">%s</a> - **%s**/%s' %
                      (self.gerrit.url_for_change(cherry['_number']),
                       self.__md_escape(html.escape(cherry['subject'])),
                       cherry['revisions'][cherry['current_revision']]
                       ['commit']['author']['name'],
                       cherry['revisions'][cherry['current_revision']]
                       ['commit']['committer']['date']),
                      end='')
                break

            print(" |")

    def update_cache(self,
                     project: str,
                     branch: str,
                     since: str = None,
                     until: str = None):
        searches = [
            'project:%s' % project,
            'branch:%s' % branch, '-is:abandoned'
        ]
        if since is None or since == '':
            since = self.branches.get_since(branch)

        info.debug('Since %s, until %s' %(since, until))
        changes = self.gerrit.query_changes_between(searches, [], since, until)
        info.debug('Got %d commits' % (len(changes)))

    @staticmethod
    def __cherry_pick_list(tools, args):
        tools.cherry_pick_list(args.project, args.branch, args.branch_to,
                               args.since, args.until)

    @staticmethod
    def __update_cache(tools, args):
        tools.update_cache(args.project, args.branch, args.since, args.until)

    @staticmethod
    def usage(subparsers: argparse._SubParsersAction):
        # cherry-pick-list
        cmd = subparsers.add_parser('cherry-pick-list',
                                    help='Get cherry-pick list',
                                    add_help=True)
        cmd.add_argument('project', help='Project name')
        cmd.add_argument('branch', help='Branch name')
        cmd.add_argument('branch_to', help='Cherry-pick target branch name')
        cmd.add_argument(
            'since',
            nargs='?',
            help=
            'Change modified time after(format: 2006-01-02[ 15:04:05[.890])',
            default='')
        cmd.add_argument(
            'until',
            nargs='?',
            help=
            'Change modified time until(format: 2006-01-02[ 15:04:05[.890])',
            default='')
        cmd.set_defaults(func=GerritTools.__cherry_pick_list)

        # update_cache
        cmd = subparsers.add_parser('update-cache',
                                    help='Update cache',
                                    add_help=True)
        cmd.add_argument('project', help='Project name')
        cmd.add_argument('branch', help='Branch name')
        cmd.add_argument(
            'since',
            nargs='?',
            help=
            'Change modified time after(format: 2006-01-02[ 15:04:05[.890])',
            default='')
        cmd.add_argument(
            'until',
            nargs='?',
            help=
            'Change modified time until(format: 2006-01-02[ 15:04:05[.890])',
            default='')
        cmd.set_defaults(func=GerritTools.__update_cache)


def _get_conf_file(conf: str, filename: str):
    path = os.path.dirname(os.path.realpath(__file__))
    dirs = ["./", path, "~/"]
    files = [conf]
    for dir in dirs:
        files += [
            os.path.join(dir, filename),
            os.path.join(dir, '.%s' % filename)
        ]
    for f in files:
        if f and os.path.exists(f):
            return f
    return None

def get_conf_file(conf: str):
    return _get_conf_file(conf, 'gerrit.config.json')

def get_branch_conf_file(conf: str):
    return _get_conf_file(conf, 'branch.config.json')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument('-c', "--conf", help='Config file')
    parser.add_argument('-b', '--branch_conf', help='Config file for branch')
    parser.add_argument('-l', "--log", help='Log config file')
    parser.add_argument('-C', '--cache', help='Cache database')
    parser.add_argument('--only_cache',
                        action='store_true',
                        help='Read data from cache only')
    parser.add_argument('-o', '--out', help='Output file(default: stdout)')
    parser.add_argument('-H', '--host', help='Gerrit host address')
    parser.add_argument('-U',
                        '--user',
                        help='User name for gerrit',
                        default="")
    parser.add_argument('-P',
                        '--passwd',
                        help='Password for gerrit',
                        default="")
    parser.add_argument('-I',
                        '--insecure',
                        action='store_true',
                        help='Insecure https')
    parser.add_argument('-V',
                        "--verbose",
                        action='store_true',
                        help='Show debug log')
    parser.add_argument('-VV',
                        '--verbose_http',
                        action='store_true',
                        help='Show http log')
    GerritTools.usage(parser.add_subparsers())

    args = parser.parse_args()

    config = {
        'insecure': False,
        'verbose': False,
        'verbose_http': False,
        'only_cache': False,
    }
    with open(get_conf_file(args.conf)) as f:
        config.update(json.load(f))

    branch_config = {}
    with open(get_branch_conf_file(args.branch_conf)) as f:
        branch_config.update(json.load(f))

    if args.host:
        config['host'] = args.host
    if args.user:
        config['user'] = args.user
    if args.passwd:
        config['passwd'] = args.passwd
    if args.insecure:
        config['insecure'] = args.insecure
    if args.verbose:
        config['verbose'] = args.verbose
    if args.verbose_http:
        config['verbose_http'] = args.verbose_http
    if args.only_cache:
        config['only_cache'] = args.only_cache

    if 'host' not in config or config['host'] == "":
        print('Missing argument: host', file=sys.stderr)
        sys.exit(1)

    if args.out:
        sys.stdout = open(args.out, 'w')

    if args.log:
        logging.config.fileConfig(args.log, disable_existing_loggers=True)
    else:
        level = logging.INFO if not args.verbose else logging.DEBUG
        logging.basicConfig(level=level,
                            format='[%(levelname)-5.5s] %(message)s')
        logging.getLogger().setLevel(level)

    gerrit_tools = GerritTools(config, branch_config)
    args.func(gerrit_tools, args)

    sys.stdout.flush()

    logging.debug(
        'Cache match/miss: %d/%d' %
        (gerrit_tools.gerrit.cache_match, gerrit_tools.gerrit.cache_miss))
