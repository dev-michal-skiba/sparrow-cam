import { ref, onMounted } from 'vue'

interface AdjacentRecording {
  year: string
  month: string
  day: string
  stream: string
}

interface AdjacentResult {
  previous: AdjacentRecording | null
  next: AdjacentRecording | null
}

export function useArchiveAdjacent(year: string, month: string, day: string, stream: string) {
  const previous = ref<AdjacentRecording | null>(null)
  const next = ref<AdjacentRecording | null>(null)

  onMounted(async () => {
    try {
      const params = new URLSearchParams({ year, month, day, stream })
      const response = await fetch(`/archive/api/adjacent?${params}`)
      if (!response.ok) return
      const data: AdjacentResult = await response.json()
      previous.value = data.previous
      next.value = data.next
    } catch {
      // leave as null
    }
  })

  return { previous, next }
}
