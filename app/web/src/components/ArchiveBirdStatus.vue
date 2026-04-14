<template>
  <div class="archive-bird-status">
    <template v-if="metaAvailable === null">
      <p class="status-text status-loading">Loading detection data…</p>
    </template>
    <template v-else-if="metaAvailable === false">
      <p class="status-text status-unavailable">Bird detection data not available for this stream.</p>
    </template>
    <template v-else-if="currentDetections.length === 0">
      <p class="status-text status-none">No birds detected in this segment.</p>
    </template>
    <template v-else>
      <ul class="detection-list">
        <li v-for="(detection, index) in currentDetections" :key="index" class="detection-item">
          <span class="detection-class">{{ detection.class }}</span>
          <span class="detection-confidence">{{ (detection.confidence * 100).toFixed(1) }}%</span>
        </li>
      </ul>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { Detection } from '../composables/useArchiveMeta'

defineProps<{
  currentDetections: Detection[]
  metaAvailable: boolean | null
}>()
</script>

<style scoped>
.archive-bird-status {
  padding: 12px 15px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.08);
  min-height: 44px;
  display: flex;
  align-items: flex-start;
  flex-direction: column;
  gap: 6px;
}

.status-text {
  font-size: 14px;
  font-weight: 500;
  margin: 0;
}

.status-loading,
.status-unavailable,
.status-none {
  color: rgba(255, 255, 255, 0.5);
}

.status-detected {
  color: var(--secondary-color);
}

.detection-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detection-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.detection-class {
  font-size: 14px;
  font-weight: 500;
  color: var(--secondary-color);
}

.detection-confidence {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.6);
}
</style>
