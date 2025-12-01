"use client"

import React, { useState, useRef, useEffect } from "react"
import { Send, Bot, Loader2, X, Sparkles, Trash2, ChevronDown, ChevronRight, Wrench } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"
import clsx from "clsx"

interface Message {
  role: "user" | "assistant"
  content: string
  toolCalls?: ToolCall[]
}

interface ToolCall {
  name: string
  args: string
  status: "running" | "done"
}

interface ChatInterfaceProps {
  onClose: () => void
}

const SUGGESTED_QUERIES = [
  "Show me all poor condition bridges in Ontario",
  "Optimize $50M budget for infrastructure repairs",
  "What are the highest risk roads in the GTA?",
  "Forecast Highway 401 degradation over 5 years",
  "Compare funding approaches for bridge repairs",
]

// Simple markdown-like renderer for the assistant's responses
function FormattedContent({ content }: { content: string }) {
  // Parse content for tables, lists, headers, bold, etc.
  const lines = content.split('\n')
  const elements: React.ReactElement[] = []
  let tableRows: string[][] = []
  let inTable = false
  let listItems: string[] = []
  let inList = false

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`list-${elements.length}`} className="list-disc list-inside space-y-1 my-2">
          {listItems.map((item, i) => (
            <li key={i} className="text-slate-700">{formatInlineText(item)}</li>
          ))}
        </ul>
      )
      listItems = []
    }
    inList = false
  }

  const flushTable = () => {
    if (tableRows.length > 0) {
      const headers = tableRows[0]
      const dataRows = tableRows.slice(2) // Skip header and separator
      elements.push(
        <div key={`table-${elements.length}`} className="my-3 overflow-x-auto">
          <table className="min-w-full text-sm border border-slate-200 rounded-lg overflow-hidden">
            <thead className="bg-slate-100">
              <tr>
                {headers.map((h, i) => (
                  <th key={i} className="px-3 py-2 text-left font-semibold text-slate-700 border-b border-slate-200">
                    {h.trim()}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dataRows.map((row, i) => (
                <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                  {row.map((cell, j) => (
                    <td key={j} className="px-3 py-2 text-slate-600 border-b border-slate-100">
                      {formatInlineText(cell.trim())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
      tableRows = []
    }
    inTable = false
  }

  const formatInlineText = (text: string) => {
    // Bold: **text** or __text__
    const parts = text.split(/(\*\*[^*]+\*\*|__[^_]+__)/g)
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="font-semibold text-slate-900">{part.slice(2, -2)}</strong>
      }
      if (part.startsWith('__') && part.endsWith('__')) {
        return <strong key={i} className="font-semibold text-slate-900">{part.slice(2, -2)}</strong>
      }
      // Code: `text`
      const codeParts = part.split(/(`[^`]+`)/g)
      return codeParts.map((cp, j) => {
        if (cp.startsWith('`') && cp.endsWith('`')) {
          return <code key={`${i}-${j}`} className="bg-slate-100 px-1.5 py-0.5 rounded text-sm font-mono text-blue-600">{cp.slice(1, -1)}</code>
        }
        return cp
      })
    })
  }

  lines.forEach((line, idx) => {
    const trimmed = line.trim()

    // Check for table row (contains |)
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      flushList()
      inTable = true
      const cells = trimmed.slice(1, -1).split('|')
      // Skip separator rows (---|---|---)
      if (!trimmed.match(/^\|[\s-:|]+\|$/)) {
        tableRows.push(cells)
      } else {
        tableRows.push([]) // Placeholder for separator
      }
      return
    } else if (inTable) {
      flushTable()
    }

    // Headers
    if (trimmed.startsWith('### ')) {
      flushList()
      elements.push(
        <h3 key={idx} className="text-base font-bold text-slate-900 mt-4 mb-2">
          {formatInlineText(trimmed.slice(4))}
        </h3>
      )
      return
    }
    if (trimmed.startsWith('## ')) {
      flushList()
      elements.push(
        <h2 key={idx} className="text-lg font-bold text-slate-900 mt-4 mb-2">
          {formatInlineText(trimmed.slice(3))}
        </h2>
      )
      return
    }
    if (trimmed.startsWith('# ')) {
      flushList()
      elements.push(
        <h1 key={idx} className="text-xl font-bold text-slate-900 mt-4 mb-2">
          {formatInlineText(trimmed.slice(2))}
        </h1>
      )
      return
    }

    // List items
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.match(/^\d+\. /)) {
      inList = true
      const itemText = trimmed.replace(/^[-*]\s+/, '').replace(/^\d+\.\s+/, '')
      listItems.push(itemText)
      return
    } else if (inList && trimmed === '') {
      flushList()
      return
    } else if (inList) {
      flushList()
    }

    // Empty line
    if (trimmed === '') {
      elements.push(<div key={idx} className="h-2" />)
      return
    }

    // Regular paragraph
    elements.push(
      <p key={idx} className="text-slate-700 leading-relaxed">
        {formatInlineText(line)}
      </p>
    )
  })

  // Flush remaining
  flushList()
  flushTable()

  return <div className="space-y-1">{elements}</div>
}

// Collapsible Tool Call component
function ToolCallDisplay({ tool, index }: { tool: ToolCall; index: number }) {
  const [expanded, setExpanded] = useState(false)
  
  return (
    <div className="bg-slate-50 border border-slate-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-slate-100 transition-colors"
      >
        <Wrench size={14} className={clsx(
          tool.status === "running" ? "text-amber-500 animate-pulse" : "text-green-500"
        )} />
        <span className="text-xs font-medium text-slate-700 flex-1">
          {tool.name}
        </span>
        <span className={clsx(
          "text-xs px-2 py-0.5 rounded-full",
          tool.status === "running" 
            ? "bg-amber-100 text-amber-700" 
            : "bg-green-100 text-green-700"
        )}>
          {tool.status === "running" ? "Running..." : "Done"}
        </span>
        {expanded ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronRight size={14} className="text-slate-400" />}
      </button>
      {expanded && tool.args && (
        <div className="px-3 py-2 border-t border-slate-200 bg-slate-100">
          <pre className="text-xs font-mono text-slate-600 whitespace-pre-wrap overflow-x-auto">
            {tool.args}
          </pre>
        </div>
      )}
    </div>
  )
}

export function ChatInterface({ onClose }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage = input
    setInput("")
    setMessages((prev) => [...prev, { role: "user", content: userMessage }])
    setIsLoading(true)

    try {
      const response = await fetch("http://0.0.0.0:8080/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage }),
      })

      if (!response.ok) throw new Error("Failed to send message")
      if (!response.body) return

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let assistantMessage = ""

      setMessages((prev) => [...prev, { role: "assistant", content: "" }])

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        const lines = chunk.split("\n\n")

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6)
            
            if (data === "[DONE]") break
            
            if (data.startsWith("[TOOL_START]")) {
                const toolName = data.slice(13)
                const toolCall: ToolCall = { name: toolName, args: "", status: "running" }
                setMessages((prev) => {
                    const newMessages = [...prev]
                    const lastMsg = newMessages[newMessages.length - 1]
                    lastMsg.toolCalls = [...(lastMsg.toolCalls || []), toolCall]
                    return newMessages
                })
            } else if (data.startsWith("[TOOL_END]")) {
                // Mark last tool as done
                setMessages((prev) => {
                    const newMessages = [...prev]
                    const lastMsg = newMessages[newMessages.length - 1]
                    if (lastMsg.toolCalls && lastMsg.toolCalls.length > 0) {
                        const lastTool = lastMsg.toolCalls[lastMsg.toolCalls.length - 1]
                        lastTool.status = "done"
                    }
                    return newMessages
                })
            } else if (!data.startsWith("Error:")) {
                assistantMessage += data
                setMessages((prev) => {
                    const newMessages = [...prev]
                    newMessages[newMessages.length - 1].content = assistantMessage
                    return newMessages
                })
            }
          }
        }
      }
    } catch (error) {
      console.error("Error:", error)
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, something went wrong. Please try again." },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion)
  }

  const clearChat = () => {
    setMessages([])
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-slate-100 z-[2000] flex flex-col"
    >
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-200">
            <Sparkles className="text-white" size={20} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">PRISM AI Agent</h1>
            <p className="text-sm text-slate-500">Infrastructure Intelligence Assistant</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={clearChat}
            className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <Trash2 size={16} />
            Clear Chat
          </button>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-lg transition-colors text-slate-500 hover:text-slate-700"
          >
            <X size={24} />
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Chat Area */}
        <div className="flex-1 flex flex-col">
          {/* Messages */}
          <div 
            ref={scrollRef}
            className="flex-1 overflow-y-auto p-6"
          >
            <div className="max-w-4xl mx-auto space-y-6">
              {messages.length === 0 && (
                <div className="text-center py-12">
                  <div className="w-20 h-20 bg-gradient-to-br from-blue-100 to-indigo-100 rounded-2xl flex items-center justify-center mx-auto mb-6">
                    <Bot className="h-10 w-10 text-blue-600" />
                  </div>
                  <h2 className="text-2xl font-bold text-slate-900 mb-2">How can I help you today?</h2>
                  <p className="text-slate-500 mb-8 max-w-md mx-auto">
                    I can help you analyze infrastructure data, optimize funding, search for bridges and roads, and forecast degradation.
                  </p>
                  
                  {/* Suggested Queries */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-2xl mx-auto">
                    {SUGGESTED_QUERIES.map((suggestion, i) => (
                      <button
                        key={i}
                        onClick={() => handleSuggestionClick(suggestion)}
                        className="text-left p-4 bg-white border border-slate-200 rounded-xl hover:border-blue-300 hover:shadow-md transition-all text-sm text-slate-700 hover:text-slate-900"
                      >
                        <span className="text-blue-500 mr-2">→</span>
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              
              {messages.map((message, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex gap-4 ${
                    message.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  {message.role === "assistant" && (
                    <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-sm font-bold shrink-0 shadow-lg shadow-blue-200">
                      AI
                    </div>
                  )}
                  
                  <div className={`space-y-2 max-w-[75%] ${message.role === "user" ? "items-end" : "items-start"}`}>
                    {message.toolCalls && message.toolCalls.length > 0 && (
                      <div className="space-y-1 mb-2">
                        {message.toolCalls.map((tool, i) => (
                          <ToolCallDisplay key={i} tool={tool} index={i} />
                        ))}
                      </div>
                    )}
                    
                    <div className={clsx(
                      "p-4 rounded-2xl shadow-sm",
                      message.role === "user" 
                        ? "bg-blue-600 text-white rounded-br-md" 
                        : "bg-white text-slate-800 border border-slate-200 rounded-bl-md"
                    )}>
                      {message.role === "assistant" ? (
                        <FormattedContent content={message.content} />
                      ) : (
                        <div className="text-sm whitespace-pre-wrap leading-relaxed">
                          {message.content}
                        </div>
                      )}
                    </div>
                  </div>

                  {message.role === "user" && (
                    <div className="h-10 w-10 rounded-xl bg-slate-700 flex items-center justify-center text-white text-sm font-bold shrink-0">
                      JD
                    </div>
                  )}
                </motion.div>
              ))}
              
              {isLoading && messages[messages.length - 1]?.role === "user" && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex gap-4"
                >
                  <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-sm font-bold shrink-0 shadow-lg shadow-blue-200">
                    AI
                  </div>
                  <div className="bg-white p-4 rounded-2xl rounded-bl-md border border-slate-200 shadow-sm flex items-center gap-3">
                    <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
                    <span className="text-sm text-slate-600">Analyzing your request...</span>
                  </div>
                </motion.div>
              )}
            </div>
          </div>

          {/* Input Area */}
          <div className="border-t border-slate-200 bg-white p-4">
            <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
              <div className="flex gap-3">
                <div className="flex-1 relative">
                  <input
                    type="text"
                    value={input}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setInput(e.target.value)}
                    placeholder="Ask about infrastructure, bridges, roads, or funding..."
                    className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                    disabled={isLoading}
                  />
                </div>
                <button 
                  type="submit" 
                  className={clsx(
                    "px-6 py-3 rounded-xl font-medium flex items-center gap-2 transition-all",
                    isLoading || !input.trim()
                      ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                      : "bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-200 hover:shadow-xl"
                  )}
                  disabled={isLoading || !input.trim()}
                >
                  <Send className="h-5 w-5" />
                  Send
                </button>
              </div>
              <p className="text-xs text-slate-400 mt-2 text-center">
                PRISM AI can search bridges, roads, optimize funding, and forecast infrastructure degradation
              </p>
            </form>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
