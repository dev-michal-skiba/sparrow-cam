<template>
  <button class="day" :class="{ today: isToday, future: isFuture }" :disabled="isFuture" @click="$emit('click')">
    <span class="day-number">{{ day }}</span>
    <span v-if="streamCount > 0" class="badge">{{ streamCount }}</span>
  </button>
</template>

<script setup lang="ts">
defineProps<{
  day: number
  streamCount: number
  isToday: boolean
  isFuture: boolean
}>()

defineEmits<{ click: [] }>()
</script>

<style scoped>
.day {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 8px 4px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: none;
  color: var(--primary-color);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.9rem;
  transition: background 0.15s, border-color 0.15s;
  min-height: 60px;
}

.day:not(.future):hover {
  background: var(--accent-soft);
  border-color: var(--secondary-color);
}

.day.today {
  border-color: var(--secondary-color);
  background: var(--accent-soft);
}

.day.future {
  opacity: 0.3;
  cursor: default;
}

.day-number {
  font-size: 0.95rem;
}

.badge {
  font-size: 0.7rem;
  background: var(--secondary-color);
  color: #0a0a0a;
  border-radius: 10px;
  padding: 1px 6px;
  font-weight: 600;
  line-height: 1.4;
}
</style>
