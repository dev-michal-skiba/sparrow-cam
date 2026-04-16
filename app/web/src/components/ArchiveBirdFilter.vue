<template>
  <div class="bird-filter">
    <button
      v-for="bird in visibleBirdTypes"
      :key="bird"
      class="filter-btn"
      :class="{ active: selectedBirds.has(bird) }"
      @click="toggleBird(bird)"
    >
      {{ bird }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { BIRD_TYPES, BIRD_SLUGS, useBirdFilter } from '../composables/useBirdFilter'

const props = defineProps<{ availableBirds?: string[] }>()

const { selectedBirds, toggleBird } = useBirdFilter()

const visibleBirdTypes = computed(() => {
  if (!props.availableBirds) return BIRD_TYPES
  return BIRD_TYPES.filter((bird) => props.availableBirds!.includes(BIRD_SLUGS[bird]))
})

watch(
  () => props.availableBirds,
  (slugs) => {
    if (!slugs) return
    for (const bird of [...selectedBirds.value]) {
      if (!slugs.includes(BIRD_SLUGS[bird])) {
        toggleBird(bird)
      }
    }
  },
)
</script>

<style scoped>
.bird-filter {
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
  overflow-x: auto;
  padding: 8px 15px;
  -webkit-overflow-scrolling: touch;
}

.filter-btn {
  background: none;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 20px;
  color: var(--primary-color);
  cursor: pointer;
  flex-shrink: 0;
  font-family: inherit;
  font-size: 0.8rem;
  opacity: 0.6;
  padding: 4px 12px;
  transition: background 0.15s, border-color 0.15s, opacity 0.15s;
  white-space: nowrap;
}

.filter-btn:hover {
  opacity: 1;
  border-color: rgba(255, 255, 255, 0.4);
}

.filter-btn.active {
  background: var(--accent-soft);
  border-color: var(--secondary-color);
  color: var(--secondary-color);
  opacity: 1;
}
</style>
