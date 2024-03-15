PACKAGE_DIR="./"
docker images --format '{{.Repository}}:{{.Tag}}' | while read IMAGE; do
    # 为每个镜像创建一个子目录
    IMG_DIR="$PACKAGE_DIR/$(echo $IMAGE | tr '/' '-')"
    # mkdir -p "$IMG_DIR"
    
    # 保存镜像为tar文件
    docker save "$IMAGE" -o "${IMAGE//\//_}.tar"
done