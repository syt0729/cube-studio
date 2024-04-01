FROM syt-yolov7-flask:20240326

RUN mkdir /images
COPY 1.jpg /images
COPY /service-deploy/ /yolov7

WORKDIR /yolov7
RUN mkdir UPLOAD_FOLDER
# COPY ./service_deploy/ /yolov7
ENTRYPOINT ["python", "server-web-yolov7-syt.py"]