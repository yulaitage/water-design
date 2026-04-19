import client from './client'

export interface Specification {
  id: string
  name: string
  code: string
  chapter: string
  section: string | null
  content: string
  project_types: string[]
  created_at: string | null
}

export interface Case {
  id: string
  name: string
  project_type: string
  location: string
  owner: string
  summary: string | null
  design_params: Record<string, unknown>
  created_at: string | null
}

export interface RetrievalResult {
  source: 'specification' | 'case'
  title: string
  content: string
  relevance_score: number
  metadata: Record<string, unknown>
}

export const knowledgeApi = {
  listSpecifications: (skip = 0, limit = 20) =>
    client.get<Specification[]>('/knowledge-base/specifications', { params: { skip, limit } }),

  addSpecification: (data: Omit<Specification, 'id' | 'created_at'>) =>
    client.post<Specification>('/knowledge-base/specifications', data),

  listCases: (skip = 0, limit = 20) =>
    client.get<Case[]>('/knowledge-base/cases', { params: { skip, limit } }),

  addCase: (data: Omit<Case, 'id' | 'created_at'>) =>
    client.post<Case>('/knowledge-base/cases', data),

  search: (query: string, projectType?: string) =>
    client.get<RetrievalResult[]>('/knowledge-base/search', {
      params: { query, project_type: projectType },
    }),
}
