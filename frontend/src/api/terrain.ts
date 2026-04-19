import client from './client'

export interface TerrainFeatures {
  centerline: unknown | null
  cross_sections: unknown[] | null
  elevation_range: [number, number] | null
  slope_analysis: Record<string, unknown> | null
}

export interface TerrainData {
  id: string
  project_id: string
  file_type: string
  status: string
  features: TerrainFeatures | null
  feature_count: number | null
}

export interface TerrainUploadResponse extends TerrainData {
  warning: { code: string; message: string } | null
}

export interface TerrainStatus {
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
}

export const terrainApi = {
  upload: (projectId: string, file: File, onProgress?: (percent: number) => void) => {
    const formData = new FormData()
    formData.append('file', file)
    return client.post<TerrainUploadResponse>(`/projects/${projectId}/terrain`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (e.total && onProgress) {
          onProgress(Math.round((e.loaded * 100) / e.total))
        }
      },
    })
  },

  get: (projectId: string) =>
    client.get<TerrainData | null>(`/projects/${projectId}/terrain`),

  getStatus: (projectId: string) =>
    client.get<TerrainStatus>(`/projects/${projectId}/terrain/status`),
}
