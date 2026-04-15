<template>
  <div class="page">
    <ArchiveBirdFilter />
    <ArchiveCalendar />
  </div>
</template>

<script setup lang="ts">
import ArchiveCalendar from '../components/ArchiveCalendar.vue'
import ArchiveBirdFilter from '../components/ArchiveBirdFilter.vue'
</script>

<style scoped>
.page {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
