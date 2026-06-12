<template>
  <div class="bird-filter">
    <button v-if="showReset" class="filter-btn reset-btn" :class="{ 'reset-btn--inactive': isDefaultFilter }" :disabled="isDefaultFilter" @click="resetFilters">Reset</button>
    <button
      v-for="bird in visibleBirdTypes"
      :key="bird"
      class="filter-btn"
      :class="{ active: selectedBirds.has(bird) }"
      @click="toggleBird(bird)"
    >
      {{ bird }}
    </button>
    <button
      v-for="filter in visibleAnnotationFilters"
      :key="filter"
      class="filter-btn"
      :class="{ active: selectedAnnotationFilter === filter }"
      @click="toggleAnnotationFilter(filter)"
    >
      {{ filter }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { BIRD_TYPES, BIRD_SLUGS, useBirdFilter } from '../composables/useBirdFilter'
import { ANNOTATION_FILTERS, useAnnotationsFilter, type AnnotationFilter } from '../composables/useAnnotationsFilter'
import { useFilterQuery } from '../composables/useFilterQuery'

const props = defineProps<{ availableBirds?: string[]; availableAnnotationFilters?: string[]; showReset?: boolean }>()

const { selectedBirds, toggleBird } = useBirdFilter()
const { selectedAnnotationFilter, toggleAnnotationFilter } = useAnnotationsFilter()
const { isDefaultFilter, resetFilters } = useFilterQuery()

const visibleAnnotationFilters = computed<AnnotationFilter[]>(() => {
  if (!props.availableAnnotationFilters) return [...ANNOTATION_FILTERS]
  return ANNOTATION_FILTERS.filter((f) => props.availableAnnotationFilters!.includes(f))
})

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

.reset-btn {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.45);
  color: var(--primary-color);
  font-weight: 600;
  opacity: 1;
}

.reset-btn:not(.reset-btn--inactive):hover {
  background: rgba(255, 255, 255, 0.2);
  border-color: rgba(255, 255, 255, 0.6);
}

.reset-btn--inactive,
.reset-btn--inactive:hover {
  opacity: 0.2;
  cursor: default;
  background: none;
  border-color: rgba(255, 255, 255, 0.2);
  font-weight: normal;
}
</style>
