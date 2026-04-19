import client from './client'

export interface UnitPrice {
  id: string
  item_name: string
  unit: string
  price: number
  region: string | null
  year: number | null
  source: string
  created_at: string
}

export interface UnitPriceListResponse {
  items: UnitPrice[]
  total: number
}

export interface UnitPriceCreateRequest {
  item_name: string
  unit: string
  price: number
  region?: string
  year?: number
  source?: string
}

export const unitPriceApi = {
  list: (params?: { item_name?: string; region?: string; limit?: number }) =>
    client.get<UnitPriceListResponse>('/unit-prices', { params }),

  create: (data: UnitPriceCreateRequest) =>
    client.post<UnitPrice>('/unit-prices', data),

  importBatch: (items: UnitPriceCreateRequest[]) =>
    client.post<UnitPriceListResponse>('/unit-prices/import', { items }),
}
