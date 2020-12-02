rm -rf compass_out || true
mkdir compass_out

pushd compasses

for DIR in *; do
    pushd $DIR
    tar -czvf $DIR.tar.gz *
    mv $DIR.tar.gz ../../compass_out/$DIR.tar.gz
    popd
done

popd