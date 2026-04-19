import client from './client'

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp?: string
  tool_calls?: unknown[]
}

export interface ChatResponse {
  conversation_id: string
  message: string
  intent: string
  tool_calls?: unknown[]
  context?: Record<string, unknown>
}

export interface ConversationHistory {
  id: string
  project_id: string
  messages: ChatMessage[]
  context: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export const chatApi = {
  send: (projectId: string, message: string) =>
    client.post<ChatResponse>('/chat', { project_id: projectId, message }),

  getConversations: (projectId: string, limit = 50, offset = 0) =>
    client.get<ConversationHistory[]>(`/chat/projects/${projectId}/conversations`, {
      params: { limit, offset },
    }),
}

export function createSSEStream(
  projectId: string,
  message: string,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (error: string) => void,
): () => void {
  const url = `/api/v1/chat?stream=true`
  const controller = new AbortController()

  fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': import.meta.env.VITE_API_KEY || '',
    },
    body: JSON.stringify({ project_id: projectId, message }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.body) {
        onError('No response body')
        return
      }
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6)
          if (data === '[DONE]') {
            onDone()
            return
          }
          try {
            const parsed = JSON.parse(data) as { error?: string; content?: string }
            if (parsed.error) {
              onError(parsed.error)
            } else if (parsed.content) {
              onChunk(parsed.content)
            }
          } catch {
            // ignore parse errors
          }
        }
      }
      onDone()
    })
    .catch((e: unknown) => {
      if (e instanceof Error && e.name !== 'AbortError') {
        onError(e.message)
      }
    })

  return () => controller.abort()
}
