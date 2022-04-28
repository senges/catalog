#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
# Author : @senges
# Version : March 2022
# Description : Catalog, a quick tool installer
# =============================================================================

import os
import re
import sys
import json
import shutil
import argparse
import datetime

from glob import glob
from pathlib import Path
from subprocess import STDOUT, check_call
from urllib.request import Request, urlopen

CONFIG_FILES = glob( '%s/static/*.json' % os.path.dirname(os.path.realpath(__file__)) )

class Config:
    VERBOSE = False
    DEBUG = False
    FORCE = False
    DRY_RUN = False
    DEPENDENCIES = 'fail'
    CACHE = False

    @classmethod
    def ignore_dependencies(cls):
        return cls.DEPENDENCIES == 'ignore'

    @classmethod
    def satisfy_dependencies(cls):
        return cls.DEPENDENCIES == 'satisfy'

class Command:
    def __init__(self, args: [str] = [], cwd: str = None):
        self.args = args
        self.cwd = cwd

    def __str__(self):
        cmd = ' '.join(self.args)
        return '[cwd=%s] %s' % (self.cwd, cmd)

class CommandSet:
    def __init__(self, args: [str] = [], cwd: str = None):
        self.commands = []
        if args: self.add(args, cwd)

    def add(self, args: [str], cwd: str = None):
        args = Command(args, cwd)
        self.commands.append(args)

    def update(self, cmdset: 'CommandSet'):
        self.commands += cmdset.commands

class Installer:
    def __init__(self, tool: str, config: dict = {}):

        self.wd = '/opt/%s' % tool
        self.config = config.get(tool, {})
        self.config_map = config
        self.tool = tool
        self.builtins = builtins()

        self.mkpath = lambda x: os.path.join(self.wd, x)
        self.expand = lambda x: x if Config.DRY_RUN else glob(x)[0]

        self.functions_mapper = {
            'apt'   : self._apt,
            'pip'   : self._pip,
            'npm'   : self._npm,
            'go'    : self._go,
            'wget'  : self._wget,
            'link'  : self._link,
            'rm'    : self._rm,
            'run'   : self._run,
            'make'   : self._make,
            'git'   : self._git,
            'shell' : self._shell,
            'extract' : self._extract,
            'github_release' : self._github_release
        }

    @classmethod
    def is_installed(cls, name):
        path = os.path.join('/opt/.catalog/tools', name)
        return os.path.exists(path)

    def init(self):
        try:
            Path( '/opt/.catalog/bin' ).mkdir(exist_ok = True, parents = True)
            Path( '/opt/.catalog/tools' ).mkdir(exist_ok = True, parents = True)
            Path( self.wd ).mkdir(exist_ok = True, parents = True)
        except PermissionError:
            print('[!] Got permission denied on \'/opt\' folder.')
            exit(1)

        link = self._link({
            'name' : 'catalog',
            'target' : os.path.join(self.wd, 'catalog.py')
        })

        for cmd in link.commands:
            verbose( str(cmd) )
            shell_run( cmd )
            verbose('=> Ok')

    def install(self):
        # Tool is already installed
        if self.is_installed(self.tool):
            if Config.FORCE and not Config.DRY_RUN:
                shutil.rmtree( self.wd )
            else:
                print('\n[~] %s already installed, skipping' % self.tool)
                return

        # Tool has no install candidate
        if not self.config:
            print('\n[~] %s is not available for install, skipping' % self.tool)
            return

        print('\n[+] Installing ' + self.tool)

        # Install dependencies first if any
        for dependency in self.config.get('dependencies', []):
            self._dependency(dependency)

        # Create working directory
        if not Config.DRY_RUN:
            Path( self.wd ).mkdir(exist_ok = True, parents = True)
        
        for step in self.config.get('steps'):
            action = step.get('type')
            
            if not action in self.functions_mapper:
                print('[-] %s step type does not exist. Aborting.' % action)
                break

            cmdset = self.functions_mapper[ action ](step)
            
            for cmd in cmdset.commands:
                verbose( str(cmd) )
                if not Config.DRY_RUN: 
                    shell_run( cmd )
                    verbose('=> Ok')

        # Keep trace of tool installation
        if not Config.DRY_RUN:
            trace = os.path.join('/opt/.catalog/tools', self.tool)
            with open(trace, 'w+') as f:
                f.write( str(datetime.datetime.now()) )

    # Check that dependency is satisfied
    def _dependency(self, name: str):
        if name in self.builtins: 
            return

        if self.is_installed(name): 
            return

        if Config.satisfy_dependencies():
            verbose('\n------ Installing dependency %s ------' % name)
            Installer(name, self.config_map).install()
            verbose('\n------ ENDOF - %s ------' % name)
            return

        elif Config().ignore_dependencies():
            print('\n[i] Ignoring unsatisfied dependency ' + name)
            return

        print('[!] Unsatisfied dependency : %s' % name)
        exit(1)
                
    def _apt(self, step: dict) -> CommandSet:
        pkg = step.get('packages')
        cmdset = CommandSet()

        # If any custom repo source to add
        if source := step.get('source'):
            repo = source.get('repository')
            key = source.get('key')
            sources = []

            # Download pgp key
            cmdset.update(
                    self._wget({
                    'url' : key
                })
            )

            _, keyname = os.path.split(key)

            # Add pgp key
            cmdset.add(['apt-key', 'add', self.mkpath(keyname)])

            # Remove pgp key file
            cmdset.update(
                self._rm({
                    'selectors' : [ keyname ]
                })
            )

            # Load installed source list
            try:
                with open('/etc/apt/sources.list.d/catalog.list', 'r') as f:
                    while line := f.readline():
                        sources.append(line.rstrip())
            except FileNotFoundError:
                pass

            # Avoid duplicates
            if repo not in sources:
                with open('/etc/apt/sources.list.d/catalog.list', 'a') as f:
                    f.write(repo + '\n')

        if cmdset.commands or not Config.CACHE:
            cmdset.add( ['apt', 'update'] )
            Config.CACHE = True

        cmdset.add( ['apt', 'install', '-y', '--no-install-recommends'] + pkg )

        return cmdset

    def _pip(self, step: dict) -> CommandSet:
        self._dependency("pip3")

        if pkg := step.get('packages'):
            cmd = ['pip3', 'install'] + pkg
            return CommandSet(cmd)
            
        requirements = step.get('file')
        requirements = self.mkpath(requirements)
        cmd = ['pip3', 'install', '-r', requirements]

        return CommandSet(cmd)

    def _go(self, step: dict) -> CommandSet:
        self._dependency("golang")
        package = step.get('package')

        return CommandSet(['go', 'install', '-v', package])

    def _npm(self, step: dict) -> CommandSet:
        self._dependency("npm")

        packages = step.get('packages')
        cmdset = CommandSet()

        for package in packages:
            cmdset.add( ['npm', 'install', '--prefix', self.wd, package] )
            cmdset.update(
                self._link({
                    'name' : package,
                    'target' : os.path.join(self.wd, 'node_modules/.bin/%s' % package)
                })
            )

        return cmdset

    def _wget(self, step: dict) -> CommandSet:
        self._dependency("wget")

        url = step.get('url')
        outfile = step.get('outfile')

        if outfile:
            filename = outfile
        else:
            _, filename = os.path.split(url)

        path = os.path.join(self.wd, filename)
        cmd = ['wget', '-O', path, '--no-check-certificate', url]

        return CommandSet(cmd)

    def _link(self, step: dict) -> CommandSet:
        name = step.get('name')
        
        target = step.get('target')
        target = self.mkpath(target)
        target = self.expand(target)

        cmdset = CommandSet()
        cmdset.add([ 'chmod', '+x', target ])
        cmdset.add([ 'ln', '-fs', target, f'/opt/.catalog/bin/{name}' ])

        return cmdset

    def _make(self, step: dict) -> CommandSet:
        self._dependency("make")

        arguments = step.get('arguments')
        path = step.get('path')

        cmd = [ 'make' ]

        if path:
            path = self.mkpath(path)
            path = self.expand(path)
            cmd += ['-C', path]

        if arguments:
            cmd += arguments
        
        return CommandSet(cmd)

    # Broken glob selecor.
    # Need to be fixed as not functionnal yet.
    def _rm(self, step: dict) -> CommandSet:
        selectors = step.get('selectors')
        path = '%s/{%s}' % (self.wd, ','.join(selectors))

        return CommandSet([ 'rm', '-rf', path ])

    def _git(self, step: dict) -> CommandSet:
        self._dependency("git")
        
        repo = step.get('repository')
        clean = step.get('clean')

        if not clean:
            clean = []

        cmdset = CommandSet()
        cmdset.add([ 'git', 'clone', '--depth', '1', repo, self.wd ])
        cmdset.update(
            self._rm({
                'selectors' : ['.git*','*.md','.travis.yml'] + clean
            })
        )

        return cmdset

    def _github_release(self, step: dict) -> CommandSet:
        self._dependency("git")
        self._dependency("wget")

        repo     = step.get('repository') 
        artifact = step.get('artifact') 
        outfile  = step.get('outfile')

        api = 'https://api.github.com/repos/%s' % repo
        url = 'https://github.com/%s' % repo
        
        try:
            request  = Request('%s/releases' % api)
            response = urlopen( request )
            data     = json.load(response)
            tag      = data[0]['tag_name']
            # Probably not super good (see knative)
            latest   = re.sub('[^\d\.]', '', tag)
        except:
            print('[!] Could not properly load url %s/releases' % api)
            exit(1)

        artifact = artifact.replace('{{latest}}', latest)

        # Github API has been a pain in the a** since the beginning.
        # Sticking to it is fastidious and provide complicated inconvenient code.
        # Browser download works like a charm, I will focus on this solution for now.

        if artifact.startswith(('tar.gz@', 'zip@')):
            form, version = artifact.split('@')
            url = '%s/archive/refs/tags/v%s.%s' % (url, version, form)
        else:
            url = '%s/releases/download/%s/%s' %  (url, tag, artifact)

        cmd = [ 'wget', url, '-O', self.mkpath(outfile) ]
        cmd.append('--retry-connrefused')
        cmd.append('--waitretry=5')
        cmd.append('--tries=2')

        return CommandSet(cmd)

    def _run(self, step: dict) -> CommandSet:
        cwd = step.get('cwd', False)
        cwd = self.mkpath(cwd)
        cwd = self.expand(cwd)
        
        path = step.get('file')
        path = self.mkpath(path)
        path = self.expand(path)

        args = step.get('arguments', [])
        args = [ x.replace('{{pwd}}', self.wd) for x in args ]

        cmdset = CommandSet()
        cmdset.add([ 'chmod', '+x', path ])
        cmdset.add([path] + args, cwd)

        return cmdset

    def _shell(self, step: dict) -> CommandSet:
        return step.get('cmd')

    def _extract(self, step: dict) -> CommandSet:
        
        compression = step.get('compression')
        remove      = step.get('remove')
        archive     = step.get('archive')
        archive     = self.mkpath(archive)
        archive     = self.expand(archive)
        cmdset = CommandSet()

        if compression == 'tgz':
            cmdset.add( untar(archive, self.wd) )
        elif compression == 'targz':
            cmdset.add( untargz(archive, self.wd) )
        elif compression == 'zip':
            self._dependency("zip")
            cmdset.add( unzip(archive, self.wd) )
        else:
            raise KeyError()

        if remove:
            cmdset.add(['rm', '-f', archive])

        return cmdset

def shell_run(cmd: Command):
    env = os.environ
    
    env['GOPATH'] = env['HOME'] + '/.go'            # To update with /opt managed folder
    env['PYTHONPATH'] = env['HOME'] + '/.python'    # To update with /opt managed folder
    
    try:
        check_call(
            args = cmd.args,
            stdout = open( '/var/log/cata.log', 'a' ), 
            stderr = STDOUT,
            env = env,
            cwd = cmd.cwd
        )
    except Exception as e:
        with open('/var/log/cata.log', 'r') as f:
            debug(f.read())

        debug(e)
        print('[!] Command execution has failed.')
        print('[!] Logs are availables at /var/log/cata.log')
        exit(1)

def unzip(archive: str, target: str) -> [str]:
    return ['unzip', archive, '-d', target]

def untar(archive: str, target: str) -> [str]:
    return ['tar', '-vxf', archive, '-C', target]

def untargz(archive: str, target: str) -> [str]:
    return ['tar', '-vzxf', archive, '-C', target]

# List builtins tools available in $PATH
def builtins() -> [str]:
    envpath = os.environ.get('PATH', [])
    envpath = envpath.split(':')
    builtins = []

    for path in envpath:
        builtins += ls(path)
    
    return builtins

# List (only) files in one folder
def ls(folder: str) -> [str]:
    _, _, files = next(os.walk(folder), (None, None, []))
    return files

def verbose(msg: str):
    if Config.VERBOSE:
        print(msg)

def debug(msg: str):
    if Config.DEBUG:
        print(msg)

def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--infile', help = 'input tool list file')
    parser.add_argument('-a', '--available', help = 'list available tools and exit', action = 'store_true')
    parser.add_argument('-l', '--list', help = 'list installed tools and exit', action = 'store_true')
    parser.add_argument('-f', '--force', help = 'force tool reinstall if present', action = 'store_true')
    parser.add_argument('-v', '--verbose', help = 'verbose mode', action = 'store_true')
    parser.add_argument('--init', help = 'setup catalog basic requirements', action = 'store_true')
    parser.add_argument('--debug', help = 'run catalog in debug mode', action = 'store_true')
    # parser.add_argument('-d', '--dind', help = 'use docker in docker provided installers (pip, go, npm..)', action = 'store_true')
    parser.add_argument('--preserve-cache', help = 'do not clear any installation cache', action = 'store_true')
    parser.add_argument('--dry-run', help = 'run catalog in verbose but do not install anything', action = 'store_true')
    parser.add_argument('--dependencies', help = 'dependencies behavior', default = 'satisfy', choices = ['fail', 'ignore', 'satisfy'])
    # parser.add_argument('--keep-installers', help = 'keep any installer', action = 'store_true')
    parser.add_argument('tools', metavar = 'TOOL_NAME', nargs = '*')

    args = parser.parse_args()

    Config.VERBOSE = args.verbose
    Config.DEBUG = args.debug
    Config.FORCE = args.force
    Config.DRY_RUN = args.dry_run
    Config.DEPENDENCIES = args.dependencies

    # Dry run infer verbose mode and dependency ignore
    if Config.DRY_RUN: 
        Config.VERBOSE = True
        Config.DEPENDENCIES = 'ignore'

    # If catalog init
    if args.init:
        Installer('catalog').init()
        exit(0)

    config_map = dict()
    tool_list = args.tools

    # Load config files
    try:
        for cf in CONFIG_FILES:
            with open(cf, 'rb') as f:
                config = json.load(f)
                config_map = { **config_map, **config }
    except:
        raise Exception('Error loading config files')
        

    # List available installs and exit
    if args.available:
        available = sorted([x for x, _ in config_map.items()], key = str.casefold)
        print( '\n'.join( available ) )
        exit(0)

    # List installed tools and exit
    if args.list:
        tools = ls('/opt/.catalog/tools')
        print( '\n'.join(sorted( tools, key = str.casefold )))
        exit(0)

    if args.infile:
        try:
            # Load tool file
            with open( args.infile ) as f:
                while tool := f.readline().rstrip():
                    tool_list.append(tool)
        except:
            raise Exception('Error loading tool list')

    # Make sure installation folders are ready
    try:
        Path( '/opt/.catalog/bin' ).mkdir(exist_ok = True, parents = True)
        Path( '/opt/.catalog/tools' ).mkdir(exist_ok = True, parents = True)
    except PermissionError:
        print('[!] Got permission denied on \'/opt\' folder.')
        exit(1)

    # Foreach tool, follow install procedure
    for tool in tool_list:
        Installer( tool, config_map ).install()

    # Remove cache (to be improved)
    if not args.preserve_cache:
        print('\n[i] Removing cached data...')
        shutil.rmtree( '/var/lib/apt/lists/' )
        os.mkdir( '/var/lib/apt/lists/' )

    print()

if __name__ == '__main__':
    main()