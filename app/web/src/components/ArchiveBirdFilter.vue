<template>
  <div class="bird-filter">
    <button
      v-for="bird in BIRD_TYPES"
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
import { BIRD_TYPES, useBirdFilter } from '../composables/useBirdFilter'

const { selectedBirds, toggleBird } = useBirdFilter()
</script>

<style scoped>
.bird-filter {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 15px;
}

.filter-btn {
  background: none;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 20px;
  color: var(--primary-color);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.8rem;
  opacity: 0.6;
  padding: 4px 12px;
  transition: background 0.15s, border-color 0.15s, opacity 0.15s;
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
