#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# =============================================================================
# Author : @senges
# Version : March 2022
# Description : Catalog, a quick tool installer
# =============================================================================

import os
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

    @classmethod
    def ignore_dependencies(cls):
        return cls.DEPENDENCIES == 'ignore'

    @classmethod
    def satisfy_dependencies(cls):
        return cls.DEPENDENCIES == 'satisfy'

class Installer:

    def __init__(self, config: dict, tool: dict):

        self.wd = '/opt/%s' % tool
        self.config = config.get(tool)
        self.config_map = config
        self.tool = tool

        self.mkpath = lambda x: os.path.join(self.wd, x)

        self.functions_mapper = {
            'apt'   : self._apt,
            'pip'   : self._pip,
            'npm'   : self._npm,
            'go'    : self._go,
            'wget'  : self._wget,
            'link'  : self._link,
            'rm'    : self._rm,
            'run'   : self._run,
            'git'   : self._git,
            'shell' : self._shell,
            'extract' : self._extract,
            'github_release' : self._github_release
        }

    def install(self):

        # Tool is already installed
        if os.path.exists( self.wd ):
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
        if not Config.ignore_dependencies():
            for dependency in self.config.get('dependencie', []):
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

            for cmd in cmdset:
                verbose( ' '.join(cmd) )
                if not Config.DRY_RUN: 
                    shell_run( cmd )
                verbose('=> Ok')
                
        # Keep trace of tool installation
        trace = os.path.join('/opt/.catalog/tools', self.tool)
        with open(trace, 'w+') as f:
            f.write( str(datetime.datetime.now()) )

    # Check that dependency is satisfied
    def _dependency(self, name: str):
        path = os.path.join('/opt/.catalog/tools', name)

        if os.path.exists( path ): return

        if Config.satisfy_dependencies():
            print('\n[i] Installing dependency ' + self.tool)
            Installer(self.config_map, name).install()
            return

        elif Config().ignore_dependencies():
            print('\n[i] Ignoring unsatisfied dependency ' + self.tool)
            return

        print('[!] Unsatisfied dependency : %s' % name)
        exit(1)
                
    def _apt(self, step: dict):
        pkg = step.get('packages')

        cmd = []

        # If any custom repo source to add
        if source := step.get('source'):
            repo = source.get('repository')
            key = source.get('key')

            # Download pgp key
            cmd += self._wget({
                'url' : key
            })

            _, keyname = os.path.split(key)

            # Add pgp key
            cmd.append(['apt-key', 'add', self.mkpath(keyname)])

            # Remove pgp key file
            cmd += self._rm({
                'selectors' : [ keyname ]
            })

            sources = []

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

        cmd.append( ['apt', 'update'] )
        cmd.append( ['apt', 'install', '-y', '--no-install-recommends'] + pkg )

        return cmd

    def _pip(self, step: dict):

        if pkg := step.get('packages'):
            return [['pip', 'install'] + pkg]
            
        requirements = step.get('file')
        requirements = self.mkpath(requirements)

        return [['pip', 'install', '-r', requirements]]

    def _go(self, step: dict):
        package = step.get('package')

        return [['go', 'install', '-v', package]]

    def _npm(self, step: dict):
        packages = step.get('packages')
        cmd = []

        for package in packages:
            cmd.append( ['npm', 'install', '--prefix', self.wd, package] )
            cmd += self._link({
                'name' : package,
                'target' : os.path.join(self.wd, 'node_modules/.bin/%s' % package)
            })

        return cmd

    def _wget(self, step: dict):
        url = step.get('url')
        outfile = step.get('outfile')

        if outfile:
            filename = outfile
        else:
            _, filename = os.path.split(url)

        path = os.path.join(self.wd, filename)

        return [['wget', '-O', path, '--no-check-certificate', url]]

    def _link(self, step: dict):
        name = step.get('name')
        
        target = step.get('target')
        target = self.mkpath(target)

        cmd = []
        cmd.append([ 'chmod', '+x', target ])
        cmd.append(['ln', '-fs', target, f'/opt/bin/{name}' ])

        return cmd

    def _rm(self, step: dict):
        selectors = step.get('selectors')
        path = '%s/{%s}' % (self.wd, ','.join(selectors))

        return [['rm', '-rf', path]]

    def _git(self, step: dict):
        repo = step.get('repository')
        clean = step.get('clean')

        if not clean:
            clean = []

        cmd = [[ 'git', 'clone', '--depth', '1', repo, self.wd ]]

        cmd += self._rm({
            'selectors' : ['.git*','*.md','.travis.yml'] + clean
        })

        return cmd

    def _github_release(self, step: dict):
        repo     = step.get('repository') 
        artifact = step.get('artifact') 
        outfile  = step.get('outfile')

        try:
            request  = Request('https://api.github.com/repos/%s/releases' % repo)
            response = urlopen( request )
            data     = json.load(response)
            latest   = data[0]['tag_name'][1:]
        except:
            print('[!] Could not properly load url https://api.github.com/repos/%s/releases' % repo)
            exit(1)
    
        artifact = artifact.replace('{{latest}}', latest)

        return [[
            'wget', 'https://github.com/%s/releases/download/v%s/%s' % (repo, latest, artifact),
            '-O', self.mkpath(outfile),
            '--retry-connrefused',
            '--waitretry=5',
            '-t', '2'
        ]]

    def _run(self, step: dict):
        path = step.get('file')
        path = self.mkpath(path)

        cmd = []
        cmd.append([ 'chmod', '+x', path ])
        cmd.append([ path ])

        return cmd

    def _shell(self, step: dict):
        return step.get('cmd')

    def _extract(self, step: dict):

        compression = step.get('compression')
        remove      = step.get('remove')
        archive     = step.get('archive')
        archive     = self.mkpath(archive)

        cmd = []

        if compression == 'tgz':
            cmd.append( untar(archive, self.wd) )
        elif compression == 'targz':
            cmd.append( untargz(archive, self.wd) )
        elif compression == 'zip':
            cmd.append( unzip(archive, self.wd) )
        else:
            raise KeyError()

        if remove:
            cmd.append(['rm', '-f', archive])

        return cmd

def shell_run(args: [str]):
    env = os.environ
    
    env['GOPATH'] = env['HOME'] + '/.go'            # To update with /opt managed folder
    env['PYTHONPATH'] = env['HOME'] + '/.python'    # To update with /opt managed folder
    
    try:
        check_call(
            args,
            stdout = open( '/var/log/cata.log', 'a' ), 
            stderr = STDOUT,
            env = env
        )
    except:
        with open('/var/log/cata.log', 'r') as f:
            debug(f.read())
  
        print('[!] Command execution has failed.')
        print('[!] Logs are availables at /var/log/cata.log')
        exit(1)

def unzip(archive: str, target: str) -> [str]:
    return ['unzip', archive, '-d', target]

def untar(archive: str, target: str) -> [str]:
    return ['tar', '-vxf', archive, '-C', target]

def untargz(archive: str, target: str) -> [str]:
    return ['tar', '-vzxf', archive, '-C', target]

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
    parser.add_argument('--debug', help = 'run catalog in debug mode', action = 'store_true')
    # parser.add_argument('-d', '--dind', help = 'use docker in docker provided installers (pip, go, npm..)', action = 'store_true')
    parser.add_argument('--rm-cache', help = 'removed any installation cache', action = 'store_true')
    parser.add_argument('--dry-run', help = 'run catalog in verbose but do not install anything', action = 'store_true')
    parser.add_argument('--dependencies', help = 'dependencies behavior', default = 'fail', choices = ['fail', 'ignore', 'satisfy'])
    # parser.add_argument('--keep-installers', help = 'keep any installer', action = 'store_true')
    parser.add_argument('tools', metavar = 'TOOL_NAME', nargs = '*')

    args = parser.parse_args()

    Config.VERBOSE = args.verbose
    Config.DEBUG = args.debug
    Config.FORCE = args.force
    Config.DRY_RUN = args.dry_run
    Config.DEPENDENCIES = args.dependencies

    # Dry run infer verbose mode
    if Config.DRY_RUN: Config.VERBOSE = True

    config_map = dict()
    tool_list = args.tools

    try:
        # Load config files
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
        _, tools, _ = next(os.walk('/opt'))
        if 'bin' in tools:
            tools.remove('bin')
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
        Path( '/opt/bin' ).mkdir(exist_ok = True, parents = True)
        Path( '/opt/.catalog/tools' ).mkdir(exist_ok = True, parents = True)
    except PermissionError:
        print('[!] Got permission denied on \'/opt\' folder.')
        exit(1)

    # Foreach tool, follow install procedure
    for tool in tool_list:
        Installer( config_map, tool ).install()

    # Remove cache (to be improved)
    if args.rm_cache:
        print('\n[i] Removing cached data...')
        shutil.rmtree( '/var/lib/apt/lists/' )
        os.mkdir( '/var/lib/apt/lists/' )

    print()

if __name__ == '__main__':
    main()