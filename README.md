# Aliasr

[![PyPI version](https://img.shields.io/pypi/v/aliasr?v1.0.8)](https://pypi.org/project/aliasr/)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue)

**Aliasr** is a modern, feature-rich TUI launcher for penetration testing commands inspired by [Arsenal](https://github.com/Orange-Cyberdefense/arsenal), but with significantly improved functionality.

[![Aliasr Quick Guide](https://img.youtube.com/vi/5xc_cXWfvm0/maxresdefault.jpg)](https://www.youtube.com/watch?v=5xc_cXWfvm0)

## Contents

- [Features](#features)
- [Install](#install)
- [Usage](#usage)
- [Commands](#commands)
- [Cheats](#cheats)
- [Variations](#variations)
- [Configuration](#configuration)
- [Credentials & hosts](#credentials--hosts)
- [Projects](#projects)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)

## Features

Some of the largest improvements Aliasr implements include:

- [x] Significantly expanded tmux integration.
- [x] Cheat variations that allow for different authentication methods to be built into a single parameter.
- [x] Automatic parameter population based on history and other sources.
- [x] Exegol-history (SQLite) integration for credential and host management.
- [x] NetExec (`nxcdb`) integration — credentials and hosts are pulled in on startup and kept in sync.
- [x] A built-in `scan` that fingerprints a target with NetExec and auto-fills your globals.

## Install

```bash
# Latest release (PyPI)
uv tool install aliasr
pipx install aliasr

# Latest commit (GitHub)
uv tool install git+https://github.com/Mojo8898/aliasr
pipx install git+https://github.com/Mojo8898/aliasr
```

I also highly recommend adding the following line to your `~/.zshrc`:

```bash
alias a=aliasr
```

If you intend on leveraging the extended tmux integration aliasr offers (which you should), also add the following to your `~/.tmux.conf`:

```bash
# Add to ~/.tmux.conf
bind U split-window "aliasr send -pp"
bind K split-window "aliasr -e send -pp"

# Recommended tmux settings
set -s escape-time 0
set -s focus-events on
set -s default-terminal "tmux-256color"
set -as terminal-overrides ",*:Tc"
```

You can now use the `prefix+K` hotkey to open aliasr below the current pane and send commands automatically to the pane that was focused previously. `prefix+U` does the same but without also sending the enter key to execute the command.

## Usage

```bash
$ aliasr -h
usage: aliasr [-h] [-e] {audit,send,scan,list,clear} ...

aliasr - Modern TUI launcher for pentest commands

positional arguments:
  {audit,send,scan,list,clear}
    audit               Audit cheatsheets and configs
    send                Modify how commands are sent
    scan                Auto-populate globals from a target IP
    list                List globals or credentials
    clear               Clear session data

options:
  -h, --help            show this help message and exit
  -e, --exec            Execute the command immediately
```

Run bare `aliasr` (optionally `aliasr -e` to execute on selection) to open the TUI. **Note:** *Almost* all hotkeys can be found in the footer of the application when running.

## Commands

### `audit` — sanity-check cheats and config

Bare `aliasr audit` prints a brief summary across every section. Add flags to run a section in full; flags **combine freely** (e.g. `aliasr audit -rv`):

| Flag | Audits |
| --- | --- |
| `-c`, `--cheats` | Cheatsheets. Add `-l`/`--list-all` to list every cheat grouped by tag. |
| `-r`, `--references` | Parameter references. |
| `-v`, `--variations` | Variations (`variations.toml`). |
| `--config` | Configuration (`config.toml`), including the active file and resolved values. |
| `-a`, `--all` | Every section, in full. |

### `send` — control how a built command is delivered

```bash
aliasr send [-c | -o FILE | -p [PANE] | -pp]
```

- `-c`, `--copy` — copy to clipboard
- `-o`, `--outfile FILE` — write to a file
- `-p`, `--pane [PANE]` — send to a tmux pane (defaults to pane `0`)
- `-pp`, `--previous-pane` — send to the previously focused tmux pane (see the [tmux binds above](#install))

### `scan` — auto-populate globals from a target

```bash
aliasr scan <IP> [-u USER] [-p PASSWORD] [-H HASH] [-k] [--use-kcache]
```

Fingerprints a target with [NetExec](https://github.com/Pennyw0rth/NetExec) (`nxc` must be on your `PATH`) and fills your globals — `hostname`, `domain`, `fqdn`, `dc_ip`, `dc_fqdn`, `domain_sid`, `netbios`, and more — detecting whether the host is a domain controller along the way. Supplied credentials are saved too.

The authentication flags mirror NetExec's own and are passed straight through, so any combination `nxc` accepts works here. `-k` is only ever emitted when you ask for it (it is never forced onto password/hash auth).

### `list` — print stored data

```bash
aliasr list {globals,creds,all}
```

Lists your current globals, saved credentials, or both.

### `clear` — wipe stored data

```bash
aliasr clear {cache,globals,creds,hosts,all} [-y]
```

- `cache` — the cheats cache. **Not usually needed:** the cache rebuilds automatically whenever your cheats change.
- `globals` — reset globals to the configured defaults.
- `creds` / `hosts` / `all` — clear credentials/hosts (and everything, respectively).

`creds`, `hosts`, and `all` ask for confirmation first (they also clear the matching entries in `nxcdb` by default — see [Credentials & hosts](#credentials--hosts)). Pass `-y`/`--yes` to skip the prompt for scripting. If there's nothing to clear, aliasr says so and skips the prompt.

## Cheats

Aliasr uses an enhanced Markdown format with special syntax for parameters and references:

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

Cheats are loaded from the paths in `[cheats].paths` (plus the bundled defaults, unless disabled). See [`config.toml`](./aliasr/data/config.toml) for the relevant options.

### Placeholders (work in progress)

The purpose of this list is to unify cheats and provide a standard for future PRs. The current cheat list is also a work in progress.

**Defaults** (seeded into every globals file):

```
krb5ccname
lhost
lport
lwport      # "local web port", where you host a simple HTTP server to stage files
ip
hostname
domain
fqdn
dc_ip
dc_fqdn
domain_sid
aliasr_prefix
```

**Non-defaults:**

```
netbios
tld
target_obj    # Target object in Active Directory
trustee       # Security principal being granted rights in Active Directory

userlist
passwordlist
```

### Tags

Tags written directly under the `# <file title>` heading apply to **every** command in that file (these are a cheat's *cheat tags*). Tags written under an individual `## <command>` heading apply only to that command (its *build tags*). Both are used for filtering and search; `aliasr audit -cl` lists every cheat with its build tags.

**Mandatory + exclusive — target:**

```
target/remote
target/local
```

**Mandatory + exclusive — operating system** (`os/*` references where the command is executed **from**):

```
os/linux
os/windows
```

**Categories** (mandatory, optional, or mutually inclusive):

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

**Protocols** and **ports:**

```
proto/*
port/*
```

## Variations

Variations let you create placeholder parameters (such as for authentication) that invoke a separate menu before the build menu when selecting a command. In the variations menu you pick from predefined command snippets, which are substituted when you return to the build menu. See this snippet from [`variations.toml`](./aliasr/data/cheats/variations.toml):

```toml
[bloodyAD.auth]
Password = "-p '<password>'"
"NT hash" = "-p :<nt_hash>"
Kerberos = "-k"
```

This applies to the following example cheat for bloodyAD:

``````md
## Get writable
```
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' <auth> get writable
```
``````

The `<auth>` parameter invokes the variations menu when the cheat is selected, offering the options defined by the variation (`Password`, `NT hash`, `Kerberos`). Selecting `Password`, for example, replaces `<auth>` and opens the build menu with:

```md
bloodyAD --host <dc_fqdn> -d <domain> -u '<user>' -p '<password>' get writable
```

Variations are titled using the schema:

```
[<first_word>.<parameter_to_replace>]
```

A variation that applies across **all** commands uses:

```
[_.<parameter_to_replace>]
```

You can define custom variations in a `variations.toml` placed alongside your cheats; it is discovered and merged automatically, the same way `config.toml` is.

## Configuration

Aliasr is configured via a single TOML file. Refer to the built-in [`config.toml`](./aliasr/data/config.toml) for every available option. Configuration is loaded in this order (highest priority first):

1. `ALIASR_CONFIG` (if set)
2. `$ALIASR_HOME/config.toml` (defaults to `~/.aliasr/config.toml`)
3. `$XDG_CONFIG_HOME/aliasr/config.toml` (if `XDG_CONFIG_HOME` is set)
4. `~/.config/aliasr/config.toml`
5. Built-in defaults shipped with Aliasr

If multiple locations exist, the first one found wins.

On first run Aliasr creates `~/.aliasr/` and drops an editable copy of the default `config.toml` there; your edits are merged over the built-in defaults at runtime. Globals live beside it at `~/.aliasr/globals.json` (a pre-existing `~/.aliasr.json` is migrated automatically). Set `ALIASR_HOME` to relocate the whole folder.

A few notable options:

- `[creds].confirm_delete` — prompt before deleting a row in the credentials/hosts menu (set `false` for one-key deletes).
- `[nxc].block_bulk_delete` — forbid the `clear` commands from deleting anything in NetExec (see [NetExec sync](#netexec-nxcdb-sync)).

### Keeping your config current

When aliasr starts and your `config.toml` is missing options that a newer version added, it lists them and offers to back your file up to `config.toml.bak` and drop in the current defaults. Decline (or run non-interactively) and it simply proceeds — the missing options still take their default values, since your file is merged over the built-in defaults either way.

## Credentials & hosts

Credentials and hosts are shared **two ways** with both [Exegol-history](https://github.com/ThePorgs/Exegol-history) and [NetExec](https://github.com/Pennyw0rth/NetExec), and are managed from a single in-app menu.

### Exegol-history

Credentials are stored in an Exegol-history SQLite database (default `~/.exegol_history/exh.db`), so they're shared with Exegol. Point `[creds].db` elsewhere, or override it with `ALIASR_CREDS_DB`, to use a different file.

**Current credential.** Building a command records the credential you used as Exegol-history's *current credential* — the `USER`/`PASSWORD`/`NT_HASH`/`DOMAIN` exports in its `profile.sh` buffer. On the next build aliasr defaults the credential fields to whatever is set there, so the cred follows you across runs and syncs both ways with Exegol. The profile path is auto-detected from `~/.exegol_history/config.toml`; override it with `[creds].profile` or the `ALIASR_PROFILE` env var.

Writing `profile.sh` cannot change the environment of the shell already running aliasr — a process can't mutate its parent's env. It takes effect the next time a shell sources the profile: a new shell, or an `exec zsh`. Exegol's own `exh` wrapper does this with `exegol-history "$@" && exec zsh`; to get the same live refresh for aliasr, wrap its launch the same way in your shell rc:

```zsh
function a { aliasr "$@" && exec zsh }
```

This is optional — the current-credential default works regardless, because aliasr reads it from the `profile.sh` file (a single shared location), not from the environment of whichever pane launched it.

**Hosts.** Host globals are shared with Exegol-history the same way. On a build that uses them, aliasr upserts the values into Exegol's shared `hosts` table (in `exh.db`) and sets the matching `profile.sh` variables:

| aliasr global | Exegol `hosts` row     | profile.sh var(s)  |
| ------------- | ---------------------- | ------------------ |
| `ip`          | target row `ip`        | `IP`, `TARGET`     |
| `fqdn`        | target row `hostname`  | `DB_HOSTNAME`      |
| `dc_ip`       | DC row `ip` (role=DC)  | `DC_IP`            |
| `dc_fqdn`     | DC row `hostname` (DC) | `DC_HOST`          |

The DC is stored as a separate `hosts` row with `role = "DC"`, which drives Exegol's `DC_IP` / `DC_HOST`. Only the host fields a command actually uses are written, so building against a target leaves the DC pinned — matching Exegol's own set-host behavior. Host writes **upsert** (keyed on `ip` + `hostname`) and never delete, so hosts you added in Exegol are preserved. When Exegol has a host set, aliasr seeds those build fields from it, just like the current credential. (`DOMAIN` is a credential field in Exegol, so it syncs with the credential, not here; `domain_sid` has no Exegol equivalent.)

### NetExec (nxcdb) sync

Aliasr also integrates with NetExec's database. On startup it reads NetExec's current workspace (`~/.nxc/workspaces/<workspace>/*.db`, workspace taken from `~/.nxc/nxc.conf`) and pulls every credential and host it finds into the shared store. NetExec records a credential's secret as a plaintext password or an NT hash; hosts become aliasr hosts (short name + domain joined into an FQDN, with `smb.db`'s DC flag becoming `role = "DC"`). NetExec's databases are only ever opened read-only during the pull.

Deletions propagate **back** to NetExec: deleting a NetExec-sourced credential or host from the menu deletes it from every protocol database in the workspace too, keeping the two stores in sync. The `clear creds`/`clear hosts`/`clear all` commands likewise empty NetExec's store by default. Set `[nxc].block_bulk_delete = true` to forbid the `clear` commands from touching NetExec — individual deletions from the menu still propagate, as they're explicit and confirmed.

### The credentials & hosts menu

Open it from the main screen with the `Creds/Hosts` binding (`Ctrl+L` by default). It has two tabs — **Credentials** and **Hosts** — switched with `alt+left`/`alt+right`:

- Add, edit, and delete rows; deleting asks for confirmation first (toggle with `[creds].confirm_delete`).
- The per-column copy keys adapt to the active tab — on Credentials they copy user / password / hash / domain; on Hosts they copy ip / hostname / role.

## Projects

Aliasr supports project-specific configs with the tool [`direnv`](https://direnv.net/).

To create an Aliasr project, set `ALIASR_CONFIG` to point to either a file (e.g. `/path/to/.aliasr.toml`) or a directory (Aliasr will use `<dir>/config.toml`).

Example layout:

```
/root/projects/
├── project-1/
│   ├── .envrc                   # direnv config
│   ├── .aliasr.toml             # local aliasr config
│   ├── .aliasr-globals.json     # project-specific globals
│   ├── .credentials.db          # project-specific creds (SQLite)
│   ├── exploits/
│   ├── loot/
│   └── scans/
└── project-2/
    ├── .envrc
    ├── .aliasr.toml
    └── ...
```

Example `.envrc`:

```bash
export ALIASR_MACHINE_DIR="$PWD"
export ALIASR_CONFIG="$PWD/.aliasr.toml"
```

Example `.aliasr.toml`:

```toml
[globals]
path = "${ALIASR_MACHINE_DIR}/.aliasr-globals.json"

[creds]
db = "${ALIASR_MACHINE_DIR}/.credentials.db"

[globals.defaults]
ip       = ["10.10.11.123"]
hostname = ["machine-1"]
domain   = ["htb.local"]
fqdn     = ["machine-1.htb.local"]
lhost    = ["10.10.14.5"]
lport    = ["4444"]
```

Load and apply the changes in `.envrc` with:

```bash
direnv allow
```

Then verify the configuration is being picked up:

```bash
aliasr audit --config
```

For a project created in `/root/projects/project-1/` you should see, for example:

```
  ✓ ALIASR_CONFIG /root/projects/project-1/.aliasr.toml
  ...
  ✓ Globals file: /root/projects/project-1/.aliasr-globals.json
  ...
  ✓ Credentials DB (Exegol-history): /root/projects/project-1/.credentials.db
```

## Contributing

Contributions are welcome. If you're contributing cheats, follow the format and tag conventions in [Cheats](#cheats). Feel free to open an issue to propose other features.

Detailed development setup instructions can be found in the [official Textual documentation](https://textual.textualize.io/guide/devtools/).

## Acknowledgments

- Inspired by [Arsenal](https://github.com/Orange-Cyberdefense/arsenal) by Orange Cyberdefense
- Built with [Textual](https://github.com/Textualize/textual)
- Special thanks to all members of my HackTheBox team [S4U2SelfEnjoyers](https://app.hackthebox.com/teams/7014?tab=members) for beta testing and providing essential feedback.
