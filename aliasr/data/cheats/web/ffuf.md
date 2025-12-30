# ffuf
#target/remote #os/linux #cat/web

## Fuzz endpoints
```
ffuf -u '<proto|http>://<fqdn>/FUZZ' -w <wordlist|/usr/share/seclists/Discovery/Web-Content/raft-small-words.txt> -c -ac
```

## Fuzz vhosts
```
ffuf -u '<proto|http>://<domain>' -H 'Host: FUZZ.<domain>' -w <wordlist|/usr/share/seclists/Discovery/DNS/services-names.txt> -c -ac
```

## Fuzz extensions
```
ffuf -u '<proto|http>://<fqdn>/indexFUZZ' -w <wordlist|/usr/share/seclists/Discovery/Web-Content/web-extensions.txt> -c -ac
```

- wordlist
/usr/share/seclists/Discovery/DNS/services-names.txt
/usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt
/usr/share/seclists/Discovery/DNS/combined_subdomains.txt
/usr/share/seclists/Discovery/Web-Content/dsstorewordlist.txt
/usr/share/seclists/Discovery/Web-Content/quickhits.txt
/usr/share/seclists/Discovery/Web-Content/web-extensions.txt
/usr/share/seclists/Discovery/Web-Content/raft-small-files.txt
/usr/share/seclists/Discovery/Web-Content/raft-small-words.txt
/usr/share/seclists/Discovery/Web-Content/combined_words.txt
/usr/share/seclists/Discovery/Web-Content/raft-small-directories.txt
/usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt
/usr/share/seclists/Discovery/Web-Content/combined_directories.txt
/usr/share/seclists/Discovery/Web-Content/api/api-endpoints.txt
/usr/share/seclists/Discovery/Web-Content/api/api-endpoints-res.txt
/usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt
/usr/share/seclists/Fuzzing/special-chars.txt
/usr/share/seclists/Fuzzing/alphanum-case-extra.txt
/usr/share/seclists/Usernames/Names/names.txt
/usr/share/seclists/Usernames/xato-net-10-million-usernames.txt
/home/kali/repos/statistically-likely-usernames/jsmith2.txt
/home/kali/repos/statistically-likely-usernames/jsmith.txt

- proto
http
https
