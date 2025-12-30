# NFS
#target/remote #os/linux #proto/nfs

## Mount remote share
```
mkdir nfs;mount -t nfs <ip>:<share> nfs -o nolock
```

## Mount & Copy
```
mkdir temp;mount -t nfs <ip>:<share> temp -o nolock;cp -r temp nfs;umount temp;rm -r temp
```

## Mount remote share version 2
```
mkdir nfs;mount -t nfs -o vers=2 <ip>:<share> nfs -o nolock
```
