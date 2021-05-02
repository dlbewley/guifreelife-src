#!/bin/bash
repo_dir=$(git rev-parse --show-toplevel)
post_dir=$repo_dir/content/blog
banner_dir=$repo_dir/static/img/banners

select_rand_banner() {
    qty=`ls -1 $banner_dir/banner* | wc -l`
    banner="/img/banners/banner-$((1 + $RANDOM % $qty)).jpg"
}

select_first_img() {
    # find first image in markdown file TODO make asciidoc smart
	grep -E '(\[\!|\!\[)' $1 \
        | head -1 \
        | gsed 's/^[^(]*(\([^(]*\)).*$/\1/'
}

for f in $post_dir/*; do
    grep '^banner: ' $f > /dev/null
    if [ $? -eq 0 ]; then
        # banner already defined
        continue
    fi

    first_img=''
	select_first_img $f
	if [ -n "$first_img" ]; then
        banner=$first_img
    else
        select_rand_banner
    fi

    if [ -n "$banner" ]; then
        echo "inserting banner $banner into $f"
        # creates a backup named ${f}-e
        #sed -i -e '/^title:/a\'$'\n'"banner: $banner"$'\n' "$f"
        # does not match
        #sed -i '' -e '/^title:/a\'$'\n'"banner: $banner"$'\n' "$f"
        sed -e '/^title:/a\'$'\n'"banner: $banner"$'\n' -i '' "$f"
    fi
done

