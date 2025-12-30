# KeePass
#target/local #os/linux #cat/utils

## Crack .kdbx file
```
keepass2john <kdbx> > keepass.hash;john --wordlist=/usr/share/wordlists/rockyou.txt keepass.hash &>/dev/null && john keepass.hash --show | head -n1 | cut -d':' -f2 | keepassxc-cli export <kdbx> -f csv -q > keepass.csv; cat keepass.csv | cut -d'"' -f'8' | tail -n +2 | tee test_passwords.txt; echo; cat keepass.csv | cut -d'"' -f'4,6,8' | tail -n +2 | tr '"' ':'; echo; cat keepass.csv
```

## Decrypt .kdbx file using provided key
```
keepassxc-cli export <kdbx> -k <key> --no-password -f csv
```
