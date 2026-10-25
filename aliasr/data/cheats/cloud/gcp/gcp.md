# GCP
#target/remote #os/linux #cat/cloud #cat/gcp

## gcp query metadata
```
curl -sH 'Metadata-Flavor: Google' http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token | cut -d'"' -f4
```
