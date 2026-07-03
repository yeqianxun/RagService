import { defineStore } from 'pinia'

export const useChatStore = defineStore('chat', {
  state: () => ({
    conversations: [],
    currentConversationId: null,
    messages: {}
  }),

  getters: {
    currentMessages: (state) => {
      if (!state.currentConversationId) return []
      return state.messages[state.currentConversationId] || []
    },
    
    allConversations: (state) => {
      return state.conversations
    }
  },

  actions: {
    // 创建新对话
    createConversation(title) {
      const id = Date.now().toString()
      const newConversation = {
        id,
        title: title || `新对话 ${this.conversations.length + 1}`,
        createdAt: new Date().toISOString()
      }
      
      this.conversations.unshift(newConversation)
      this.currentConversationId = id
      this.messages[id] = []
      
      return id
    },

    // 切换对话
    switchConversation(conversationId) {
      this.currentConversationId = conversationId
    },

    // 添加消息
    addMessage(conversationId, message) {
      if (!this.messages[conversationId]) {
        this.messages[conversationId] = []
      }
      
      // 如果消息没有ID，则生成一个
      if (!message.id) {
        message.id = Date.now()
      }
      
      // 如果消息没有时间戳，则添加当前时间
      if (!message.timestamp) {
        message.timestamp = new Date().toISOString()
      }
      
      this.messages[conversationId].push(message)
    },

    // 发送消息
    async sendMessage(content) {
      if (!content.trim()) return
      
      const userMessage = {
        id: Date.now(),
        role: 'user',
        content: content,
        timestamp: new Date().toISOString()
      }
      
      this.addMessage(this.currentConversationId, userMessage)
      
      // 模拟AI回复
      setTimeout(() => {
        const aiMessage = {
          id: Date.now() + 1,
          role: 'assistant',
          content: `我收到了你的消息："${content}"。这是一个模拟的回复，实际应用中这里会连接AI服务。`,
          timestamp: new Date().toISOString()
        }
        this.addMessage(this.currentConversationId, aiMessage)
      }, 1000)
    }
  }
})