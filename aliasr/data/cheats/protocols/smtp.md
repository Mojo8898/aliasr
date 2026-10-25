# SMTP
#target/remote #os/linux #proto/smtp #port/25

## swaks send email
```
swaks -t <target_user>@<domain> -f <from_user>@<domain> -h 'Subject: IMPORTANT' --body '<body>' -s <ip>
```

## send email including attachment
```
swaks -t <target_user>@<domain> -f <from_user>@<domain> --attach @<file> -h 'Subject: IMPORTANT' --body '<body>' -s <ip>
```

## send email including authentication
```
swaks -t <target_user>@<domain> -f <from_user>@<domain> -au '<user>'@<domain> -ap <password> -h 'Subject: IMPORTANT' --body '<body>' -s <ip>
```

## send email including domain
```
swaks -t <target_user>@<domain> -f <from_user>@<domain> -au '<user>'@<domain> -ap <password> -h 'Subject: IMPORTANT' --body '<body>' -s <ip> --ehlo <domain>
```
