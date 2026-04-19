import client from './client'

export interface ProjectInfo {
  name: string
  location: string
  owner: string
  scale: string
  description: string
}

export interface ReportTask {
  task_id: string
  status: string
  report_type: string
  version: number
}

export interface ReportStatus {
  task_id: string
  status: string
  progress: number
  current_chapter: string | null
  version: number
  error: string | null
}

export interface Revision {
  version: number
  created_at: string
  revision_type: string | null
  user_input: string | null
}

export interface RevisionHistory {
  revisions: Revision[]
}

export const reportsApi = {
  create: (projectId: string, reportType: string, projectInfo: ProjectInfo) =>
    client.post<ReportTask>(`/projects/${projectId}/reports`, {
      report_type: reportType,
      project_info: projectInfo,
    }),

  getStatus: (projectId: string, taskId: string) =>
    client.get<ReportStatus>(`/projects/${projectId}/reports/${taskId}/status`),

  getDownloadUrl: (projectId: string, taskId: string) =>
    `/api/v1/projects/${projectId}/reports/${taskId}/download`,

  getRevisions: (projectId: string, taskId: string) =>
    client.get<RevisionHistory>(`/projects/${projectId}/reports/${taskId}/revisions`),

  submitRevision: (projectId: string, taskId: string, data: unknown) =>
    client.post<{ revision_id: string; version: number; status: string }>(
      `/projects/${projectId}/reports/${taskId}/revisions`, data,
    ),
}
