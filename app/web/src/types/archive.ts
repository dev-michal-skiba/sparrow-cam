export type ArchiveApiResponse = Record<string, Record<string, Record<string, Record<string, object>>>>

export interface DayArchive {
  day: number
  streams: string[]
}

export type MonthArchive = Map<number, DayArchive>
