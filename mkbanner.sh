#!/bin/bash

INPUT=/Users/dale/Downloads/Pictures/banners
OUTPUT=/Users/dale/src/dwnwrd-src/static/img/banners/banner
GEOM="1000x750"
THUMBDIR="thumb"

pushd $INPUT

mkdir -p $THUMBDIR
rm -f $THUMBDIR/*

for img in *.jpeg *.jpg; do
    convert -geometry "$GEOM" "$img" "$THUMBDIR/$img"
done

COUNTER=0
for img in $THUMBDIR/*.jpg $THUMBDIR/*.jpeg; do
    let COUNTER=COUNTER+1
    cp -p "$img" "${OUTPUT}-${COUNTER}.jpg"
    echo $img
done

popd