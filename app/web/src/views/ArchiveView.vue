<template>
  <div class="page">
    <ArchiveCalendar />
  </div>
</template>

<script setup lang="ts">
import ArchiveCalendar from '../components/ArchiveCalendar.vue'
</script>

<style scoped>
.page {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
