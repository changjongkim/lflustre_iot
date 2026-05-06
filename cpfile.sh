
for file in *; do
  [ -f "$file" ] || continue
  base="${file%.*}"
  ext="${file##*.}"
  if [ "$base" = "$file" ]; then
    # no extension
    cp "$file" "${file}c"
  else
    # has extension
    cp "$file" "${base}c.${ext}"
  fi
done


