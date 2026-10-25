# Simulated IP camera: MediaMTX + ffmpeg looping a CC-BY 4.0 sample video of people walking
# (intel-iot-devkit/sample-videos, people-detection.mp4).
FROM bluenviron/mediamtx:1.21.2-ffmpeg

SHELL ["/bin/ash", "-eo", "pipefail", "-c"]

ARG VIDEO_URL=https://github.com/intel-iot-devkit/sample-videos/raw/master/people-detection.mp4
ARG VIDEO_SHA256=18ffe8672d741e3e29c9d891d22c59d453720b086c25b35c88b393d55f92f693
# the build fails if the download does not match the pinned digest
RUN mkdir -p /media \
    && wget -q -O /media/sample.mp4 "$VIDEO_URL" \
    && echo "$VIDEO_SHA256  /media/sample.mp4" | sha256sum -c -
COPY mediamtx.yml /mediamtx.yml

EXPOSE 8554 9997
# healthy only when the stream can actually be opened and decoded
HEALTHCHECK --interval=10s --timeout=8s --start-period=10s --retries=3 \
    CMD ffprobe -v error -rtsp_transport tcp -i rtsp://localhost:8554/cam1 \
        -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 | grep -q h264
