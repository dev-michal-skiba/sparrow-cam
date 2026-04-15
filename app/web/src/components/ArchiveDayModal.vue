<template>
  <div class="overlay" @click.self="$emit('close')">
    <div class="card">
      <div class="card-header">
        <span class="title">{{ formattedDate }}</span>
        <button class="close-btn" @click="$emit('close')">✕</button>
      </div>
      <div class="stream-list">
        <RouterLink
          v-for="stream in streams"
          :key="stream.name"
          class="stream-item"
          :to="{ name: 'archive-playback', params: { year, month: paddedMonth, day: paddedDay, stream: stream.name } }"
          @click="$emit('close')"
        >
          <span class="stream-time">{{ formatStreamName(stream.name) }}</span>
          <span v-if="stream.birds.length > 0" class="stream-birds">
            <span v-for="bird in stream.birds" :key="bird" class="bird-tag">{{ bird }}</span>
          </span>
        </RouterLink>
        <p v-if="streams.length === 0" class="empty">No streams for this day.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { RouterLink } from 'vue-router'
import type { StreamInfo } from '../types/archive'

const props = defineProps<{
  year: number
  month: number
  day: number
  streams: StreamInfo[]
}>()

const emit = defineEmits<{ close: [] }>()

const paddedMonth = computed(() => String(props.month).padStart(2, '0'))
const paddedDay = computed(() => String(props.day).padStart(2, '0'))

const formattedDate = computed(() => {
  const d = new Date(props.year, props.month - 1, props.day)
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
})

function formatStreamName(name: string): string {
  // stream names follow: auto_YYYY-MM-DDTHHMMSSZZ_id
  const match = name.match(/(\d{4})-(\d{2})-(\d{2})T(\d{2})(\d{2})(\d{2})Z/)
  if (match) {
    const d = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]), Number(match[4]), Number(match[5]), Number(match[6])))
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
  }
  return name
}

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}

onMounted(() => document.addEventListener('keydown', onKeyDown))
onUnmounted(() => document.removeEventListener('keydown', onKeyDown))
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.card {
  background: #111;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  width: min(420px, calc(100vw - 32px));
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.title {
  color: var(--primary-color);
  font-size: 1rem;
}

.close-btn {
  background: none;
  border: none;
  color: var(--primary-color);
  cursor: pointer;
  font-size: 1rem;
  opacity: 0.6;
  padding: 4px;
  font-family: inherit;
  line-height: 1;
}

.close-btn:hover {
  opacity: 1;
}

.stream-list {
  overflow-y: auto;
  padding: 8px 0;
}

.stream-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 20px;
  color: var(--primary-color);
  text-decoration: none;
  font-size: 0.9rem;
  transition: background 0.15s, color 0.15s;
}

.stream-item:hover {
  background: var(--accent-soft);
  color: var(--secondary-color);
}

.stream-time {
  flex-shrink: 0;
}

.stream-birds {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: flex-end;
}

.bird-tag {
  background: rgba(3, 182, 3, 0.12);
  border: 1px solid rgba(3, 182, 3, 0.3);
  border-radius: 10px;
  color: var(--secondary-color);
  font-size: 0.75rem;
  padding: 2px 8px;
}

.empty {
  padding: 16px 20px;
  color: var(--primary-color);
  opacity: 0.5;
  font-size: 0.9rem;
  margin: 0;
}
</style>
