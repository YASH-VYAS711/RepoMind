import { useState, useRef, useEffect  } from "react"
import ReactMarkdown from "react-markdown"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism"

export default function Chat({ repo, setRepos }) {
  const bottomRef = useRef()
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
    const getRepoName = (url) => {
  if (!url) return "repo"
  const parts = url.split("/")
  let name = parts[parts.length - 1]
  return name.replace(".git", "").toLowerCase()
}
const repoName = getRepoName(repo?.url)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [repo?.messages])

    if (!repo) {
  return (
    <div className="flex-1 flex items-center justify-center text-gray-500">
      🚀 Add a repo to start exploring
    </div>
  )
}
  const updateMessages = (newMessages) => {
    setRepos(prev =>
      prev.map(r =>
        r.id === repo.id ? { ...r, messages: newMessages } : r
      )
    )
  }

const sendMessageWith = async (text) => {
  if (!text.trim()) return

  const userMsg = { role: "user", content: text }
  const newMessages = [...(repo.messages || []), userMsg]

  updateMessages(newMessages)
  setInput("")
  setLoading(true)

  // Show placeholder immediately — before fetch even starts
  updateMessages([...newMessages, { role: "bot", loading: true, answer: "" }])

  try {
    const res = await fetch("http://127.0.0.1:8000/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: text, repo_id: repo.id }),
    })

    const reader = res.body.getReader()
    const decoder = new TextDecoder()

    let answer = ""

    while (true) {
  const { done, value } = await reader.read()
  if (done) break

  const chunk = decoder.decode(value, { stream: true })

      if (chunk.includes("ERROR:")) {
  updateMessages([
    ...newMessages,
    {
      role: "bot",
      loading: false,
      answer: "❌ " + chunk.replace("ERROR:", "")
    }
  ])
  return
}
  answer += chunk
  updateMessages([
    ...newMessages,
    { role: "bot", loading: true, answer }
  ])
}

    // Mark loading: false — this triggers switch from plain text to ReactMarkdown
    updateMessages([...newMessages, { role: "bot", loading: false, answer }])

  } catch (err) {
  console.error(err)

  updateMessages([
    ...newMessages,
    {
      role: "bot",
      loading: false,
      answer: "❌ Failed to generate response. Please try again."
    }
  ])
}

  setLoading(false)
}

// Keep this for the Send button and Enter key
const sendMessage = () => sendMessageWith(input)

  return (
    <div className="flex-1 flex flex-col">

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {!repo.messages?.length ? (
          <div className="h-full flex flex-col items-center justify-center gap-3 text-gray-500">
            <p className="text-lg">
              Ask anything about <span className="text-green-400 font-semibold">{repoName}</span>
            </p>
            {["Give an overview", "How are routes defined?", "Where is auth handled?"].map(q => (
              <button
                key={q}
                onClick={() => {
                  setInput(q)          // set the input text
                  // ✅ call sendMessage directly with the value, don't rely on state
                  sendMessageWith(q)
                }}
                className="text-sm border border-gray-700 px-4 py-2 rounded hover:border-green-400 hover:text-green-400 transition"
              >
                {q}
              </button>
            ))}
          </div>
        ) : (
          repo.messages.map((msg, i) => {
            if (msg.role === "user") {
              return (
                <div key={i} className="p-3 rounded-lg max-w-2xl bg-blue-600 ml-auto">
                  {msg.content}
                </div>
              )
            }

            // Bot message — split status lines from answer
            
            return (
  <div key={i} className="max-w-2xl space-y-1">
    {msg.loading && (
      <div className="text-sm text-green-400 animate-pulse">
        🤖 Generating...
      </div>
    )}
    {msg.answer && (
      <div className="p-3 rounded-lg bg-gray-800">
        {msg.loading ? (
  <div className="whitespace-pre-wrap">{msg.answer}</div>
) : (
        <ReactMarkdown components={{
          code({ inline, className, children }) {
            const lang = /language-(\w+)/.exec(className || "")?.[1]
            return !inline && lang ? (
              <SyntaxHighlighter style={oneDark} language={lang} PreTag="div">
                {String(children).replace(/\n$/, "")}
              </SyntaxHighlighter>
            ) : (
              <code className="bg-gray-700 px-1 rounded text-sm">{children}</code>
            )
          }
        }}>
          {msg.answer}
        </ReactMarkdown>
)}
      </div>
    )}
  </div>
)
          })
        )}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-800 flex gap-2">
        <input
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault()
              sendMessage()
            }
          }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the repo..."
          className="flex-1 bg-gray-900 p-3 rounded border border-gray-700 outline-none focus:border-green-400"
        />

        <button
          onClick={sendMessage}
          disabled={loading}
          className="bg-green-500 hover:bg-green-600 text-black px-5 rounded font-semibold"
        >
          Send
        </button>
      </div>
      <div ref={bottomRef} />
    </div>
  )
}