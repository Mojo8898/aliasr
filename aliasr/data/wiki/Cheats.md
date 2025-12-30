# Cheats

Aliasr uses enhanced Markdown format with special syntax for parameters and references:

``````md
# ffuf
#target/remote #os/linux #cat/web

## Fuzz endpoints
```
ffuf -u '<proto|http>://<fqdn>/FUZZ' -w <wordlist|/usr/share/seclists/Discovery/Web-Content/raft-small-words.txt> -c -ac
```

- wordlist
/usr/share/seclists/Discovery/Web-Content/raft-small-files.txt
/usr/share/seclists/Discovery/Web-Content/raft-small-words.txt
``````

In this example, the parameter menu will include all values defined under the `wordlist` reference at the bottom of the cheat. The input, however, will still be prefilled with `/usr/share/seclists/Discovery/Web-Content/raft-small-words.txt`, as prefill is determined by the following order of priority:

1. The current corresponding global value.
2. The placeholder defined in the associated cheatsheet, if one is defined.
3. The first value in references, if any are defined.

## Variations

A detailed reference on writing variations can be found [here](./Variations.md).

## Placeholders (WORK IN PROGRESS)

The purpose of this list is to unify cheats and provide a standard for future PRs. The current cheat list is also a work in progress.

### Defaults

```
krb5ccname
lhost
lport
lwport      # Stands for "local web port", is where you host simple http server to stage files
ip
hostname
domain
fqdn
dc_ip
dc_fqdn
domain_sid
krb5ccname
aliasr_prefix
```

### Non-defaults

```
netbios
tld
target_obj    # Target object in active directory
trustee       # Security principal being granted rights in active directory

userlist
passwordlist
```

## Tags

### Mandatory + Exclusive

**Target**

```
target/remote
target/local
```

**Operating System**

```
os/linux
os/windows
```

**Note:** os/* references where command is executed **from**.

### Categories

- Mandatory
- Optional
- Mutually inclusive

```
cat/web
cat/ad
cat/powerview
cat/cloud
cat/aws
cat/gcp
cat/azure
cat/containers
cat/mobile

cat/recon
cat/pivoting
cat/movement  # Lateral movement
cat/privesc
cat/persist

cat/pwn
cat/cracking
cat/bruteforce
cat/utils
```

### Protocols

```
proto/*
```

### Ports

```
port/*
```
