# SMB
#target/remote #os/linux #cat/ad #proto/smb #port/445

## smb all in one
```
nxc smb <ip> -u '<user>' <auth> --shares --pass-pol

nxc smb <ip> -u '<user>' <auth> -M enum_av -M enum_ca -M enum_cve -M gpp_privileges -M ioxidresolver -M sccm-recon6 -M smbghost -M spooler -M webdav -M gpp_autologin -M gpp_password

skewrun <ip> -- nxc smb <ip> -u '<user>' -p '<password>' -M nopac -M remove-mic

nxc smb <ip> -u '<user>' -p '<password>' -M timeroast

nxc smb <ip> -u '<user>' <auth> --users --rid-brute 10000

smbclientng --host <fqdn> -d <domain> -u '<user>' <auth> -S <(echo 'shares')
```

## smbclientng
```
smbclientng --host <fqdn> -d <domain> -u '<user>' <auth> -S <(echo 'shares')
```

## nxc smb modules
```
nxc smb <ip> -u '<user>' <auth> <smb_modules>
```
