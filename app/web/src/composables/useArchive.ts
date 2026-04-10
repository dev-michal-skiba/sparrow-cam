import { ref, watchEffect, type Ref } from 'vue'
import type { ArchiveApiResponse, MonthArchive } from '../types/archive'

const cache = new Map<string, MonthArchive>()

export function useArchive(year: Ref<number>, month: Ref<number>) {
  const archive = ref<MonthArchive>(new Map())
  const loading = ref(false)

  watchEffect(async () => {
    const y = year.value
    const m = month.value
    const cacheKey = `${y}-${m}`

    if (cache.has(cacheKey)) {
      archive.value = cache.get(cacheKey)!
      return
    }

    loading.value = true

    const mm = String(m + 1).padStart(2, '0')
    const lastDay = new Date(y, m + 1, 0).getDate()
    const from = `${y}-${mm}-01`
    const to = `${y}-${mm}-${String(lastDay).padStart(2, '0')}`

    try {
      const res = await fetch(`/archive/api?from=${from}&to=${to}`)
      if (!res.ok) {
        archive.value = new Map()
        return
      }
      const data: ArchiveApiResponse = await res.json()
      const result: MonthArchive = new Map()

      const yearData = data[String(y)]
      if (yearData) {
        const monthData = yearData[mm]
        if (monthData) {
          for (const dayStr of Object.keys(monthData)) {
            const day = parseInt(dayStr, 10)
            const streams = Object.keys(monthData[dayStr]).sort()
            result.set(day, { day, streams })
          }
        }
      }

      cache.set(cacheKey, result)
      archive.value = result
    } catch {
      archive.value = new Map()
    } finally {
      loading.value = false
    }
  })

  return { archive, loading }
}
