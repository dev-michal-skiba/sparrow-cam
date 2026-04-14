<template>
  <div class="layout">
    <AppHeader />
    <main class="content">
      <RouterView :key="$route.fullPath" />
    </main>
  </div>
</template>

<script setup lang="ts">
import AppHeader from './components/AppHeader.vue'
import { RouterView } from 'vue-router'
</script>

<style scoped>
.layout {
  width: 100%;
  max-width: var(--player-width);
  display: flex;
  flex-direction: column;
}

.content {
  padding: 24px 0;
}

@media (max-width: 640px) {
  .content {
    padding: 16px 0;
  }
}
</style>
