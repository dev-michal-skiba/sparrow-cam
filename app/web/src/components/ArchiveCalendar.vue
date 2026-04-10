<template>
  <div class="calendar">
    <div class="nav">
      <button class="nav-btn" @click="prevMonth">&#8249;</button>
      <span class="month-label">{{ monthLabel }}</span>
      <button class="nav-btn" :class="{ disabled: !canGoNext }" :disabled="!canGoNext" @click="nextMonth">&#8250;</button>
    </div>
    <div class="weekdays">
      <span v-for="wd in weekdays" :key="wd" class="weekday">{{ wd }}</span>
    </div>
    <div class="grid">
      <span v-for="i in firstDayOffset" :key="`empty-${i}`" class="empty-cell" />
      <ArchiveCalendarDay
        v-for="day in daysInMonth"
        :key="day"
        :day="day"
        :stream-count="archive.get(day)?.streams.length ?? 0"
        :is-today="isToday(day)"
        :is-future="isFuture(day)"
        @click="selectedDay = day"
      />
    </div>
    <ArchiveDayModal
      v-if="selectedDay !== null"
      :year="currentYear"
      :month="currentMonth + 1"
      :day="selectedDay"
      :streams="archive.get(selectedDay)?.streams ?? []"
      @close="selectedDay = null"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useArchive } from '../composables/useArchive'
import ArchiveCalendarDay from './ArchiveCalendarDay.vue'
import ArchiveDayModal from './ArchiveDayModal.vue'

const weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const now = new Date()
const currentYear = ref(now.getFullYear())
const currentMonth = ref(now.getMonth()) // 0-indexed
const selectedDay = ref<number | null>(null)

const { archive } = useArchive(currentYear, currentMonth)

const daysInMonth = computed(() => new Date(currentYear.value, currentMonth.value + 1, 0).getDate())

// firstDayOffset: how many empty cells before day 1 (Monday = 0, Sunday = 6)
const firstDayOffset = computed(() => {
  const jsDay = new Date(currentYear.value, currentMonth.value, 1).getDay() // 0=Sun
  return (jsDay + 6) % 7 // convert to Mon=0
})

const monthLabel = computed(() => {
  return new Date(currentYear.value, currentMonth.value, 1).toLocaleDateString('en-US', {
    month: 'long',
    year: 'numeric',
  })
})

const canGoNext = computed(() => {
  const nextM = currentMonth.value === 11 ? 0 : currentMonth.value + 1
  const nextY = currentMonth.value === 11 ? currentYear.value + 1 : currentYear.value
  return nextY < now.getFullYear() || (nextY === now.getFullYear() && nextM <= now.getMonth())
})

function prevMonth() {
  if (currentMonth.value === 0) {
    currentMonth.value = 11
    currentYear.value--
  } else {
    currentMonth.value--
  }
  selectedDay.value = null
}

function nextMonth() {
  if (!canGoNext.value) return
  if (currentMonth.value === 11) {
    currentMonth.value = 0
    currentYear.value++
  } else {
    currentMonth.value++
  }
  selectedDay.value = null
}

function isToday(day: number): boolean {
  return (
    currentYear.value === now.getFullYear() &&
    currentMonth.value === now.getMonth() &&
    day === now.getDate()
  )
}

function isFuture(day: number): boolean {
  const d = new Date(currentYear.value, currentMonth.value, day)
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  return d > today
}
</script>

<style scoped>
.calendar {
  width: var(--player-width);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px 8px;
}

.month-label {
  color: var(--primary-color);
  font-size: 1rem;
}

.nav-btn {
  background: none;
  border: none;
  color: var(--primary-color);
  font-size: 1.6rem;
  cursor: pointer;
  padding: 4px 10px;
  font-family: inherit;
  line-height: 1;
  border-radius: 6px;
  transition: background 0.15s;
}

.nav-btn:hover:not(:disabled) {
  background: var(--accent-soft);
}

.nav-btn.disabled {
  opacity: 0.3;
  cursor: default;
}

.weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
}

.weekday {
  text-align: center;
  color: var(--primary-color);
  opacity: 0.5;
  font-size: 0.75rem;
  padding: 4px 0;
}

.grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
}

.empty-cell {
  min-height: 60px;
}

@media (max-width: 900px) and (orientation: landscape) {
  .calendar {
    width: 100%;
  }
}

@media (max-width: 640px) {
  .calendar {
    width: 100%;
  }
}
</style>
