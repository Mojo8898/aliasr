# powerview.py
#target/remote #os/linux #cat/ad #cat/powerview #proto/ldap #port/389

## Query userlist
```
Get-DomainUser -Select sAMAccountName
```

## Enumerate users
```
Get-DomainUser -Prop * -Select sAMAccountName,memberOf,logonCount,userAccountControl
```

## Enumerate group membership
```
Get-DomainObject -Select samaccountname,memberof,distinguishedname -TableView -Where 'memberof not .'
```

## Enumerate Domain GPOs
```
Get-DomainGPO -Properties * -Select displayname,name -TableView
```

## Enumerate create GPO rights
```
Get-DomainObjectAcl 'CN=Policies,CN=System,DC=<netbios>,DC=<tld>' -ResolveGUIDs -Where 'AccessMask contains CreateChild' -Select SecurityIdentifier
```

## Enumerate deleted objects
```
Get-DomainObject -IncludeDeleted -Where 'isDeleted eq True' -Select distinguishedName,whenChanged -TableView
```

## Enumerate Reanimate-Tombstones privileges
```
Get-DomainObjectAcl -Where 'ObjectAceType eq Reanimate-Tombstones' -Select SecurityIdentifier -TableView
```

## Enumerate inbound ACLs for a target object
```
Get-ObjectAcl <target_obj> -Select SecurityIdentifier,AccessMask,ActiveDirectoryRights,ObjectAceType -Where 'SecurityIdentifier contains <netbios>' -ResolveGUIDs -TableView
```

## Enumerate outbound ACLs for a principal
```
Get-ObjectAcl -SecurityIdentifier <target_obj> -Select AccessMask,ActiveDirectoryRights,ObjectAceType,ObjectDN -ResolveGUIDs -TableView
```

## Enumerate GMSA rights for a target account
```
Get-ObjectAcl <gmsa_account> -Select SecurityIdentifier,AccessMask,ActiveDirectoryRights,ObjectAceType -Where 'ObjectAceType eq ms-DS-ManagedPassword' -ResolveGUIDs -TableView
```

## Enumerate GPO rights
```
Get-DomainObjectAcl 'CN=<gpo_name>,CN=Policies,CN=System,DC=<netbios>,DC=<tld>' -ResolveGUIDs -Select SecurityIdentifier,ActiveDirectoryRights -TableView
```

## Restore deleted object
```
Restore-DomainObject -Identity '<target_dn>'
```
