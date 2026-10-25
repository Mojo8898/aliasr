# NFS
#target/remote #os/linux #proto/nfs #port/2049

## mount nfs
```
mkdir nfs
mount -t nfs <ip>:<share> nfs -o nolock
```

## mount and copy nfs
```
mkdir temp
mount -t nfs <ip>:<share> temp -o nolock
cp -r temp nfs
umount temp
rm -r temp
```

## mount version 2
```
mkdir nfs
mount -t nfs -o vers=2 <ip>:<share> nfs -o nolock
```
