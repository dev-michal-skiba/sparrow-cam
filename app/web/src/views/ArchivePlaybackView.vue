<template>
  <div class="page">
    <div class="top-bar">
      <RouterLink to="/archive" class="back-link">&#8592; Archive</RouterLink>
      <span class="stream-title">{{ formattedTitle }}</span>
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

const route = useRoute()
const { year, month, day, stream } = route.params as Record<string, string>

const playlistUrl = `/archive/storage/${year}/${month}/${day}/${stream}/sparrow_cam.m3u8`
const metaUrl = `/archive/storage/${year}/${month}/${day}/${stream}/meta.json`

const currentSegment = ref<string | null>(null)
const { currentDetections, metaAvailable } = useArchiveMeta(metaUrl, currentSegment)

const formattedTitle = computed(() => {
  const d = new Date(Number(year), Number(month) - 1, Number(day))
  const dateStr = d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
  const match = (stream as string).match(/T(\d{2})(\d{2})(\d{2})Z/)
  const timeStr = match ? `${match[1]}:${match[2]}:${match[3]} UTC` : stream
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
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 15px;
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
