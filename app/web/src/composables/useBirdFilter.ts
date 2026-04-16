import { ref, computed } from 'vue'

export const BIRD_TYPES = ['Great tit', 'House sparrow', 'Pigeon'] as const
export type BirdType = (typeof BIRD_TYPES)[number]

export const BIRD_SLUGS: Record<BirdType, string> = {
  'Great tit': 'great_tit',
  'Pigeon': 'pigeon',
  'House sparrow': 'house_sparrow',
}

const SLUG_TO_BIRD: Record<string, string> = Object.fromEntries(
  Object.entries(BIRD_SLUGS).map(([name, slug]) => [slug, name]),
)

export function unslugBird(slug: string): string {
  return SLUG_TO_BIRD[slug] ?? slug
}

const selectedBirds = ref<Set<BirdType>>(new Set())

export function useBirdFilter() {
  function toggleBird(bird: BirdType) {
    const next = new Set(selectedBirds.value)
    if (next.has(bird)) {
      next.delete(bird)
    } else {
      next.add(bird)
    }
    selectedBirds.value = next
  }

  const selectedBirdsArray = computed(() => [...selectedBirds.value])
  const birdsParam = computed(() => selectedBirdsArray.value.map((b) => BIRD_SLUGS[b]).join(','))

  return { selectedBirds, selectedBirdsArray, toggleBird, birdsParam }
}
