<template>
  <div class="doubao-container">
    <el-container class="main-layout">
      <el-aside class="sidebar" :class="{ collapsed: isSidebarCollapsed }">
        <div class="logo-section">
          <div class="logo-icon">豆</div>
          <h1 v-show="!isSidebarCollapsed" class="logo-text">AI助手</h1>
          <el-button
            class="collapse-btn"
            :icon="isSidebarCollapsed ? ArrowRight : ArrowLeft"
            @click="toggleSidebar"
            text
            circle
          ></el-button>
        </div>

        <div class="new-chat-section">
          <el-button type="primary" class="new-chat-btn" @click="createNewChat">
            <el-icon><Plus /></el-icon>
            <span v-show="!isSidebarCollapsed">新建对话</span>
          </el-button>
        </div>

        <div class="menu-section">
          <div class="menu-item" :class="{ active: activeMenu === 'chat' }" @click="activeMenu = 'chat'">
            <el-icon><ChatLineRound /></el-icon>
            <span v-show="!isSidebarCollapsed">对话</span>
          </div>
          <div class="menu-item" :class="{ active: activeMenu === 'tasks' }" @click="activeMenu = 'tasks'">
            <el-icon><Document /></el-icon>
            <span v-show="!isSidebarCollapsed">任务</span>
          </div>
          <div class="menu-item" :class="{ active: activeMenu === 'files' }" @click="activeMenu = 'files'">
            <el-icon><FolderOpened /></el-icon>
            <span v-show="!isSidebarCollapsed">文件</span>
          </div>
          <div class="menu-item" :class="{ active: activeMenu === 'more' }" @click="activeMenu = 'more'">
            <el-icon><Grid /></el-icon>
            <span v-show="!isSidebarCollapsed">更多</span>
          </div>
        </div>

        <div class="history-section">
          <div class="history-title" v-show="!isSidebarCollapsed">
            <span>历史对话</span>
          </div>
          <div class="history-list">
            <div
              v-for="chat in allConversations"
              :key="chat.id"
              class="history-item"
              :class="{ active: chat.id === currentConversationId }"
              @click="selectChat(chat.id)"
            >
              <el-icon><Document /></el-icon>
              <span v-show="!isSidebarCollapsed">{{ chat.title }}</span>
            </div>
          </div>
        </div>

        <div class="user-section">
          <div class="user-avatar">
            <el-avatar :size="32" src="https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png"></el-avatar>
          </div>
          <div class="user-info" v-show="!isSidebarCollapsed">
            <span class="user-name">用户</span>
          </div>
        </div>
      </el-aside>

      <el-container>
        <el-header class="header">
          <div class="header-content">
            <div class="header-left">
              <h2>{{ currentChatTitle }}</h2>
            </div>
            <div class="header-right">
              <el-button text :icon="Share">分享</el-button>
              <el-button text :icon="Setting">设置</el-button>
              <el-button type="primary" round size="small" class="upgrade-btn">
                <el-icon><Star /></el-icon>
                升级到高级版
              </el-button>
            </div>
          </div>
        </el-header>

        <el-main class="chat-area">
          <div v-if="isWelcomeScreen" class="welcome-screen">
            <div class="welcome-content">
              <h1 class="welcome-title">有什么我能帮你的吗？</h1>

              <div class="quick-questions">
                <div class="question-row">
                  <div class="question-card" @click="sendQuickQuestion('如何快速上手Vue3的新特性')">
                    <div class="question-text">如何快速上手Vue3的新特性</div>
                  </div>
                  <div class="question-card" @click="sendQuickQuestion('帮我写一个Python爬虫脚本')">
                    <div class="question-text">帮我写一个Python爬虫脚本</div>
                  </div>
                  <div class="question-card" @click="sendQuickQuestion('如何提升前端代码质量')">
                    <div class="question-text">如何提升前端代码质量</div>
                  </div>
                </div>
                <div class="question-row">
                  <div class="question-card" @click="sendQuickQuestion('给我推荐几款好用的AI工具')">
                    <div class="question-text">给我推荐几款好用的AI工具</div>
                  </div>
                  <div class="question-card" @click="sendQuickQuestion('如何做好一个项目的需求分析')">
                    <div class="question-text">如何做好一个项目的需求分析</div>
                  </div>
                  <div class="question-card" @click="sendQuickQuestion('帮我解释一下什么是RAG技术')">
                    <div class="question-text">帮我解释一下什么是RAG技术</div>
                  </div>
                </div>
              </div>

              <div class="capabilities">
                <div class="capability-title">我的能力</div>
                <div class="capability-list">
                  <div class="capability-item">
                    <el-icon class="capability-icon"><Document /></el-icon>
                    <span>文档总结</span>
                  </div>
                  <div class="capability-item">
                    <el-icon class="capability-icon"><Picture /></el-icon>
                    <span>图片生成</span>
                  </div>
                  <div class="capability-item">
                    <el-icon class="capability-icon"><Edit /></el-icon>
                    <span>写作助手</span>
                  </div>
                  <div class="capability-item">
                    <el-icon class="capability-icon"><Microphone /></el-icon>
                    <span>语音生成</span>
                  </div>
                  <div class="capability-item">
                    <el-icon class="capability-icon"><ChatLineRound /></el-icon>
                    <span>翻译</span>
                  </div>
                  <div class="capability-item">
                    <el-icon class="capability-icon"><VideoCamera /></el-icon>
                    <span>视频生成</span>
                  </div>
                  <div class="capability-item">
                    <el-icon class="capability-icon"><Reading /></el-icon>
                    <span>深度研究</span>
                  </div>
                  <div class="capability-item">
                    <el-icon class="capability-icon"><Grid /></el-icon>
                    <span>更多</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-else class="messages-container">
            <ChatMessage
              v-for="(msg, index) in currentMessages"
              :key="msg.id || index"
              :message="msg"
            />
          </div>

          <div class="input-container">
            <ChatInput
              v-model="inputMessage"
              placeholder="发送消息或按空格键唤起..."
              @send="handleSendMessage"
            />
          </div>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Plus,
  Document,
  ChatLineRound,
  ArrowLeft,
  ArrowRight,
  Share,
  Setting,
  Star,
  FolderOpened,
  Grid,
  Picture,
  Edit,
  Microphone,
  VideoCamera,
  Reading
} from '@element-plus/icons-vue'
import { useChatStore } from '@/stores/chat'
import { storeToRefs } from 'pinia'
import ChatMessage from '@/components/ChatMessage.vue'
import ChatInput from '@/components/ChatInput.vue'

const isSidebarCollapsed = ref(false)
const activeMenu = ref('chat')
const chatStore = useChatStore()
const { currentMessages, allConversations, currentConversationId } = storeToRefs(chatStore)

const inputMessage = ref('')

const isWelcomeScreen = computed(() => {
  if (!currentConversationId.value) return true
  return currentMessages.value.length === 0
})

const currentChatTitle = computed(() => {
  if (!currentConversationId.value) return '新对话'
  const chat = allConversations.value.find(c => c.id === currentConversationId.value)
  return chat ? chat.title : '新对话'
})

const createNewChat = () => {
  chatStore.createConversation()
  ElMessage.success('已创建新对话')
}

const selectChat = (id) => {
  chatStore.switchConversation(id)
}

const toggleSidebar = () => {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}

const sendQuickQuestion = (question) => {
  if (!currentConversationId.value) {
    chatStore.createConversation(question.substring(0, 20))
  }
  chatStore.sendMessage(question)
}

const handleSendMessage = (message) => {
  if (!message.trim()) {
    ElMessage.warning('请输入消息内容')
    return
  }

  if (!currentConversationId.value) {
    chatStore.createConversation(message.substring(0, 20))
  }

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
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
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
    width: 240px !important;

    &:not(.collapsed) {
      width: 240px !important;
    }

    &.collapsed {
      width: 72px !important;
    }

    .logo-section {
      display: flex;
      align-items: center;
      padding: 16px;
      border-bottom: 1px solid #e5e7eb;
      height: 64px;
      justify-content: space-between;

      .logo-icon {
        width: 36px;
        height: 36px;
        border-radius: 8px;
        background: linear-gradient(135deg, #626aef, #5c6aed);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 16px;
        flex-shrink: 0;
      }

      .logo-text {
        font-size: 18px;
        font-weight: 700;
        color: #1f2329;
        letter-spacing: -0.5px;
        margin: 0 12px;
        flex: 1;
      }

      .collapse-btn {
        width: 28px;
        height: 28px;
        min-height: 28px;
        padding: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        color: #6b7280;

        &:hover {
          background: #e5e7eb;
          color: #1f2329;
        }
      }
    }

    .new-chat-section {
      padding: 12px;

      .new-chat-btn {
        width: 100%;
        height: 40px;
        border-radius: 8px;
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

    .menu-section {
      padding: 8px;

      .menu-item {
        display: flex;
        align-items: center;
        padding: 10px 12px;
        border-radius: 8px;
        cursor: pointer;
        margin-bottom: 2px;
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
          margin-left: 10px;
          font-size: 14px;
        }
      }
    }

    .history-section {
      flex: 1;
      overflow-y: auto;
      padding: 0 8px 12px 8px;

      .history-title {
        padding: 12px 8px 6px 8px;
        font-size: 12px;
        color: #6b7280;
        font-weight: 500;
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

    .user-section {
      padding: 12px;
      border-top: 1px solid #e5e7eb;
      display: flex;
      align-items: center;

      .user-avatar {
        flex-shrink: 0;
      }

      .user-info {
        margin-left: 10px;
        .user-name {
          font-size: 14px;
          font-weight: 500;
          color: #374151;
        }
      }
    }
  }

  .header {
    border-bottom: 1px solid #e5e7eb;
    padding: 0;
    background: #ffffff;
    height: 56px !important;

    .header-content {
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 24px;

      h2 {
        font-size: 16px;
        font-weight: 600;
        color: #1f2329;
        margin: 0;
      }
    }

    .header-right {
      display: flex;
      align-items: center;
      gap: 4px;

      .upgrade-btn {
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        border: none;
        font-weight: 500;
        font-size: 13px;
        padding: 6px 16px;
      }
    }
  }

  .chat-area {
    display: flex;
    flex-direction: column;
    padding: 0;
    background-color: #fcfcfc;
    position: relative;

    .welcome-screen {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow-y: auto;
      padding: 40px 24px;

      .welcome-content {
        width: 100%;
        max-width: 900px;
        display: flex;
        flex-direction: column;
        align-items: center;

        .welcome-title {
          font-size: 32px;
          font-weight: 700;
          color: #1f2329;
          margin-bottom: 32px;
        }

        .quick-questions {
          width: 100%;
          margin-bottom: 48px;

          .question-row {
            display: flex;
            gap: 16px;
            margin-bottom: 16px;
          }

          .question-card {
            flex: 1;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 20px;
            cursor: pointer;
            transition: all 0.2s ease;

            &:hover {
              border-color: #c7d2fe;
              box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
              transform: translateY(-2px);
            }

            .question-text {
              font-size: 14px;
              color: #374151;
              line-height: 1.5;
            }
          }
        }

        .capabilities {
          width: 100%;

          .capability-title {
            font-size: 14px;
            font-weight: 600;
            color: #6b7280;
            margin-bottom: 16px;
            text-align: center;
          }

          .capability-list {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 24px;

            .capability-item {
              display: flex;
              flex-direction: column;
              align-items: center;
              gap: 8px;
              cursor: pointer;
              transition: all 0.2s ease;

              &:hover {
                .capability-icon {
                  color: #4f46e5;
                }
                span {
                  color: #4f46e5;
                }
              }

              .capability-icon {
                font-size: 28px;
                color: #6b7280;
                width: 52px;
                height: 52px;
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
              }

              span {
                font-size: 12px;
                color: #6b7280;
              }
            }
          }
        }
      }
    }

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
    }

    .input-container {
      padding: 20px 24px;
      background: #fcfcfc;
      display: flex;
      justify-content: center;
      max-width: 800px;
      margin: 0 auto;
      width: 100%;
    }
  }
}

@media (max-width: 768px) {
  .sidebar {
    width: 72px !important;

    .logo-text, .menu-item span, .history-title, .history-item span, .user-info {
      display: none;
    }
  }

  .welcome-title {
    font-size: 24px !important;
  }

  .question-row {
    flex-direction: column;
  }
}
</style>
