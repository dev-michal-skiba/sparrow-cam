export type BirdSlug = 'great_tit' | 'house_sparrow' | 'pigeon' | 'eurasian_nuthatch'

export interface BoundingBox {
  x: number
  y: number
  width: number
  height: number
}

export interface ROIAnnotation {
  bird_class: BirdSlug
  bbox: BoundingBox
}

export type ManualAnnotationsMap = Record<string, ROIAnnotation[]>
