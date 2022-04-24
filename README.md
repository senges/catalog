# Catalog

Catalog makes tool installation super easy, fast and clean.

New environment ? Be ready in minuts !

> Catalog is still under development and does only support apt based distributions for now. Feel free to improve.

## Requirements

To work properly, Catalog needs `wget`, `zip`, `git`, `python3` and `python3-pip` packages installed.

## Basic usage

```text
$  catalog --help
usage: catalog.py [-h] [-i INFILE] [-l] [-f] [-v] [TOOL_NAME [TOOL_NAME ...]]

positional arguments:
  TOOL_NAME

optional arguments:
  -h, --help                    show this help message and exit
  -i INFILE, --infile INFILE    input tool list file
  -l, --list                    list available tools and exit
  -f, --force                   force tool reinstall if present
  -v, --verbose                 verbose mode

```

Feed catalog with a list of tools to install :

```bash
$  cat tools.txt
vscodium
vim
kubectl
dirsearch
htop

$  catalog -i tools.txt

$  catalog vscodium vim kubectl dirsearch htop
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
    "dependency" : []  <-- Not yet implemented
}
```

> Catalog is built to work with relative path. Each step is executed in the same scope as the one before. Eache tool has its proper scope.

Tools are installed under `/opt/toolname`.

***

## Available `steps` types

**# apt**

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

**# pip**

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

**# wget**

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

**# link**

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

**# git**

Clone a git repository.

*(optional)* `clean` allows you to quickly remove unwanted files in the repository (already included : `.git*`, `*.md`, `.travis.yml`)

```json
{
    "type" : "git",
    "repository" : "https://github.com/foo/bar.git",
    "clean" : ["images", "*.dat"]
}
```

**# github release**

Will download a github release archive. Keyword `{{latest}}` is available in order to follow dynamic archive naming based on version number.

```json
{
    "type" : "github_release",
    "repository" : "foo/bar",
    "artifact" : "mytool-v{{latest}}-linux-adm64.zip",
    "outfile" : "mytool-linux-amd64.zip"
}
```

**# run**

Run all kind of executable files.

```json
{
    "type" : "run",
    "file" : "configure.sh"
}
```

This is the equivalent of :

```text
$  ./configure.sh
```

**# extract**

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

**# rm**

Remove junk local files to save some disk space. 

```json
{
    "type" : "rm",
    "selectors" : ["data.sqlite", "*.??*"],
}
```