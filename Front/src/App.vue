<template>
  <div class="doubao-container">
    <el-container class="main-layout">
      <!-- 侧边栏 -->
      <el-aside class="sidebar" :class="{ collapsed: isSidebarCollapsed }">
        <div class="logo-section">
          <div class="logo-icon">豆</div>
          <h1 v-show="!isSidebarCollapsed" class="logo-text">豆包</h1>
          <el-button
            class="collapse-btn"
            :icon="isSidebarCollapsed ? ArrowRight : ArrowLeft"
            @click="toggleSidebar"
            text
            circle
          />
        </div>

        <div class="new-chat-section">
          <el-button type="primary" class="new-chat-btn" @click="createNewChat">
            <el-icon><Plus /></el-icon>
            <span v-show="!isSidebarCollapsed">新建对话</span>
          </el-button>
        </div>

        <div class="history-section">
          <div class="history-title" v-show="!isSidebarCollapsed">
            <span>历史记录</span>
          </div>
          <div class="history-list">
            <div
              v-for="chat in allConversations"
              :key="chat.id"
              class="history-item"
              :class="{ active: chat.id === currentChatId }"
              @click="selectChat(chat.id)"
            >
              <el-icon><Document /></el-icon>
              <span v-show="!isSidebarCollapsed">{{ chat.title }}</span>
            </div>
          </div>
        </div>
      </el-aside>

      <!-- 折叠按钮，当侧边栏隐藏时显示 -->
      <div v-if="isSidebarCollapsed" class="absolute left-0 top-1/2 transform -translate-y-1/2 z-10">
        <el-button
          class="w-8 h-8 min-h-8 p-0 flex items-center justify-center rounded-r-lg text-gray-500 bg-white shadow-md hover:bg-indigo-100 hover:text-indigo-600 border border-gray-200"
          :icon="ArrowRight"
          @click="toggleSidebar"
          text
          circle
        />
      </div>

      <!-- 主内容区 -->
      <el-container>
        <el-header class="header">
          <div class="header-content">
            <h2>{{ currentChatTitle }}</h2>
          </div>
        </el-header>

        <el-main class="chat-area">
          <div class="messages-container">
            <ChatMessage
              v-for="(msg, index) in currentMessages"
              :key="msg.id || index"
              :message="msg"
            />
          </div>

          <div class="input-container">
            <ChatInput
              v-model="inputMessage"
              placeholder="请输入消息..."
              @send="handleSendMessage"
            />
          </div>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Plus,
  Document,
  User,
  ChatLineRound,
  ArrowLeft,
  ArrowRight
} from '@element-plus/icons-vue'
import { useChatStore } from '@/stores/chat'
import { storeToRefs } from 'pinia'
import ChatMessage from '@/components/ChatMessage.vue'
import ChatInput from '@/components/ChatInput.vue'

const isSidebarCollapsed = ref(false)
let currentChatId = ref('')
let currentChatTitle=ref('')
const chatStore = useChatStore()
const { currentMessages, allConversations } = storeToRefs(chatStore)

// 初始化一些示例对话
if (allConversations.value.length === 0) {
  chatStore.createConversation('关于Vue3的问题')
  chatStore.createConversation('JavaScript学习')
  chatStore.createConversation('前端开发技巧')

  // 添加一些示例消息
  chatStore.addMessage(allConversations.value[0].id, {
    role: 'assistant',
    content: '你好！我是豆包，有什么可以帮助你的吗？'
  })
  chatStore.addMessage(allConversations.value[0].id, {
    role: 'user',
    content: '你好，我想了解Vue3的一些特性'
  })
  chatStore.addMessage(allConversations.value[0].id, {
    role: 'assistant',
    content: '好的，Vue3是Vue.js的最新版本，引入了许多新特性，如Composition API、更好的TypeScript支持、性能优化等。你可以问我具体想了解哪方面。'
  })
}

const inputMessage = ref('')

// 创建新聊天
const createNewChat = () => {
  chatStore.createConversation()
  ElMessage.success('已创建新对话')
}

// 选择聊天
const selectChat = (id) => {
  chatStore.switchConversation(id)
}

// 切换侧边栏展开/折叠
const toggleSidebar = () => {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}

// 处理发送消息
const handleSendMessage = (message) => {
  if (!message.trim()) {
    ElMessage.warning('请输入消息内容')
    return
  }

  // 发送消息
  chatStore.sendMessage(message)
}
</script>

<style lang="scss">
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.doubao-container {
  height: 100vh;
  width: 100%;
  overflow: hidden;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
}

.main-layout {
  height: 100vh;

  .sidebar {
    background-color: #f9f9f9;
    border-right: 1px solid #e5e7eb;
    display: flex;
    flex-direction: column;
    transition: width 0.3s ease;
    overflow: hidden;

    &:not(.collapsed) {
      width: 240px !important;
    }

    &.collapsed {
      width: 0px !important;
    }

    .logo-section {
      display: flex;
      align-items: center;
      padding: 16px;
      border-bottom: 1px solid #e5e7eb;
      height: 48px;
      justify-content: space-between;

      .logo-icon {
        width: 32px;
        height: 32px;
        border-radius: 8px;
        background: linear-gradient(135deg, #626aef, #5c6aed);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 14px;
        flex-shrink: 0;
      }

      .logo-text {
        font-size: 18px;
        font-weight: 700;
        color: #1f2329;
        letter-spacing: -0.5px;
        margin: 0 8px;
        flex: 1;
      }

      .collapse-btn {
        width: 32px;
        height: 32px;
        min-height: 32px;
        padding: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        color: #6b7280;
        background: #e0e7ff;

        &:hover {
          background: #c7d2fe;
          color: #4f46e5;
        }
      }
    }

    .new-chat-section {
      padding: 12px;

      .new-chat-btn {
        width: 100%;
        height: 38px;
        border-radius: 10px;
        font-weight: 500;
        font-size: 14px;
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        border: none;

        &:hover {
          opacity: 0.9;
          background: linear-gradient(135deg, #5a5dc7, #7a4fd8);
        }
      }
    }

    .history-section {
      flex: 1;
      overflow-y: auto;
      padding: 0 8px 12px 8px;

      .history-title {
        padding: 12px 8px 6px 8px;
        font-size: 11px;
        color: #6b7280;
        font-weight: 500;
        text-transform: uppercase;
      }

      .history-list {
        .history-item {
          display: flex;
          align-items: center;
          padding: 8px 10px;
          border-radius: 8px;
          cursor: pointer;
          margin-bottom: 3px;
          color: #374151;
          transition: all 0.2s ease;

          &:hover {
            background-color: #e5e7eb;
          }

          &.active {
            background-color: #e0e7ff;
            color: #4f46e5;
          }

          span {
            margin-left: 8px;
            font-size: 13px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            flex: 1;
          }
        }
      }
    }
  }

  .header {
    border-bottom: 1px solid #e5e7eb;
    padding: 0;
    background: #f9fafb;
    height: 48px !important;

    .header-content {
      height: 100%;
      display: flex;
      align-items: center;
      padding: 0 16px;

      h2 {
        font-size: 15px;
        font-weight: 600;
        color: #1f2329;
        margin: 0;
      }
    }
  }

  .chat-area {
    display: flex;
    flex-direction: column;
    padding: 0;
    background-color: #fcfcfc;

    .messages-container {
      flex: 1;
      overflow-y: auto;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 24px;
      max-width: 800px;
      margin: 0 auto;
      width: 100%;

      .message {
        display: flex;
        gap: 16px;
        max-width: 100%;

        &.user-message {
          align-self: flex-end;
          flex-direction: row-reverse;

          .content {
            .text {
              background-color: #4f46e5;
              color: white;
              border-radius: 18px 2px 18px 18px;
            }
          }
        }

        &.bot-message {
          .content {
            .text {
              background-color: white;
              padding: 12px 16px;
              border-radius: 2px 18px 18px 18px;
              box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
              border: 1px solid #f3f4f6;
            }
          }
        }

        .avatar {
          display: flex;
          align-items: flex-start;
          margin-top: 4px;
        }

        .content {
          flex: 1;

          .text {
            padding: 12px 16px;
            font-size: 14px;
            line-height: 1.5;
            white-space: pre-wrap;
            word-break: break-word;
          }
        }
      }
    }

    .input-container {
      padding: 24px;
      background: #fcfcfc;
      display: flex;
      justify-content: center;
      max-width: 800px;
      margin: 0 auto;
      width: 100%;

      .chat-input-container {
        width: 100%;
        display: flex;
        gap: 12px;

        .message-input {
          flex: 1;
        }

        .send-btn {
          border-radius: 12px;
          padding: 10px 20px;
          font-weight: 500;
          height: 44px;
          background: linear-gradient(135deg, #6366f1, #8b5cf6);
          border: none;

          &:hover:not(:disabled) {
            opacity: 0.9;
            background: linear-gradient(135deg, #5a5dc7, #7a4fd8);
          }

          &:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }
        }
      }
    }
  }
}

// 响应式设计
@media (max-width: 768px) {
  .sidebar {
    width: 80px !important;

    .logo-text, .history-title, .history-item span {
      display: none;
    }

    .logo-section {
      justify-content: center;
      padding: 20px 10px;
    }

    .logo-icon {
      margin-right: 0 !important;
    }

    .new-chat-btn span {
      display: none;
    }

    .new-chat-btn .el-icon {
      margin-right: 0;
    }
  }

  .main-layout .chat-area .messages-container,
  .main-layout .chat-area .input-container {
    padding: 16px;
  }
}
</style>