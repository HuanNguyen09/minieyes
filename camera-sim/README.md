# camera-sim

A stand-in for an IP camera: [MediaMTX](https://github.com/bluenviron/mediamtx) serves
`rtsp://<host>:8554/cam1`, fed by ffmpeg looping a sample video at 5 fps. If ffmpeg exits,
MediaMTX restarts it (`runOnInitRestart`).

The video ([people-detection.mp4](https://github.com/intel-iot-devkit/sample-videos),
© Intel, CC-BY 4.0) is downloaded at build time and verified by SHA-256; it is never committed.

```bash
docker build -t minieyes-camera-sim camera-sim
docker run --rm -p 8554:8554 minieyes-camera-sim
ffprobe -rtsp_transport tcp rtsp://localhost:8554/cam1      # or open it in VLC
```

To use another video, mount it over `/media/sample.mp4`.
