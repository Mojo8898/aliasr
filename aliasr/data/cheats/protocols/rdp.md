# RDP
#target/remote #os/linux #proto/rdp #port/3389

## rdp standard connect
```
xfreerdp3 /cert:ignore /v:<ip> /u:'<user>' /p:'<password>' /dynamic-resolution /drive:.,linux /auto-reconnect /clipboard /compression /bpp:8 /audio-mode:0 -window-drag -themes -wallpaper
```

## rdp unauthenticated connect
```
xfreerdp3 /cert:ignore /v:<ip> /dynamic-resolution /drive:.,linux /auto-reconnect /clipboard /compression /bpp:8 /audio-mode:0 -window-drag -themes -wallpaper -sec-nla
```

## rdp legacy connect (i.e. Windows 2012 R2)
```
xfreerdp3 /cert:ignore /v:<ip> /u:'<user>' /p:'<password>' /dynamic-resolution /drive:.,linux /auto-reconnect /clipboard /compression /bpp:8 /audio-mode:0 -window-drag -themes -wallpaper /sec:nla /tls-seclevel:0
```
