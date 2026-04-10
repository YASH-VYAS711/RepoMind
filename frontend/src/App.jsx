import { useState, useEffect } from "react"
import Sidebar from "./components/Sidebar"
import Chat from "./components/Chat"

export default function App() {
  const [repos, setRepos] = useState(() => {
    try {
      // Only restore id + url, never messages
      // Messages were causing localStorage to balloon and lag the input
      const saved = JSON.parse(localStorage.getItem("repos") || "[]")
      return saved.map(r => ({ id: r.id, url: r.url, messages: [] }))
    } catch { return [] }
  })

  const [activeRepoId, setActiveRepoId] = useState(() => {
    return localStorage.getItem("activeRepoId") || null
  })

  useEffect(() => {
    // Only persist id + url, not messages
    const slim = repos.map(r => ({ id: r.id, url: r.url }))
    localStorage.setItem("repos", JSON.stringify(slim))
  }, [repos])

  useEffect(() => {
    if (activeRepoId) localStorage.setItem("activeRepoId", activeRepoId)
    else localStorage.removeItem("activeRepoId")
  }, [activeRepoId])

  const activeRepo = repos.find(r => r.id === activeRepoId) || repos[0] || null

  return (
    <div className="flex h-screen bg-gray-950 text-white">
      <Sidebar
        repos={repos}
        setRepos={setRepos}
        activeRepoId={activeRepoId}
        setActiveRepoId={setActiveRepoId}
      />
      <Chat
        key={activeRepo?.id}
        repo={activeRepo}
        setRepos={setRepos}
      />
    </div>
  )
}