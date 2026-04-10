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
          :key="stream"
          class="stream-item"
          :to="{ name: 'archive-playback', params: { year, month: paddedMonth, day: paddedDay, stream } }"
          @click="$emit('close')"
        >
          {{ formatStreamName(stream) }}
        </RouterLink>
        <p v-if="streams.length === 0" class="empty">No streams for this day.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { RouterLink } from 'vue-router'

const props = defineProps<{
  year: number
  month: number
  day: number
  streams: string[]
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
  const match = name.match(/(\d{4}-\d{2}-\d{2}T(\d{2})(\d{2})(\d{2})Z)/)
  if (match) {
    return `${match[2]}:${match[3]}:${match[4]} UTC`
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
  display: block;
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

.empty {
  padding: 16px 20px;
  color: var(--primary-color);
  opacity: 0.5;
  font-size: 0.9rem;
  margin: 0;
}
</style>
