<template>
  <div class="page">
    <div class="top-bar">
      <RouterLink :to="`/archive?year=${year}&month=${month}`" class="back-link">&#8592; Back</RouterLink>
      <span class="stream-title">{{ formattedTitle }}</span>
      <div class="adj-nav">
        <RouterLink
          v-if="previous"
          :to="`/archive/${previous.year}/${previous.month}/${previous.day}/${previous.stream}`"
          class="adj-link"
          title="Previous recording"
        >&#8592;</RouterLink>
        <span v-else class="adj-link adj-link--disabled" title="No previous recording">&#8592;</span>
        <RouterLink
          v-if="next"
          :to="`/archive/${next.year}/${next.month}/${next.day}/${next.stream}`"
          class="adj-link"
          title="Next recording"
        >&#8594;</RouterLink>
        <span v-else class="adj-link adj-link--disabled" title="No next recording">&#8594;</span>
      </div>
    </div>
    <main class="main-content">
      <section>
        <ArchivePlayer :playlist-url="playlistUrl" @segment-change="currentSegment = $event" />
        <ArchiveBirdStatus :current-detections="currentDetections" :meta-available="metaAvailable" />
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import ArchivePlayer from '../components/ArchivePlayer.vue'
import ArchiveBirdStatus from '../components/ArchiveBirdStatus.vue'
import { useArchiveMeta } from '../composables/useArchiveMeta'
import { useArchiveAdjacent } from '../composables/useArchiveAdjacent'

const route = useRoute()
const { year, month, day, stream } = route.params as Record<string, string>

const playlistUrl = `/archive/storage/${year}/${month}/${day}/${stream}/sparrow_cam.m3u8`
const metaUrl = `/archive/storage/${year}/${month}/${day}/${stream}/meta.json`

const currentSegment = ref<string | null>(null)
const { currentDetections, metaAvailable } = useArchiveMeta(metaUrl, currentSegment)
const { previous, next } = useArchiveAdjacent(year, month, day, stream)

const formattedTitle = computed(() => {
  const d = new Date(Number(year), Number(month) - 1, Number(day))
  const dateStr = d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
  const match = (stream as string).match(/T(\d{2})(\d{2})(\d{2})Z/)
  let timeStr: string
  if (match) {
    const utcDate = new Date(Date.UTC(Number(year), Number(month) - 1, Number(day), Number(match[1]), Number(match[2]), Number(match[3])))
    timeStr = utcDate.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
  } else {
    timeStr = stream
  }
  return `${dateStr} — ${timeStr}`
})
</script>

<style scoped>
.page {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.top-bar {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  padding: 0 15px;
  gap: 8px;
}

.back-link {
  color: var(--primary-color);
  text-decoration: none;
  opacity: 0.7;
  font-size: 0.9rem;
  transition: opacity 0.15s;
  white-space: nowrap;
}

.back-link:hover {
  opacity: 1;
}

.stream-title {
  color: var(--primary-color);
  font-size: 0.9rem;
  opacity: 0.9;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.adj-nav {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
}

.adj-link {
  color: var(--primary-color);
  text-decoration: none;
  opacity: 0.7;
  font-size: 1.1rem;
  line-height: 1;
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  transition: opacity 0.15s, background 0.15s;
  user-select: none;
}

.adj-link:not(.adj-link--disabled):hover {
  opacity: 1;
  background: rgba(255, 255, 255, 0.07);
}

.adj-link--disabled {
  opacity: 0.2;
  cursor: default;
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
