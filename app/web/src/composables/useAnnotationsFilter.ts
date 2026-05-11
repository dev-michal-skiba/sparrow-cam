import { ref, computed } from 'vue'

export const ANNOTATION_FILTERS = ['Exclude annotated', 'Include false positives'] as const
export type AnnotationFilter = (typeof ANNOTATION_FILTERS)[number]

const FILTER_PARAM_KEYS: Record<AnnotationFilter, string> = {
  'Include false positives': 'include_false_positives',
  'Exclude annotated': 'exclude_annotated',
}

const selectedAnnotationFilter = ref<AnnotationFilter | null>(null)

export function useAnnotationsFilter() {
  function toggleAnnotationFilter(filter: AnnotationFilter) {
    selectedAnnotationFilter.value = selectedAnnotationFilter.value === filter ? null : filter
  }

  const annotationsParams = computed<Record<string, string>>(() => {
    if (!selectedAnnotationFilter.value) return {}
    return { [FILTER_PARAM_KEYS[selectedAnnotationFilter.value]]: 'true' }
  })

  return { selectedAnnotationFilter, toggleAnnotationFilter, annotationsParams }
}
