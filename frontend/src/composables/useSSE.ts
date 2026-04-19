import { ref } from 'vue'
import { createSSEStream } from '@/api/chat'

export function useSSE(projectId: () => string) {
  const streaming = ref(false)
  const abortFn = ref<(() => void) | null>(null)

  function send(message: string, onChunk: (text: string) => void) {
    return new Promise<void>((resolve, reject) => {
      streaming.value = true
      abortFn.value = createSSEStream(
        projectId(),
        message,
        (chunk) => onChunk(chunk),
        () => {
          streaming.value = false
          abortFn.value = null
          resolve()
        },
        (error) => {
          streaming.value = false
          abortFn.value = null
          reject(new Error(error))
        },
      )
    })
  }

  function abort() {
    abortFn.value?.()
    streaming.value = false
  }

  return { streaming, send, abort }
}
