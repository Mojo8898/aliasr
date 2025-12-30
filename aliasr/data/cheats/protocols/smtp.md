# SMTP
#target/remote #os/linux #proto/smtp #port/25

## Send an email
```
swaks -t <target_user>@<domain> -f <from_user>@<domain> -h 'Subject: IMPORTANT' --body '<body>' -s <ip>
```

## Send an email with attachment
```
swaks -t <target_user>@<domain> -f <from_user>@<domain> --attach @<file> -h 'Subject: IMPORTANT' --body '<body>' -s <ip>
```

## Include authentication
```
swaks -t <target_user>@<domain> -f <from_user>@<domain> -au '<user>'@<domain> -ap <password> -h 'Subject: IMPORTANT' --body '<body>' -s <ip>
```

## Include domain
```
swaks -t <target_user>@<domain> -f <from_user>@<domain> -au '<user>'@<domain> -ap <password> -h 'Subject: IMPORTANT' --body '<body>' -s <ip> --ehlo <domain>
```
