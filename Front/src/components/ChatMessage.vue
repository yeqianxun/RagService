<template>
  <div class="chat-message" :class="[message.role]">
    <div class="avatar">
      <el-avatar v-if="message.role === 'user'" size="small" shape="square" style="background-color: #4f46e5; color: white;">
        <el-icon><User /></el-icon>
      </el-avatar>
      <el-avatar v-else size="small" shape="square" style="background-color: #e0e7ff; color: #4f46e5;">
        <el-icon><ChatDotRound /></el-icon>
      </el-avatar>
    </div>
    <div class="content-wrapper">
      <div class="content">
        <MarkdownRenderer :content="message.content" />
      </div>
      <div class="timestamp">{{ formatTime(message.timestamp) }}</div>
    </div>
  </div>
</template>

<script setup>
import { ElIcon, ElAvatar } from 'element-plus'
import { User, ChatDotRound } from '@element-plus/icons-vue'
import MarkdownRenderer from './MarkdownRenderer.vue'

defineProps({
  message: {
    type: Object,
    required: true
  }
})

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.chat-message {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  max-width: 90%;
}

.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.avatar {
  margin-top: 4px;
}

.content-wrapper {
  display: flex;
  flex-direction: column;
}

.content {
  padding: 12px 16px;
  border-radius: 18px;
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.user .content {
  background-color: #4f46e5;
  color: white;
  border-radius: 18px 2px 18px 18px;
}

.assistant .content {
  background-color: white;
  color: #374151;
  border: 1px solid #e5e7eb;
  border-radius: 2px 18px 18px 18px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.timestamp {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 4px;
  text-align: right;
}

.user .timestamp {
  text-align: left;
}
</style>