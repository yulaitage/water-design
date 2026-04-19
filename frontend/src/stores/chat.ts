import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { chatApi, type ChatMessage } from '@/api/chat'

interface DisplayMessage extends ChatMessage {
  id: string
  streaming?: boolean
}

let nextId = 1

export const useChatStore = defineStore('chat', () => {
  const messages = ref<DisplayMessage[]>([])
  const loading = ref(false)

  const sortedMessages = computed(() => messages.value)

  function addUserMessage(content: string) {
    const msg: DisplayMessage = { id: String(nextId++), role: 'user', content, timestamp: new Date().toISOString() }
    messages.value = [...messages.value, msg]
    return msg
  }

  function addAssistantPlaceholder() {
    const msg: DisplayMessage = { id: String(nextId++), role: 'assistant', content: '', timestamp: new Date().toISOString(), streaming: true }
    messages.value = [...messages.value, msg]
    return msg
  }

  function appendToAssistant(id: string, chunk: string) {
    const idx = messages.value.findIndex((m) => m.id === id)
    if (idx !== -1) {
      messages.value = messages.value.map((m, i) =>
        i === idx ? { ...m, content: m.content + chunk } : m,
      )
    }
  }

  function finalizeAssistant(id: string) {
    const idx = messages.value.findIndex((m) => m.id === id)
    if (idx !== -1) {
      messages.value = messages.value.map((m, i) =>
        i === idx ? { ...m, streaming: false } : m,
      )
    }
  }

  function clearMessages() {
    messages.value = []
  }

  async function loadHistory(projectId: string) {
    try {
      const res = await chatApi.getConversations(projectId)
      const allMessages: DisplayMessage[] = []
      for (const conv of res.data) {
        for (const msg of conv.messages) {
          allMessages.push({ ...msg, id: String(nextId++) })
        }
      }
      messages.value = allMessages
    } catch {
      // silently ignore — no history yet
    }
  }

  return {
    messages: sortedMessages,
    loading,
    addUserMessage,
    addAssistantPlaceholder,
    appendToAssistant,
    finalizeAssistant,
    clearMessages,
    loadHistory,
  }
})
