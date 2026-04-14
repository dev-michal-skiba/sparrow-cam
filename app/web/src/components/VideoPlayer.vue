<template>
  <div class="video-shell">
    <video ref="videoRef" controls autoplay playsinline muted></video>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useHlsPlayer } from '../composables/useHlsPlayer'

const emit = defineEmits<{
  segmentChange: [segment: string | null]
}>()

const videoRef = ref<HTMLVideoElement | null>(null)
const { currentSegment, setup } = useHlsPlayer(videoRef, '/hls/sparrow_cam.m3u8')

onMounted(() => {
  setup()
})

watch(currentSegment, (val) => emit('segmentChange', val))
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
