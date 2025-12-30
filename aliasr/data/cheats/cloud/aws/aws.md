# AWS
#target/remote #os/linux #cat/cloud #cat/aws

## List S3 bucket
```
aws s3 ls s3://<fqdn> --no-sign-request
```

## Download S3 bucket content
```
aws s3 cp s3://<fqdn>/<path> . --no-sign-request
```
