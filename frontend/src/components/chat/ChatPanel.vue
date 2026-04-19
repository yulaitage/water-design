<template>
  <div class="chat-panel">
    <div class="chat-messages" ref="messagesRef">
      <template v-if="chatStore.messages.length === 0">
        <a-empty description="开始与AI助手对话" style="margin-top: 80px" />
      </template>
      <MessageBubble
        v-for="msg in chatStore.messages"
        :key="msg.id"
        :message="msg"
      />
    </div>

    <div class="chat-input-bar">
      <a-textarea
        v-model:value="inputText"
        :auto-size="{ minRows: 1, maxRows: 4 }"
        placeholder="输入消息..."
        @pressEnter="handleSend"
        :disabled="sse.streaming.value"
      />
      <a-button
        type="primary"
        :loading="sse.streaming.value"
        :disabled="!inputText.trim()"
        @click="handleSend"
        style="margin-left: 8px"
      >
        发送
      </a-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch, onUnmounted } from 'vue'
import { message } from 'ant-design-vue'
import MessageBubble from './MessageBubble.vue'
import { useChatStore } from '@/stores/chat'
import { useSSE } from '@/composables/useSSE'

const props = defineProps<{ projectId: string }>()

const chatStore = useChatStore()
const sse = useSSE(() => props.projectId)

const inputText = ref('')
const messagesRef = ref<HTMLElement>()

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

watch(() => chatStore.messages.length, scrollToBottom)

async function handleSend(e?: KeyboardEvent) {
  if (e && !e.shiftKey) {
    e.preventDefault()
  }
  if (!inputText.value.trim() || sse.streaming.value) return

  const text = inputText.value.trim()
  inputText.value = ''

  chatStore.addUserMessage(text)
  const assistantMsg = chatStore.addAssistantPlaceholder()
  scrollToBottom()

  try {
    await sse.send(text, (chunk) => {
      chatStore.appendToAssistant(assistantMsg.id, chunk)
      scrollToBottom()
    })
    chatStore.finalizeAssistant(assistantMsg.id)
  } catch (err) {
    chatStore.finalizeAssistant(assistantMsg.id)
    message.error('AI响应失败')
  }
}

chatStore.loadHistory(props.projectId)

onUnmounted(() => {
  if (sse.streaming.value) {
    sse.abort()
  }
})
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 140px);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 0;
}

.chat-input-bar {
  display: flex;
  align-items: flex-end;
  padding: 12px 0;
  border-top: 1px solid #f0f0f0;
}
</style>
