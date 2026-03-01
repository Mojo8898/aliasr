# Web
#target/remote #os/linux

## Subdomain all in one
```
ffuf -w /usr/share/seclists/Discovery/DNS/services-names.txt -u '<url>' -H 'Host: FUZZ.<domain>' -ac -c; ffuf -w /usr/share/seclists/Discovery/DNS/subdomains-top1million-20000.txt -u '<url>' -H 'Host: FUZZ.<domain>' -ac -c
```

## Dirbust all in one
```
ffuf -w /usr/share/seclists/Discovery/Web-Content/quickhits.txt -u '<url>/FUZZ' -ac -c; ffuf -w /usr/share/seclists/Discovery/Web-Content/raft-small-words.txt -u '<url>/FUZZ' -ac -c; feroxbuster -u '<url>'
```
