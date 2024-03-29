# Catalog

> Catalog was a fun project to code, mostly to improve my python level and support my other project [kitt](https://github.com/senges/kitt).
> It's quite pointless now tho as Nix is doing the same job way better, with strong community involvement.
> Will archive this repository for now.

Catalog makes tool installation inside containers super easy, fast and clean.  
A comprehensive currated list of available tools is available in [TOOLS.md](./TOOLS.md).

> Catalog is built for apt based distributions. 
> Feel free to improve !

## Requirements

Catalog requires `python3` installed.

## Basic usage

```text
$  catalog --help
usage: catalog.py [-h] [-i INFILE] [-a] [-l] [-f] [-v] [--init] [--debug] [--preserve-cache] [--dry-run] [--dependencies {fail,ignore,satisfy}] [TOOL_NAME [TOOL_NAME ...]]

positional arguments:
  TOOL_NAME

optional arguments:
  -h, --help            show this help message and exit
  -i INFILE, --infile INFILE
                        input tool list file
  -a, --available       list available tools and exit
  -l, --list            list installed tools and exit
  -f, --force           force tool reinstall if present
  -v, --verbose         verbose mode
  --init                setup catalog basic requirements
  --debug               run catalog in debug mode
  --preserve-cache      do not clear any installation cache
  --dry-run             run catalog in verbose but do not install anything
  --dependencies {fail,ignore,satisfy}
                        dependencies behavior
```

Feed catalog with a list of tools to install :

```bash
$  cat tools.txt
ping
terraform
java
postgresql
redis-server

$  catalog -i tools.txt

$  catalog ping terraform java postgresql redis-server
```

## Docker

Catalog image is based on `ubuntu:20.04` and can be used as a base image for your containers (compressed size `~38MB`).

```Dockerfile
FROM senges/catalog:latest

RUN catalog -v vim htop mysql-client
```

You can also install catalog yourself using `install.sh` script.

```Dockerfile
FROM ubuntu:20.04 
# [...]

# Using wget
RUN sh -c "$(wget -qO- https://raw.githubusercontent.com/senges/catalog/main/utils/install.sh)"
# Using curl
RUN sh -c "$(curl -fsSL https://raw.githubusercontent.com/senges/catalog/main/utils/install.sh)"
```

## Create installation procedure

Your tool is not available in Catalog database ? You can create your own procedure.

Installation procedures are defined as JSON objects.

Each procedure is described as a collection of `steps`.  
Available `steps` types are described right after this section.

```json
"mytool" : {
    "steps" : [
        {
            "type" : "xxx",
            ...
        },
        {
            "type" : "xxx",
            ...
        },
    ],
    "dependencies" : [ "myothertool", "mytool2" ]
}
```

> Catalog is built to work with relative path. Each step is executed in the same scope as the one before. Eache tool has its proper scope.

Tools are installed under `/opt/toolname`.

## Available `steps` types
### apt

```json
{
    "type" : "apt",
    "packages" : [ "pkg1", "pkg2" ]
}
```

Custom apt source support :

```json
{
    "type" : "apt",
    "packages" : [ "tool" ],
    "source" : {
        "repository" : "deb https://apt.tool.io/ tool-sdk main",
        "key" : "https://packages.tool.com/apt/apt-key.gpg"
    }
}
```

***
### pip

```json
{
    "type" : "pip",
    "packages" : [ "pkg1", "pkg2" ]
}
```

```json
{
    "type" : "pip",
    "file" : "static/requirements.txt"
}
```

***
### go

```json
{
    "type" : "go",
    "package" : "github.com/user/tool@latest"
}
```

***
### wget

```json
{
    "type" : "wget",
    "url" : "https://site.com/ressource.zip"
}
```

Custom outfile :

```json
{
    "type" : "wget",
    "url" : "https://get.site.com",
    "outfile" : "install.sh"
}
```

***
### link

Create a symlink to the tool in order to make it available in user $PATH.

In the following example, `mytool.py` will be globally accessible in any shell as `mytool` command.

```json
{
    "type" : "link",
    "target" : "src/release/mytool.py",
    "name" : "mytool"
}
```

```text
$  mytool
It works globally !
```

> `target` field supports glob expansion.

***
### git

Clone a git repository.

*(optional)* `clean` allows you to quickly remove unwanted files in the repository (already included : `.git*`, `*.md`, `.travis.yml`)

```json
{
    "type" : "git",
    "repository" : "https://github.com/foo/bar.git",
    "clean" : ["images", "*.dat"]
}
```

***
### github release

Will download a github release artifact archive. Keyword `{{latest}}` is available in order to follow dynamic archive naming based on version number.

```json
{
    "type" : "github_release",
    "repository" : "foo/bar",
    "artifact" : "mytool-v{{latest}}-linux-adm64.zip",
    "outfile" : "mytool-linux-amd64.zip"
}
```

You can also download release source code, either in `tar.gz` or `zip` archive. Use syntax `FORMAT@TAG`.

```json
{
    "type" : "github_release",
    "repository" : "foo/bar",
    "artifact" : "tar.gz@{{latest}}",
    "outfile" : "mytool.tgz"
},
{
    "type" : "github_release",
    "repository" : "foo/bar",
    "artifact" : "zip@9.0.2",
    "outfile" : "mytool.zip"
}
```

***
### run

Run all kind of executable files.

```json
{
    "type" : "run",
    "file" : "configure.sh"
}
```

Add arguments (`{{pwd}}` keyword will feed current context path).

```json
{
    "type" : "run",
    "file" : "configure.sh",
    "args" : [ "--prefix={{pwd}}" ]
}
```

This is the equivalent of :

```text
$  ./configure.sh --prefix="$(pwd)"
```

If the stub cannot be executed globally with absolute path, optional `cwd` options allows to set a directory for execution.

```json
{
    "type" : "run",
    "file" : "mytool_v1-*/configure",
    "cwd"  : "mytool_v1-*"
},
```

> `file` and `cwd` fields support glob expansion.

***
### extract

Extract compressed archive.

Supported compressions are :
* zip (.zip)
* tgz (.tgz)
* targz (.tar.gz)

`remove` option tells if archive should be removed after extraction or not.  

```json
{
    "type" : "extract",
    "archive" : "mytool-linux-amd64.zip",
    "compression" : "zip",
    "remove" : true
}
```

> `archive` field supports glob expansion.

***
### rm

Remove junk local files to save some disk space. 

```json
{
    "type" : "rm",
    "selectors" : ["data.sqlite", "*.??*"],
}
```

***
### shell

> This is not recommanded way of usging Catalog.
> Please make sure to use it with caution.
> If install function is lacking, feel free to PR or open an issue in Catalog repo.

Run custom shell command.

```json
{
    "type" : "shell",
    "cmd" : ["ls", "-lAh", "/tmp"],
}
```
