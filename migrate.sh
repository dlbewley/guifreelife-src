#!/bin/bash

# adoc todo
# can not use level `=`
# includes default to / of repo
# syntax highlight sucks

src=/Users/dale/src/dlbewley.github.io/_posts
img_src=/Users/dale/src/dlbewley.github.io/images
dst=/Users/dale/src/dwnwrd-src/content/blog
img_dst=/Users/dale/src/dwnwrd-src/static/images
banner_dir=/Users/dale/src/dwnwrd-src/static/img/banners

get_banner() {
    qty=`ls -1 $banner_dir/banner* | wc -l`
    banner="/img/banners/banner-$((1 + $RANDOM % $qty)).jpg"
}

for f in $src/*; do

    old_filename=`basename $f`
    pubdate=`echo $old_filename | sed -e 's/^\([0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}\)-\(.*\)$/\1/'`
    new_filename=`echo $old_filename | sed -e 's/^\([0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}\)-\(.*\)$/\2/'`

    echo $dst/$new_filename

    banner=`grep -E '(\[\!|\!\[)' $src/$old_filename \
        | head -1 \
        | gsed 's/^[^(]*(\([^(]*\)).*$/\1/'`

    if [ -z "$banner" ]; then
        get_banner
    fi

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
