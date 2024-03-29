<template>
  <h1>Photo Booth</h1>
  <div>
    <video autoplay="true" id="preview" @click="capture" />
  </div>
  <div>
    <canvas id="scratch"></canvas>
  </div>
  <div>
    <button @click="capture">Take photo</button>
  </div>
  <div>
    <button @click="feed">Feed paper</button>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import axios from 'axios'

const captureQuality = 0.95

var dimensions: { width: number, height: number } | null = null

async function connectCamera() {
  const video: HTMLMediaElement | null = document.querySelector("#preview");
  if (!video) {
    throw new Error("Video element not found");
  }
  if (!navigator.mediaDevices.getUserMedia) {
    throw new Error("Webcam permission not granted")
  }
  const stream = await navigator.mediaDevices.getUserMedia({ video: true })
  video.srcObject = stream;
  video.addEventListener('canplay', function () {
    dimensions = { width: video.videoWidth, height: video.videoHeight }
  })
}

function capture() {
  const canvas: HTMLCanvasElement | null = document.querySelector("#scratch");
  if (!canvas) {
    throw new Error("Canvas element not found");
  }
  const video: HTMLMediaElement | null = document.querySelector("#preview");
  if (!video) {
    throw new Error("Video element not found");
  }
  const context = canvas.getContext('2d');
  if (!context) {
    throw new Error("Canvas context not found");
  }

  if (!dimensions) {
    throw new Error("Video not ready yet");
  }
  const { width, height } = dimensions

  canvas.width = width;
  canvas.height = height;
  context.drawImage(video, 0, 0, width, height);

  canvas.toBlob(function (blob) {
    if (!blob) {
      throw new Error("Canvas toBlob failed");
    }
    sendToPrinter(blob)
  }, 'image/jpeg', captureQuality);
}

async function sendToPrinter(blob: Blob) {
  const form = new FormData()
  form.append('image', blob)
  const headers = { 'Content-Type': 'multipart/form-data' }
  const resp = await axios.post('/print', form, { headers })
  console.log(resp)
}

async function feed() {
  const resp = await axios.post('/feed')
  console.log(resp)
}

onMounted(() => {
  connectCamera()
})
</script>

<style lang="scss" scoped>
a {
  color: #42b983;
}

label {
  margin: 0 0.5em;
  font-weight: bold;
}

code {
  background-color: #eee;
  padding: 2px 4px;
  border-radius: 4px;
  color: #304455;
}

#preview {
  border: 1px solid #ccc;
}
</style>
