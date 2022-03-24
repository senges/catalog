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

from glob import glob
from pathlib import Path
from subprocess import STDOUT, check_call
from urllib.request import Request, urlopen

CONFIG_FILES = glob( '%s/static/*.json' % os.path.dirname(os.path.realpath(__file__)) )

VERBOSE = True
FORCE = True

class Installer:

    def __init__(self, config: dict, tool: dict):

        self.wd = '/opt/%s' % tool
        self.config = config.get(tool)
        self.tool = tool

        self.mkpath = lambda x: os.path.join(self.wd, x)

        self.functions_mapper = {
            'apt'   : self._apt,
            'pip'   : self._pip,
            'wget'  : self._wget,
            'link'  : self._link,
            'rm'    : self._rm,
            'run'   : self._run,
            'git'   : self._git,
            'extract' : self._extract,
            'github_release' : self._gh_release
        }

    def install(self):
        # NEED TO CHECK DEPENDENCY FIRST

        # Tool is already installed
        if os.path.exists( self.wd ):
            if FORCE:
                shutil.rmtree( self.wd )
            else:
                print('\n[~] %s already installed, skipping' % self.tool)
                return

        print('\n[+] Installing ' + self.tool)

        # Create working directory
        Path( self.wd ).mkdir(exist_ok = True, parents = True)

        for step in self.config.get('steps'):
            action = step.get('type')
            
            if not action in self.functions_mapper:
                print('[-] %s step type does not exist. Aborting.')
                break

            cmdset = self.functions_mapper[ action ](step)

            for cmd in cmdset:
                verbose( ' '.join(cmd) )
                shell_run( cmd )

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
            with open('/etc/apt/sources.list.d/catalog.list', 'r') as f:
                while line := f.readline():
                    sources.append(line.rstrip())

            # Avoid duplicates
            if repo not in sources:
                with open('/etc/apt/sources.list.d/catalog.list', 'a') as f:
                    f.write(repo + '\n')

            cmd.append(['apt', 'update'])

        cmd.append( ['apt', 'install', '-y', '--no-install-recommends'] + pkg )

        return cmd

    def _pip(self, step: dict):

        if pkg := step.get('packages'):
            return [['pip', 'install'] + pkg]
            
        requirements = step.get('file')
        requirements = self.mkpath(requirements)

        return [['pip', 'install', '-r', requirements]]

    def _wget(self, step: dict):
        url = step.get('url')

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

    def _gh_release(self, step: dict):
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

    ## Run inline command
    # def bash(self, step: dict):
    #     raw = step.get('raw')
    #
    #     return [ raw.split(' ') ]

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
    try:
        check_call(
            args,
            stdout = open( '/var/log/cata.log', 'a' ), 
            stderr = STDOUT
        )
    except:
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
    if VERBOSE:
        print(msg)

def main():
    global VERBOSE
    global FORCE

    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--infile', help = 'input tool list file')
    parser.add_argument('-l', '--list', help = 'list available tools and exit', action = 'store_true')
    parser.add_argument('-f', '--force', help = 'force tool reinstall if present', action = 'store_true')
    parser.add_argument('-v', '--verbose', help = 'verbose mode', action = 'store_true')
    parser.add_argument('tools', metavar = 'TOOL_NAME', nargs = '*')

    args = parser.parse_args()

    VERBOSE = args.verbose
    FORCE = args.force

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
    if args.list:
        available = sorted([x for x, _ in config_map.items()])
        print( '\n'.join( available ) )
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
    Path( '/opt/bin' ).mkdir(exist_ok = True, parents = True)

    # Foreach tool, follow install procedure
    for tool in tool_list:
        Installer( config_map, tool ).install()

    print()

if __name__ == '__main__':
    main()