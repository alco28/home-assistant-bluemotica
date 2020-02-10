#!/bin/bash
date

folder=/config/temp
id=$(date +"%y-%m-%d_%H-%M-%S")
rtsp_url=rtsp://admin:xxx@192.168.xx.xx:554/12
frames=100
fps=5

mkdir $folder
ffmpeg -y -i $rtsp_url -r $fps -frames:v $frames -vcodec copy $folder/$id.mp4
ls -lh $folder/$id.mp4 $folder/output.mp4
cp $folder/$id.mp4 $folder/output.mp4
ls  -lh $folder/$id.mp4 $folder/output.mp4
find $folder -type f -name '*.mp4' -mtime +30 -exec rm {} \;