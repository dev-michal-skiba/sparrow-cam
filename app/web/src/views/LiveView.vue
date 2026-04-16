<template>
  <div class="page">
    <main class="main-content">
      <section>
        <div class="player-wrap">
          <VideoPlayer @segment-change="onSegmentChange" />
        </div>
        <div class="meta-wrap">
          <ArchiveBirdStatus :current-detections="currentDetections" :meta-available="metaAvailable" />
        </div>
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

@media (orientation: landscape) and (max-height: 500px) {
  section {
    flex-direction: row;
    align-items: stretch;
    gap: 0;
  }

  .meta-wrap {
    order: 1;
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    padding: 8px 14px;
    background: rgba(15, 23, 42, 0.25);
    border-right: 1px solid rgba(3, 182, 3, 0.2);
  }

  .player-wrap {
    order: 2;
    flex: 0 0 62%;
    padding-left: 14px;
    align-self: flex-start;
  }
}
</style>
