# powerview.py
#target/remote #os/linux #cat/ad #cat/powerview #proto/ldap #port/389

## powerview query userlist
```
Get-DomainUser -Select sAMAccountName
```

## powerview enumerate users
```
Get-DomainUser -Prop * -Select sAMAccountName,memberOf,logonCount,userAccountControl
```

## powerview enumerate group membership
```
Get-DomainObject -Select samaccountname,memberof,distinguishedname -TableView -Where 'memberof not .'
```

## powerview enumerate domain gpos
```
Get-DomainGPO -Properties * -Select displayname,name -TableView
```

## powerview enumerate create gpo rights
```
Get-DomainObjectAcl 'CN=Policies,CN=System,DC=<netbios>,DC=<tld>' -ResolveGUIDs -Where 'AccessMask contains CreateChild' -Select SecurityIdentifier
```

## powerview enumerate deleted objects
```
Get-DomainObject -IncludeDeleted -Where 'isDeleted eq True' -Select distinguishedName,whenChanged -TableView
```

## powerview enumerate reanimate-tombstones privileges
```
Get-DomainObjectAcl -Where 'ObjectAceType eq Reanimate-Tombstones' -Select SecurityIdentifier -TableView
```

## powerview enumerate inbound acls for a target object
```
Get-ObjectAcl <target_obj> -Select SecurityIdentifier,AccessMask,ActiveDirectoryRights,ObjectAceType -Where 'SecurityIdentifier contains <netbios>' -ResolveGUIDs -TableView
```

## powerview enumerate outbound acls for a principal
```
Get-ObjectAcl -SecurityIdentifier <target_obj> -Select AccessMask,ActiveDirectoryRights,ObjectAceType,ObjectDN -ResolveGUIDs -TableView
```

## powerview enumerate gmsa rights for a target account
```
Get-ObjectAcl <gmsa_account> -Select SecurityIdentifier,AccessMask,ActiveDirectoryRights,ObjectAceType -Where 'ObjectAceType eq ms-DS-ManagedPassword' -ResolveGUIDs -TableView
```

## powerview enumerate gpo rights
```
Get-DomainObjectAcl 'CN=<gpo_name>,CN=Policies,CN=System,DC=<netbios>,DC=<tld>' -ResolveGUIDs -Select SecurityIdentifier,ActiveDirectoryRights -TableView
```

## powerview restore deleted object
```
Restore-DomainObject -Identity '<target_dn>'
```
