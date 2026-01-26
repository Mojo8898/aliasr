# Configuration

Aliasr is configured via a single TOML file. Configuration is loaded in this order (highest priority first):

1. `ALIASR_CONFIG` (if set)
2. `$XDG_CONFIG_HOME/aliasr/config.toml` (if XDG_CONFIG_HOME is set)
3. `~/.config/aliasr/config.toml`
4. Built-in defaults shipped with Aliasr

If multiple locations exist, the first one found wins.

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
│   ├── .credentials.kdbx        # project-specific creds
│   ├── .credentials.key
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
kdbx = "${ALIASR_MACHINE_DIR}/.credentials.kdbx"
key  = "${ALIASR_MACHINE_DIR}/.credentials.key"

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
  ✓ KeePass DB: /root/projects/project-1/.credentials.kdbx
  ✓ Key file: /root/projects/project-1/.credentials.key
```
