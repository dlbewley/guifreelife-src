#!/usr/bin/env zsh

cd /Users/dale/src/guifreelife-src
mkdir -p stingers/examples

for style in electro industrial chiptune drum_n_bass ambient minimal glitch; do
  python3 stingers/make_stinger.py \
    --audio-style "$style" \
    --duration 5s \
    --stem "stinger_${style}" \
    --output stingers/examples \
    --seed 42 \
    > /tmp/stinger_${style}.log 2>&1 &
  echo "  launched: $style (pid $!)"
done

echo "waiting for all renders..."
wait
echo "done"
