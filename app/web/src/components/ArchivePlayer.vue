<template>
  <div class="video-shell">
    <video ref="videoRef" controls playsinline muted></video>
  </div>
</template>

<script setup lang="ts">
import Hls from 'hls.js'
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps<{ playlistUrl: string }>()

const videoRef = ref<HTMLVideoElement | null>(null)
let hls: Hls | null = null

onMounted(() => {
  const video = videoRef.value
  if (!video) return

  if (Hls.isSupported()) {
    hls = new Hls({ startPosition: 0 })
    hls.loadSource(props.playlistUrl)
    hls.attachMedia(video)
    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      video.currentTime = 0
      video.pause()
    })
  } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = props.playlistUrl
    video.addEventListener('loadedmetadata', () => {
      video.currentTime = 0
      video.pause()
    }, { once: true })
  }
})

onUnmounted(() => {
  hls?.destroy()
  hls = null
})
</script>

<style scoped>
.video-shell {
  position: relative;
  border-radius: 14px;
  overflow: hidden;
  background: #020617;
  border: 1px solid rgba(15, 23, 42, 0.3);
  width: 100%;
  max-width: 100%;
  display: inline-block;
}

video {
  display: block;
  width: var(--player-width);
  height: auto;
  max-height: calc(100vh - 220px);
  border: none;
  border-radius: inherit;
}

@media (max-width: 900px) and (orientation: landscape) {
  .video-shell,
  video {
    width: 100%;
    max-width: 100%;
  }

  video {
    max-height: 80vh;
  }
}
</style>
