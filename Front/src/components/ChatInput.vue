<template>
  <div class="chat-input-wrapper">
    <div class="chat-input-container">
      <div class="input-left">
        <el-button text :icon="Plus" class="action-btn"></el-button>
      </div>
      <el-input
        v-model="inputValue"
        :rows="inputRows"
        type="textarea"
        :placeholder="placeholder"
        class="message-input"
        @keydown="handleKeyDown"
        ref="textareaRef"
      />
      <div class="input-right">
        <el-button text :icon="Picture" class="action-btn"></el-button>
        <el-button text :icon="Files" class="action-btn"></el-button>

        <el-divider direction="vertical" />

        <el-button
          type="primary"
          :icon="Promotion"
          class="send-btn"
          round
          :disabled="!inputValue.trim()"
          @click="handleSend"
        ></el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { ElInput, ElButton, ElDivider } from 'element-plus'
import { Plus, Picture, Files, Promotion } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '请输入消息...' }
})

const emit = defineEmits(['update:modelValue', 'send'])
const textareaRef = ref(null)

const inputValue = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const inputRows = computed(() => {
  const lines = props.modelValue ? props.modelValue.split('\n').length : 1
  return Math.min(Math.max(lines, 1), 6)
})

const handleKeyDown = (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
}

const handleSend = () => {
  if (inputValue.value.trim()) {
    emit('send', inputValue.value)
    nextTick(() => inputValue.value = '')
  }
}
</script>

<style scoped>
.chat-input-wrapper {
  width: 100%;
}
.chat-input-container {
  width: 100%;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  display: flex;
  align-items: flex-end;
  padding: 12px 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  transition: border-color 0.2s ease;
}
.chat-input-container:focus-within {
  border-color: #c7d2fe;
  box-shadow: 0 0 0 3px rgba(103, 117, 233, 0.1);
}
.input-left, .input-right {
  display: flex;
  align-items: center;
  gap: 2px;
}
.message-input {
  flex: 1;
  margin: 0 12px;
}
.message-input :deep(.el-textarea__inner) {
  border: none;
  box-shadow: none;
  padding: 0;
  font-size: 15px;
  line-height: 1.5;
  resize: none;
  background: transparent;
}
.action-btn {
  padding: 8px;
  font-size: 20px;
  color: #6b7280;
  border-radius: 8px;
}
.action-btn:hover {
  background-color: #f3f4f6;
  color: #374151;
}
.send-btn {
  padding: 8px 16px;
  font-size: 14px;
  border-radius: 100px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border: none;
  height: 36px;
}
.send-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #5a5dc7, #7a4fd8);
  opacity: 0.9;
}
.send-btn:disabled {
  background: #9ca3af;
}
</style>
