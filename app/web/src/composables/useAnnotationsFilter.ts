import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

export const ANNOTATION_FILTERS = ['Exclude annotated', 'Exclude false positives'] as const
export type AnnotationFilter = (typeof ANNOTATION_FILTERS)[number]

const FILTER_PARAM_KEYS: Record<AnnotationFilter, string> = {
  'Exclude false positives': 'exclude_false_positives',
  'Exclude annotated': 'exclude_annotated',
}

export const DEFAULT_ANNOTATION_FILTER: AnnotationFilter = 'Exclude false positives'

export function useAnnotationsFilter() {
  const route = useRoute()
  const router = useRouter()

  // Route query encoding: absent -> default 'Exclude false positives',
  // 'exclude_annotated' -> that filter, 'none' -> explicitly deselected.
  const selectedAnnotationFilter = computed<AnnotationFilter | null>(() => {
    const a = route.query.annotation
    if (a === 'exclude_annotated') return 'Exclude annotated'
    if (a === 'none') return null
    return DEFAULT_ANNOTATION_FILTER
  })

  function setAnnotationFilter(filter: AnnotationFilter | null) {
    const query = { ...route.query }
    if (filter === DEFAULT_ANNOTATION_FILTER) delete query.annotation
    else if (filter === 'Exclude annotated') query.annotation = 'exclude_annotated'
    else query.annotation = 'none'
    router.replace({ query })
  }

  function toggleAnnotationFilter(filter: AnnotationFilter) {
    setAnnotationFilter(selectedAnnotationFilter.value === filter ? null : filter)
  }

  const annotationsParams = computed<Record<string, string>>(() => {
    if (!selectedAnnotationFilter.value) return {}
    return { [FILTER_PARAM_KEYS[selectedAnnotationFilter.value]]: 'true' }
  })

  return { selectedAnnotationFilter, toggleAnnotationFilter, annotationsParams }
}
