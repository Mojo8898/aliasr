# Web
#target/remote #os/linux

## Subdomain all in one
```
ffuf -w /usr/share/seclists/Discovery/DNS/services-names.txt -u '<proto|http>://<fqdn>' -H 'Host: FUZZ.<fqdn>' -ac -c; ffuf -w /usr/share/seclists/Discovery/DNS/subdomains-top1million-20000.txt -u '<proto|http>://<fqdn>' -H 'Host: FUZZ.<fqdn>' -ac -c
```

## Dirbust all in one
```
ffuf -w /usr/share/seclists/Discovery/Web-Content/quickhits.txt -u '<proto|http>://<fqdn>/FUZZ' -ac -c; ffuf -w /usr/share/seclists/Discovery/Web-Content/raft-small-words.txt -u '<proto|http>://<fqdn>/FUZZ' -ac -c; feroxbuster -u '<proto|http>://<fqdn>'
```
