# FTP
#target/remote #os/linux #proto/ftp #port/21

## ftp connect
```
ftp ftp://<user>:<password>@<ip>
```

## lftp connect
```
lftp -u '<user>,<password>' <ip> -e 'ls -al'
```

## lftp TLS connect
```
lftp -u '<user>,<password>' -e 'set ftp:ssl-force true; set ftp:ssl-protect-data true; set ssl:verify-certificate no' <fqdn>
```
