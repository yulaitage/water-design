<template>
  <div :class="['message-bubble', message.role]">
    <div class="bubble-avatar">
      <a-avatar v-if="message.role === 'user'" :size="32">用</a-avatar>
      <a-avatar v-else :size="32" style="background-color: #0891b2">AI</a-avatar>
    </div>
    <div class="bubble-body">
      <div class="bubble-content" v-html="renderedContent"></div>
      <div v-if="message.streaming" class="typing-cursor">|</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '@/api/chat'

const props = defineProps<{ message: ChatMessage & { streaming?: boolean; id: string } }>()

function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

const renderedContent = computed(() => {
  const text = props.message.content || ''
  return escapeHtml(text).replace(/\n/g, '<br>')
})
</script>

<style scoped>
.message-bubble {
  display: flex;
  gap: 12px;
  padding: 12px 0;
}

.message-bubble.user {
  flex-direction: row-reverse;
}

.bubble-body {
  max-width: 75%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.user .bubble-body {
  background: #0891b2;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.assistant .bubble-body {
  background: #f5f5f5;
  color: #333;
  border-bottom-left-radius: 4px;
}

.typing-cursor {
  display: inline;
  animation: blink 0.8s step-end infinite;
  color: #999;
}

@keyframes blink {
  50% { opacity: 0; }
}
</style>
