# Configuration

Aliasr is configured via a single TOML file. Configuration is loaded in this order (highest priority first):

1. `ALIASR_CONFIG` (if set)
2. `$ALIASR_HOME/config.toml` (defaults to `~/.aliasr/config.toml`)
3. `$XDG_CONFIG_HOME/aliasr/config.toml` (if XDG_CONFIG_HOME is set)
4. `~/.config/aliasr/config.toml`
5. Built-in defaults shipped with Aliasr

If multiple locations exist, the first one found wins.

On first run Aliasr creates `~/.aliasr/` and drops an editable copy of the
default `config.toml` there; your edits are merged over the built-in defaults at
runtime. Globals live beside it at `~/.aliasr/globals.json` (a pre-existing
`~/.aliasr.json` is migrated automatically). Set `ALIASR_HOME` to relocate the
whole folder.

Credentials are stored in an [Exegol-history](https://github.com/ThePorgs/Exegol-history)
SQLite database (default `~/.exegol_history/exh.db`), so creds are shared with
Exegol. Point `[creds].db` elsewhere, or override it with `ALIASR_CREDS_DB`, to
use a different file.

## Current credential (Exegol-history profile.sh)

Building a command records the credential you used as Exegol-history's *current
credential* — the `USER`/`PASSWORD`/`NT_HASH`/`DOMAIN` exports in its
`profile.sh` buffer. On the next build aliasr defaults the credential fields to
whatever is currently set there, so the cred follows you across runs and is
shared both ways with Exegol (set one in `exegol-history` and aliasr picks it
up, and vice versa). The profile path is auto-detected from
`~/.exegol_history/config.toml`; override it with `[creds].profile` or the
`ALIASR_PROFILE` env var.

Writing `profile.sh` cannot change the environment of the shell that is already
running aliasr — a process can't mutate its parent's env. It takes effect the
next time a shell sources the profile: a new shell, or an `exec zsh`. Exegol's
own `exh` wrapper does this with `exegol-history "$@" && exec zsh`; to get the
same live refresh for aliasr, wrap its launch the same way, e.g. in your shell
rc:

```zsh
function a { aliasr "$@" && exec zsh }
```

This is optional — the current-credential default works regardless, because
aliasr reads it from the `profile.sh` file (a single shared location), not from
the environment of whichever pane or shell launched it.

## Hosts (Exegol-history)

Host globals are shared with Exegol-history the same way credentials are. On a
build that uses them, aliasr upserts the values into exegol's shared `hosts`
table (in `exh.db`) and sets the matching `profile.sh` variables:

| aliasr global | exegol `hosts` row     | profile.sh var(s)  |
| ------------- | ---------------------- | ------------------ |
| `ip`          | target row `ip`        | `IP`, `TARGET`     |
| `fqdn`        | target row `hostname`  | `DB_HOSTNAME`      |
| `dc_ip`       | DC row `ip` (role=DC)  | `DC_IP`            |
| `dc_fqdn`     | DC row `hostname` (DC) | `DC_HOST`          |

The DC is stored as a separate `hosts` row with `role = "DC"`, which is what
drives exegol's `DC_IP` / `DC_HOST`. Only the host fields a command actually
uses are written, so building against a target leaves the DC pinned — matching
exegol's own set-host behavior. Host writes **upsert** (keyed on `ip` +
`hostname`) and never delete, so hosts you added in exegol are preserved. When
exegol has a host set, aliasr seeds those build fields from it, just like the
current credential. (`DOMAIN` is a credential field in exegol, so it syncs with
the credential, not here; `domain_sid` has no exegol equivalent.)

## Projects

Aliasr supports project-specific configs with the tool `direnv`.

To create an Aliasr project, set `ALIASR_CONFIG` to point to either:

- a file (e.g. `/path/to/.aliasr.toml`), or
- a directory (Aliasr will use `<dir>/config.toml`)

Use the following examples for reference.

Example layout:

```
/root/projects/
├──  project-1/
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

With the environment prepared, load and apply changes defined in `.envrc` using:

```bash
direnv allow
```

Then verify the configuration is being properly identified with:

```bash
aliasr audit conf
```

You should see for example if your project was created in `/root/projects/project-1/`:

```
  ✓ ALIASR_CONFIG /root/projects/project-1/.aliasr.toml
  ...
  ✓ Globals file: /root/projects/project-1/.aliasr-globals.json
  ...
  ✓ Credentials DB (Exegol-history): /root/projects/project-1/.credentials.db
```
