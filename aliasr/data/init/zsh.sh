# Wrap aliasr so the credential/host you select follow you into your shell.
function a { aliasr "$@" && exec zsh }

# Source Exegol-history's profile.sh and surface the current USER (and DOMAIN,
# when set) in the prompt. Overrides Kali's default configure_prompt; on a
# non-Kali prompt, invoke configure_prompt yourself (e.g. via add-zsh-hook).
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
