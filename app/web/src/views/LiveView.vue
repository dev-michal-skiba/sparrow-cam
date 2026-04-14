<template>
  <div class="page">
    <main class="main-content">
      <section>
        <VideoPlayer @segment-change="onSegmentChange" />
        <ArchiveBirdStatus :current-detections="currentDetections" :meta-available="metaAvailable" />
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import ArchiveBirdStatus from '../components/ArchiveBirdStatus.vue'
import VideoPlayer from '../components/VideoPlayer.vue'
import { useAnnotations } from '../composables/useAnnotations'

const currentSegment = ref<string | null>(null)

const { currentDetections, metaAvailable } = useAnnotations(currentSegment)

function onSegmentChange(segment: string | null) {
  currentSegment.value = segment
}
</script>

<style scoped>
.page {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.main-content {
  width: 100%;
}

section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
</style>
