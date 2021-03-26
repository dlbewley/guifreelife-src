BANNER_DIR=static/img/banners

all: banners thumbnails photogrid

# gather and process images for banners
banners:
	./mkbanners.sh

# https://legacy.imagemagick.org/Usage/thumbnails/#cut
# these thumbnails will be 200x200 even if the image aspect ratio would
# preclude a square
thumbnails:
	pushd $(BANNER_DIR); \
	mkdir -p thumb; \
	for f in banner-*.jpg; do \
		convert -define jpeg:size=200x200 $$f  -thumbnail 200x200^ -gravity center -extent 200x200  thumb/$$f; \
	done; popd
#		convert -define jpeg:size=200x200 $$f  -thumbnail 100x100^ -gravity center -extent 100x100  thumb/$$f; \

# create a 10x4 thumbnail 2000pX800p  grid
photogrid:
	montage -verbose -mode Concatenate -tile 10x4 $(BANNER_DIR)/thumb/* montage.jpg; \
	mv montage-0.jpg static/img/photogrid.jpg
#	montage -verbose -background '#000000' -define jpeg:size=200x200 -geometry 200x200  -mode Concatenate  -auto-orient -tile 2000 thumb/* montage.jpg
#	montage -verbose -background '#000000' -fill 'gray' -define jpeg:size=200x200 -geometry 200x200  -mode Concatenate  -auto-orient -gravity South thumb/* montage.jpg

clean:
	rm -f montage*.jpg;

realclean: clean
	rm -rf $(BANNER_DIR)/thumb
