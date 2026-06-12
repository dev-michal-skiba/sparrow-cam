import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

export const BIRD_TYPES = ['Great tit', 'House sparrow', 'Pigeon', 'Eurasian nuthatch'] as const
export type BirdType = (typeof BIRD_TYPES)[number]

export const BIRD_SLUGS: Record<BirdType, string> = {
  'Great tit': 'great_tit',
  'Pigeon': 'pigeon',
  'House sparrow': 'house_sparrow',
  'Eurasian nuthatch': 'eurasian_nuthatch',
}

const SLUG_TO_BIRD: Record<string, string> = Object.fromEntries(
  Object.entries(BIRD_SLUGS).map(([name, slug]) => [slug, name]),
)

export function unslugBird(slug: string): string {
  return SLUG_TO_BIRD[slug] ?? slug
}

export function useBirdFilter() {
  const route = useRoute()
  const router = useRouter()

  const selectedBirds = computed<Set<BirdType>>(() => {
    const raw = route.query.birds ? String(route.query.birds).split(',') : []
    return new Set(BIRD_TYPES.filter((b) => raw.includes(BIRD_SLUGS[b])))
  })

  function toggleBird(bird: BirdType) {
    const next = new Set(selectedBirds.value)
    if (next.has(bird)) {
      next.delete(bird)
    } else {
      next.add(bird)
    }
    const slugs = [...next].map((b) => BIRD_SLUGS[b])
    const query = { ...route.query }
    if (slugs.length) query.birds = slugs.join(',')
    else delete query.birds
    router.replace({ query })
  }

  const selectedBirdsArray = computed(() => [...selectedBirds.value])
  const birdsParam = computed(() => selectedBirdsArray.value.map((b) => BIRD_SLUGS[b]).join(','))

  return { selectedBirds, selectedBirdsArray, toggleBird, birdsParam }
}
