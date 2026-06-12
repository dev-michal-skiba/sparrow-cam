import { computed } from 'vue'
import { useRoute, useRouter, type LocationQueryRaw } from 'vue-router'

export function useFilterQuery() {
  const route = useRoute()
  const router = useRouter()

  // The filter-related query keys, for propagating filters across navigation.
  const filterQuery = computed<LocationQueryRaw>(() => {
    const q: LocationQueryRaw = {}
    if (route.query.birds) q.birds = String(route.query.birds)
    if (route.query.annotation) q.annotation = String(route.query.annotation)
    return q
  })

  // Default = no birds selected and the default annotation filter (annotation absent).
  const isDefaultFilter = computed(() => !route.query.birds && !route.query.annotation)

  function resetFilters() {
    const query = { ...route.query }
    delete query.birds
    delete query.annotation
    router.replace({ query })
  }

  return { filterQuery, isDefaultFilter, resetFilters }
}
