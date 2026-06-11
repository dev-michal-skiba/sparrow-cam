<template>
  <div class="archive-bird-status">
    <span v-if="title" class="status-title">{{ title }}</span>
    <template v-if="metaAvailable === null">
      <p class="status-text status-loading">Loading detection data…</p>
    </template>
    <template v-else-if="metaAvailable === false">
      <p class="status-text status-unavailable">Bird detection data not available for this stream.</p>
    </template>
    <template v-else>
      <div class="columns-row">
        <div class="detection-col" :class="{ 'detection-col--dimmed': hasManualAnnotations }">
          <span class="col-title">Auto detections</span>
          <div v-if="streamBirds !== undefined" class="info-row">
            <span class="info-label">In recording:</span>
            <span class="info-value" :class="streamBirds.length > 0 ? 'info-value--birds' : 'info-value--none'">
              {{ streamBirds.length > 0 ? streamBirds.map(unslugBird).join(', ') : 'None' }}
            </span>
          </div>
          <div class="info-row">
            <span class="info-label">On screen:</span>
            <span v-if="currentDetections.length === 0" class="info-value info-value--none">None</span>
            <span v-else class="info-value info-value--birds">
              {{ currentDetections.map(d => `${unslugBird(d.class)} (${(d.confidence * 100).toFixed(1)}%)`).join(', ') }}
            </span>
          </div>
        </div>
        <div v-if="hasManualAnnotations" class="detection-col">
          <span class="col-title">Manual annotations</span>
          <div class="info-row">
            <span class="info-label">In recording:</span>
            <span class="info-value" :class="(streamManualBirds ?? []).length > 0 ? 'info-value--birds' : 'info-value--none'">
              {{ (streamManualBirds ?? []).length > 0 ? (streamManualBirds ?? []).map(unslugBird).join(', ') : 'None' }}
            </span>
          </div>
          <div class="info-row">
            <span class="info-label">On screen:</span>
            <span v-if="(currentManualAnnotations ?? []).length === 0" class="info-value info-value--none">None</span>
            <span v-else class="info-value info-value--birds">
              {{ (currentManualAnnotations ?? []).map(a => unslugBird(a.bird_class)).join(', ') }}
            </span>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { Detection } from '../composables/useArchiveMeta'
import type { ROIAnnotation } from '../types/annotations'
import { unslugBird } from '../composables/useBirdFilter'

defineProps<{
  currentDetections: Detection[]
  metaAvailable: boolean | null
  streamBirds?: string[]
  title?: string
  hasManualAnnotations?: boolean
  currentManualAnnotations?: ROIAnnotation[]
  streamManualBirds?: string[]
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
  gap: 8px;
}

.status-title {
  font-size: 0.85rem;
  color: var(--primary-color);
  opacity: 0.75;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  width: 100%;
}

.status-text {
  font-size: 14px;
  font-weight: 500;
  margin: 0;
}

.status-loading,
.status-unavailable {
  color: rgba(255, 255, 255, 0.5);
}

.columns-row {
  display: flex;
  gap: 16px;
  width: 100%;
}

.detection-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detection-col--dimmed {
  opacity: 0.4;
}

.col-title {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.5);
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  width: 100%;
}

.info-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 14px;
}

.info-label {
  color: rgba(255, 255, 255, 0.5);
  font-weight: 500;
  white-space: nowrap;
}

.info-value {
  font-weight: 500;
}

.info-value--birds {
  color: var(--secondary-color);
}

.info-value--none {
  color: rgba(255, 255, 255, 0.5);
}

@media (max-width: 640px), (orientation: landscape) and (max-height: 500px) {
  .columns-row {
    flex-direction: column;
  }
}
</style>
