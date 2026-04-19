import client from './client'

export interface Project {
  id: string
  name: string
  description: string | null
  created_at: string
}

export interface CreateProjectRequest {
  name: string
  description?: string
}

export interface ProjectListResponse {
  projects: Project[]
  total: number
}

export const projectsApi = {
  list: (skip = 0, limit = 20) =>
    client.get<ProjectListResponse>('/projects', { params: { skip, limit } }),

  create: (data: CreateProjectRequest) =>
    client.post<Project>('/projects', data),

  get: (id: string) =>
    client.get<Project>(`/projects/${id}`),

  update: (id: string, data: Partial<CreateProjectRequest>) =>
    client.put<Project>(`/projects/${id}`, data),

  delete: (id: string) =>
    client.delete(`/projects/${id}`),
}
