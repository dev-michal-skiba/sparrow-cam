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
  margin: 0 auto;
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

@media (max-width: 900px) and (orientation: landscape) {
  .layout {
    max-width: none;
    padding: 0 16px;
  }
}

@media (orientation: landscape) and (max-height: 500px) {
  .content {
    padding: 8px 0;
  }
}
</style>
