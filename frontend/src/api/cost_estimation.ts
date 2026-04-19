import client from './client'

export interface CostEstimateItem {
  category: string
  item: string
  quantity: number
  unit: string
  unit_price: number
  subtotal: number
}

export interface CostEstimateSummary {
  category: string
  total_quantity: number
  total_amount: number
}

export interface CostEstimate {
  id: string
  project_id: string
  project_type: string
  version: number
  status: string
  design_params: Record<string, number>
  summary: CostEstimateSummary[]
  details: CostEstimateItem[]
  total_cost: number
  cost_per_km: number | null
  created_at: string
}

export interface CostEstimateListResponse {
  estimates: CostEstimate[]
  total: number
}

export interface CostEstimateCreateRequest {
  project_type: '堤防' | '河道整治'
  design_params: Record<string, number>
}

export const costEstimationApi = {
  create: (projectId: string, data: CostEstimateCreateRequest) =>
    client.post<CostEstimate>(`/projects/${projectId}/cost-estimates`, data),

  list: (projectId: string) =>
    client.get<CostEstimateListResponse>(`/projects/${projectId}/cost-estimates`),

  get: (projectId: string, estimateId: string) =>
    client.get<CostEstimate>(`/projects/${projectId}/cost-estimates/${estimateId}`),

  recalculate: (projectId: string, estimateId: string) =>
    client.post<CostEstimate>(`/projects/${projectId}/cost-estimates/${estimateId}/recalculate`),
}
