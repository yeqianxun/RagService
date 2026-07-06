<template>
  <div class="flex gap-14 w-full items-center bg-[#fcfcfc] pt-3">
    <el-input
      v-model="inputValue"
      :rows="inputRows"
      type="textarea"
      :placeholder="placeholder"
      class="flex-1"
      @keydown="handleKeyDown"
      ref="textareaRef"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElInput } from 'element-plus'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: '请输入消息...'
  }
})

const emit = defineEmits(['update:modelValue', 'send'])

const textareaRef = ref(null)
const inputValue = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const inputRows = computed(() => {
  const lines = props.modelValue ? props.modelValue.split('\n').length : 1
  return Math.min(Math.max(lines, 1), 5) // 最少1行，最多5行
})

const handleKeyDown = (event) => {
  if (event.key === 'Enter') {
    if (!event.shiftKey) {
      event.preventDefault()
      handleSend()
    }
  }
}

const handleSend = () => {
  if (inputValue.value.trim()) {
    emit('send', inputValue.value)
    inputValue.value = '' // 清空输入框
  }
}
</script>

<style scoped>
:deep(textarea) {
  border-radius: 18px !important;
  border: 1px solid #e5e7eb !important;
  padding: 14px 20px !important;
  resize: none;
  background: #fcfcfc; /* 输入框背景色与聊天区域一致 */

  &:focus {
    border-color: #c7d2fe !important;
    box-shadow: 0 0 0 3px rgba(103, 117, 233, 0.1) !important;
  }
}
</style>