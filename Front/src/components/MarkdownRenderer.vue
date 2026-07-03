<template>
  <div class="markdown-content" v-html="renderedContent"></div>
</template>

<script setup>
import { computed } from 'vue'
import DOMPurify from 'dompurify'

// 简单的Markdown解析器
const props = defineProps({
  content: {
    type: String,
    required: true
  }
})

const renderedContent = computed(() => {
  let content = props.content
  
  // 转义HTML标签
  content = DOMPurify.sanitize(content)
  
  // 解析粗体
  content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  
  // 解析斜体
  content = content.replace(/\*(.*?)\*/g, '<em>$1</em>')
  
  // 解析行内代码
  content = content.replace(/`(.*?)`/g, '<code class="inline-code">$1</code>')
  
  // 解析代码块
  content = content.replace(/```([\s\S]*?)```/g, '<pre class="code-block"><code>$1</code></pre>')
  
  // 解析标题
  content = content.replace(/^### (.*$)/gm, '<h3>$1</h3>')
  content = content.replace(/^## (.*$)/gm, '<h2>$1</h2>')
  content = content.replace(/^# (.*$)/gm, '<h1>$1</h1>')
  
  // 解析链接
  content = content.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
  
  // 解析列表
  content = content.replace(/^\- (.*$)/gm, '<li>$1</li>')
  content = content.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
  
  // 解析换行
  content = content.replace(/\n/g, '<br>')
  
  return content
})
</script>

<style scoped>
.markdown-content {
  font-size: 14px;
  line-height: 1.6;
}

.markdown-content :deep(h1) {
  font-size: 1.5em;
  margin: 0.67em 0;
  font-weight: bold;
}

.markdown-content :deep(h2) {
  font-size: 1.3em;
  margin: 0.83em 0;
  font-weight: bold;
}

.markdown-content :deep(h3) {
  font-size: 1.17em;
  margin: 1em 0;
  font-weight: bold;
}

.markdown-content :deep(strong) {
  font-weight: bold;
}

.markdown-content :deep(em) {
  font-style: italic;
}

.markdown-content :deep(code.inline-code) {
  background-color: rgba(149, 165, 166, 0.2);
  padding: 0.2em 0.4em;
  border-radius: 3px;
  font-family: 'Monaco', 'Consolas', monospace;
  font-size: 0.875em;
}

.markdown-content :deep(pre.code-block) {
  background-color: #f6f8fa;
  border-radius: 6px;
  padding: 16px;
  overflow-x: auto;
  margin: 16px 0;
}

.markdown-content :deep(pre.code-block code) {
  font-family: 'Monaco', 'Consolas', monospace;
  line-height: 1.45;
  tab-size: 4;
}

.markdown-content :deep(a) {
  color: #4f46e5;
  text-decoration: underline;
}

.markdown-content :deep(ul) {
  list-style-type: disc;
  padding-left: 20px;
  margin: 10px 0;
}
</style>