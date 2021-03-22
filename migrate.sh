#!/bin/bash

src=/Users/dale/src/dlbewley.github.io/_posts
img_src=/Users/dale/src/dlbewley.github.io/images
dst=/Users/dale/src/dwnwrd-src/content/blog
img_dst=/Users/dale/src/dwnwrd-src/static/images


for f in $src/*; do

    old_filename=`basename $f`
    pubdate=`echo $old_filename | sed -e 's/^\([0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}\)-\(.*\)$/\1/'`
    new_filename=`echo $old_filename | sed -e 's/^\([0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}\)-\(.*\)$/\2/'`

    echo $dst/$new_filename

    banner=`grep '\[\!' $src/$old_filename \
        | head -1 \
        | gsed 's/^[^(]*(\([^(]*\)).*$/\1/'`

    cp -p "$src/$old_filename" "$dst/$new_filename"

    gsed -i \
         -e "/^title:/a\date: $pubdate" \
            $dst/$new_filename

         perl -p -i -e 's/^{%\s?highlight\s([a-z]+)\s?%}.*$/```\1/ig; s/^{%\s?end.*$/```/ig' \
            $dst/$new_filename

    if [ -n "$banner" ]; then
         gsed -i \
            -e "/^title:/a\banner: $banner" \
            $dst/$new_filename
    fi
done

cp -rp $img_src/* $img_dst/
