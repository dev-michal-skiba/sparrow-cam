<template>
  <header class="page-header">
    <RouterLink to="/" class="header-link">
      <img src="/icon.png" alt="Sparrow Cam logo" class="logo" />
      <span class="title">SparrowCam</span>
    </RouterLink>
    <nav class="nav">
      <RouterLink :to="archiveTo" class="nav-link">Archive</RouterLink>
    </nav>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useFilterQuery } from '../composables/useFilterQuery'

const route = useRoute()
const { filterQuery } = useFilterQuery()

const archiveTo = computed(() => {
  const year = route.params.year || route.query.year
  const month = route.params.month || route.query.month
  const query: Record<string, string> = { ...filterQuery.value as Record<string, string> }
  if (year) query.year = String(year)
  if (month) query.month = String(month)
  return { path: '/archive', query }
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 12px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

@media (orientation: landscape) and (max-height: 500px) {
  .page-header {
    padding: 7px 20px;
  }
}

.header-link {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #ffffff;
  text-decoration: none;
}

.header-link:hover {
  opacity: 0.85;
}

.logo {
  width: 32px;
  height: 32px;
}

.title {
  font-size: 1.1rem;
  font-weight: 600;
}

.nav {
  display: flex;
  gap: 16px;
}

.nav-link {
  color: rgba(255, 255, 255, 0.6);
  text-decoration: none;
  font-size: 0.9rem;
}

.nav-link:hover,
.nav-link.router-link-active {
  color: #ffffff;
}
</style>
