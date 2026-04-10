<template>
  <div class="page">
    <div class="status-row">
      <StreamStatus :is-stream-active="isStreamActive" />
      <BirdStatus :detected="isBirdDetected" />
    </div>
    <main class="main-content">
      <section>
        <VideoPlayer @segment-change="onSegmentChange" @stream-status-change="onStreamStatusChange" />
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import StreamStatus from '../components/StreamStatus.vue'
import BirdStatus from '../components/BirdStatus.vue'
import VideoPlayer from '../components/VideoPlayer.vue'
import { useAnnotations } from '../composables/useAnnotations'

const currentSegment = ref<string | null>(null)
const isStreamActive = ref(false)

const { isBirdDetected } = useAnnotations(currentSegment)

function onSegmentChange(segment: string | null) {
  currentSegment.value = segment
}

function onStreamStatusChange(isActive: boolean) {
  isStreamActive.value = isActive
}
</script>

<style scoped>
.page {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 15px;
}

.main-content {
  width: 100%;
}

@media (max-width: 640px) {
  .status-row {
    flex-wrap: wrap;
  }
}
</style>
