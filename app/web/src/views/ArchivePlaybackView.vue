<template>
  <div class="page">
    <div class="nav-bar">
      <RouterLink :to="`/archive?year=${year}&month=${month}`" class="back-link">&#8592; Back</RouterLink>
      <div class="adj-nav">
        <RouterLink
          v-if="previous"
          :to="`/archive/${previous.year}/${previous.month}/${previous.day}/${previous.stream}`"
          class="adj-link"
          title="Previous recording"
        >&#8592; Previous</RouterLink>
        <span v-else class="adj-link adj-link--disabled" title="No previous recording">&#8592;</span>
        <RouterLink
          v-if="next"
          :to="`/archive/${next.year}/${next.month}/${next.day}/${next.stream}`"
          class="adj-link"
          title="Next recording"
        >Next &#8594;</RouterLink>
        <span v-else class="adj-link adj-link--disabled" title="No next recording">&#8594;</span>
      </div>
    </div>
    <div class="divider" />
    <div class="filter-col">
      <ArchiveBirdFilter />
    </div>
    <div class="player-col">
      <ArchivePlayer :playlist-url="playlistUrl" @segment-change="currentSegment = $event" />
    </div>
    <div class="status-col">
      <ArchiveBirdStatus :current-detections="currentDetections" :meta-available="metaAvailable" :stream-birds="streamBirds" :title="formattedTitle" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import ArchivePlayer from '../components/ArchivePlayer.vue'
import ArchiveBirdStatus from '../components/ArchiveBirdStatus.vue'
import ArchiveBirdFilter from '../components/ArchiveBirdFilter.vue'
import { useArchiveMeta } from '../composables/useArchiveMeta'
import { useArchiveAdjacent } from '../composables/useArchiveAdjacent'
import { useBirdFilter } from '../composables/useBirdFilter'

const route = useRoute()
const { year, month, day, stream } = route.params as Record<string, string>

const playlistUrl = `/archive/storage/${year}/${month}/${day}/${stream}/sparrow_cam.m3u8`
const metaUrl = `/archive/storage/${year}/${month}/${day}/${stream}/meta.json`

const currentSegment = ref<string | null>(null)
const { currentDetections, metaAvailable, streamBirds } = useArchiveMeta(metaUrl, currentSegment)

const { birdsParam } = useBirdFilter()
const { previous, next } = useArchiveAdjacent(year, month, day, stream, birdsParam)

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

.nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 15px;
  gap: 8px;
}

.divider {
  border: none;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  margin: 0 15px;
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

.adj-nav {
  display: flex;
  gap: 4px;
}

.adj-link {
  color: var(--primary-color);
  text-decoration: none;
  opacity: 0.7;
  font-size: 0.9rem;
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

.player-col {
  width: 100%;
}

/* Landscape mobile: side-by-side layout — controls left, player right */
@media (orientation: landscape) and (max-height: 500px) {
  .page {
    display: grid;
    grid-template-columns: 40% 1fr;
    grid-template-areas:
      "nav    player"
      "sep    player"
      "filter player"
      "status player";
    align-items: start;
    gap: 0;
    background: linear-gradient(to right, rgba(15, 23, 42, 0.25) 40%, transparent 40%);
  }

  .nav-bar {
    grid-area: nav;
    padding: 6px 14px 4px;
  }

  .divider {
    grid-area: sep;
    margin: 2px 14px;
    border-top-color: rgba(255, 255, 255, 0.08);
  }

  .filter-col {
    grid-area: filter;
    padding: 4px 14px 2px;
  }

  .player-col {
    grid-area: player;
    border-left: 1px solid rgba(3, 182, 3, 0.2);
    padding-left: 14px;
    align-self: start;
  }

  .status-col {
    grid-area: status;
    padding: 2px 14px 4px;
  }
}
</style>
