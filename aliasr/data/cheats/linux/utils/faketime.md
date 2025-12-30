# faketime
#target/local #os/linux #cat/utils

## Start new session with clock synced
```
faketime "$(rdate -n <ip> -p | awk '{print $2, $3, $4}' | date -f - "+%Y-%m-%d %H:%M:%S")" zsh
```
