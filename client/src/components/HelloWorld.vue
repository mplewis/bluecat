<template>
  <h1>{{ msg }}</h1>

  <p>
    Recommended IDE setup:
    <a href="https://code.visualstudio.com/" target="_blank">VSCode</a>
    +
    <a href="https://github.com/johnsoncodehk/volar" target="_blank">Volar</a>
  </p>

  <p>
    See
    <code>README.md</code> for more information.
  </p>

  <p>
    <a href="https://vitejs.dev/guide/features.html" target="_blank">Vite Docs</a>
    |
    <a href="https://v3.vuejs.org/" target="_blank">Vue 3 Docs</a>
  </p>

  <button type="button" @click="count++">count is: {{ count }}</button>
  <p>
    Edit
    <code>components/HelloWorld.vue</code> to test hot module replacement.
  </p>

  <div>
    <video autoplay="true" id="preview" @click="capture" />
  </div>
  <div>
    <canvas id="scratch"></canvas>
  </div>
  <div>
    <button @click="capture">Take photo</button>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import axios from 'axios'

defineProps<{ msg: string }>()


const captureQuality = 0.95

const count = ref(0)

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
  const response = await axios.post('/print', form, { headers })
  console.log(response)
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
