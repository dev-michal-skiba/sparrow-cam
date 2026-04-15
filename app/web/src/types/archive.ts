export interface StreamMeta {
  birds: string[]
}

export type ArchiveApiResponse = Record<string, Record<string, Record<string, Record<string, StreamMeta>>>>

export interface StreamInfo {
  name: string
  birds: string[]
}

export interface DayArchive {
  day: number
  streams: StreamInfo[]
}

export type MonthArchive = Map<number, DayArchive>
