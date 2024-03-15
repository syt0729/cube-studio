for file in ./*.tar; do
    docker load -i "$file"
done