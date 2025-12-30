# Aliasr

[![PyPI version](https://img.shields.io/pypi/v/aliasr?v1.0.0)](https://pypi.org/project/aliasr/)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/github/license/Mojo8898/aliasr)

**Aliasr** is a modern, feature-rich TUI launcher for penetration testing commands inspired by [Arsenal](https://github.com/Orange-Cyberdefense/arsenal), but with significantly improved functionality.

## Features

Some of the largest improvements Aliasr implements include:

- [x] Significantly expanded tmux integration.
- [x] Cheat variations that allow for different authentication methods to be built into a single parameter.
- [x] Automatic parameter population based on history and other sources.
- [x] Secure KeePass integration for managing credentials.

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

**Note:** *Almost* all hotkeys can be found in the footer of the application when running.

## Configuration

Aliasr allows you to configure pretty much everything. Refer to the built-in `config.toml` found [here](./aliasr/data/config.toml) to see what configurations options are available.

Create your own config in `~/.config/aliasr/config.toml` to edit existing configurations and changes will automatically be merged at runtime.

**Note:** Paths set in the environment variables `XDG_CONFIG_HOME` and `ALIASR_CONFIG` will be used instead if set.

## Cheats

A detailed reference guide on writing cheats can be found [here](./aliasr/data/wiki/Cheats.md).

## Contributing

Contributions are welcome but make sure you if you are contributing to cheats, you follow guidelines in [Cheats Reference](./aliasr/data/wiki/Cheats.md). Also feel free to open an issue if you want to add other features.

Detailed development setup instructions can be found in the [official Textual documentation](https://textual.textualize.io/guide/devtools/).

## Acknowledgments

- Inspired by [Arsenal](https://github.com/Orange-Cyberdefense/arsenal) by Orange Cyberdefense
- Built with [Textual](https://github.com/Textualize/textual)
- Special thanks to all members of my HackTheBox team [S4U2SelfEnjoyers](https://app.hackthebox.com/teams/7014?tab=members) for beta testing and providing essential feedback.
