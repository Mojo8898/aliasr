# Aliasr

[![PyPI version](https://img.shields.io/pypi/v/aliasr?v1.1.2)](https://pypi.org/project/aliasr/)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue)

**Aliasr** is a modern, feature-rich TUI launcher for penetration testing commands inspired by [Arsenal](https://github.com/Orange-Cyberdefense/arsenal), but with significantly improved functionality.

[![Aliasr Quick Guide](https://img.youtube.com/vi/5xc_cXWfvm0/maxresdefault.jpg)](https://www.youtube.com/watch?v=5xc_cXWfvm0)

## Features

Some of the largest improvements Aliasr implements include:

- [x] Significantly expanded tmux integration.
- [x] Cheat variations that allow for different authentication methods to be built into a single parameter.
- [x] Automatic parameter population based on history and other sources.
- [x] [Exegol-history](https://github.com/ThePorgs/Exegol-history) (SQLite) integration for credential and host management.
- [x] [NetExec](https://github.com/Pennyw0rth/NetExec) (`nxcdb`) integration - credentials and hosts are pulled in on startup and kept in sync.
- [x] A built-in `scan` that fingerprints a target with NetExec and auto-fills your globals.

## Documentation

Full documentation lives in the **[wiki](https://github.com/Mojo8898/aliasr/wiki)**, which serves as a table of contents for the detailed guides:

- [Commands](https://github.com/Mojo8898/aliasr/wiki/01-%E2%80%90-Commands) - the `audit`, `send`, `scan`, `list`, and `clear` subcommands
- [Cheats](https://github.com/Mojo8898/aliasr/wiki/02-%E2%80%90-Cheats) - the cheat markdown format, placeholders, and tags
- [Variations](https://github.com/Mojo8898/aliasr/wiki/03-%E2%80%90-Variations) - per-parameter command variations
- [Configuration](https://github.com/Mojo8898/aliasr/wiki/04-%E2%80%90-Configuration) - the config file, precedence, options, and project setups
- [Credentials & Hosts](https://github.com/Mojo8898/aliasr/wiki/05-%E2%80%90-Credentials-and-Hosts) - Exegol-history and NetExec sync, and the in-app menu

## Install

```bash
# Latest release (PyPI)
uv tool install aliasr
pipx install aliasr

# Latest commit (GitHub)
uv tool install git+https://github.com/Mojo8898/aliasr
pipx install git+https://github.com/Mojo8898/aliasr
```

> [!TIP]
> Run `aliasr init` to append the zsh and tmux integration below to your `~/.zshrc` and `~/.tmux.conf` automatically (idempotent; confirms each file, or use `-y`). Scope it with `aliasr init zsh` / `aliasr init tmux`. The manual steps below remain the reference for what it adds.

Add the following to your `~/.zshrc` to wrap aliasr in a shell function, so the credential and host you select follow you into your shell:

```bash
function a { aliasr "$@" && exec zsh }
```

aliasr records the credential and host you build with as [Exegol-history](https://github.com/ThePorgs/Exegol-history)'s *current* credential/host, writing them to its `profile.sh`. The `&& exec zsh` re-sources your shell when aliasr exits, so those values refresh live instead of on the next new shell. This relies on Exegol-history's `profile.sh` being sourced by your shell; the prompt setup below does that and also surfaces the current credential. See aliasr's [Credentials & Hosts](https://github.com/Mojo8898/aliasr/wiki/05-%E2%80%90-Credentials-and-Hosts) guide for the full picture.

Add the following to your `~/.zshrc` to source `profile.sh` and show the current `USER` (and `DOMAIN`, when set) in your prompt. It overrides Kali's default `configure_prompt`:

```zsh
source ~/.exegol_history/profile.sh

configure_prompt() {
    # Exegol-history tag from the env vars profile.sh exports.
    local db_prompt=""
    if [[ -n "$USER" ]]; then
        if [[ -n "$DOMAIN" ]]; then
            db_prompt="%F{white}[%F{yellow}${USER}@${DOMAIN}%F{white}]%F{%(#.blue.green)}─"
        else
            db_prompt="%F{white}[%F{yellow}${USER}%F{white}]%F{%(#.blue.green)}─"
        fi
    fi

    case "$PROMPT_ALTERNATIVE" in
        twoline)
            PROMPT=$'%F{%(#.blue.green)}┌──'"${db_prompt}"$'${debian_chroot:+($debian_chroot)─}${VIRTUAL_ENV:+($(basename $VIRTUAL_ENV))─}(%B%F{%(#.red.blue)}%n%b%F{%(#.blue.green)})-[%B%F{reset}%(6~.%-1~/…/%4~.%5~)%b%F{%(#.blue.green)}]\n└─%B%(#.%F{red}#.%F{blue}$)%b%F{reset} '
            ;;
        oneline)
            PROMPT="${db_prompt}"$'${debian_chroot:+($debian_chroot)}${VIRTUAL_ENV:+($(basename $VIRTUAL_ENV))}%B%F{%(#.red.blue)}%n@%m%b%F{reset}:%B%F{%(#.blue.green)}%~%b%F{reset}%(#.#.$) '
            RPROMPT=
            ;;
        backtrack)
            PROMPT="${db_prompt}"$'${debian_chroot:+($debian_chroot)}${VIRTUAL_ENV:+($(basename $VIRTUAL_ENV))}%B%F{red}%n@%m%b%F{reset}:%B%F{blue}%~%b%F{reset}%(#.#.$) '
            RPROMPT=
            ;;
    esac
}

export U="$USER" P="$PASSWORD" H="$NT_HASH" D="$DOMAIN"
```

The trailing `export` also gives you short `$U` / `$P` / `$H` / `$D` handles for the current credential. On a non-Kali prompt, invoke `configure_prompt` yourself (for example with `add-zsh-hook precmd configure_prompt`).

To use aliasr's extended tmux integration, add the following to your `~/.tmux.conf`:

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

Run bare `aliasr` (optionally `aliasr -e` to execute on selection) to open the TUI, and see the [Commands](https://github.com/Mojo8898/aliasr/wiki/01-%E2%80%90-Commands) guide for the subcommands. **Note:** *Almost* all hotkeys can be found in the footer of the application when running.

## Configuration

Aliasr allows you to configure pretty much everything. Refer to the built-in `config.toml` found [here](./aliasr/data/config.toml) to see what configuration options are available, and the [Configuration](https://github.com/Mojo8898/aliasr/wiki/04-%E2%80%90-Configuration) guide for a detailed walkthrough.

Edit `~/.aliasr/config.toml` (created automatically on first run) to override any defaults; your changes are merged at runtime.

## Cheats

A detailed reference guide on writing cheats can be found in the [Cheats](https://github.com/Mojo8898/aliasr/wiki/02-%E2%80%90-Cheats) guide.

## Contributing

Contributions are welcome. If you're contributing cheats, please follow the format and tag conventions in the [Cheats](https://github.com/Mojo8898/aliasr/wiki/02-%E2%80%90-Cheats) guide. Feel free to open an issue if you want to add other features.

Detailed development setup instructions can be found in the [official Textual documentation](https://textual.textualize.io/guide/devtools/).

## Acknowledgments

- Inspired by [Arsenal](https://github.com/Orange-Cyberdefense/arsenal) by Orange Cyberdefense
- Built with [Textual](https://github.com/Textualize/textual)
- Special thanks to the members of the [S4U2SelfEnjoyers](https://app.hackthebox.com/teams/7014?tab=members) HackTheBox team for beta testing and providing essential feedback.
