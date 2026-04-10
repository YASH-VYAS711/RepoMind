import { useState, useEffect } from "react"
import Sidebar from "./components/Sidebar"
import Chat from "./components/Chat"

export default function App() {
 const [repos, setRepos] = useState(() => {
  try { return JSON.parse(localStorage.getItem("repos") || "[]") }
  catch { return [] }
})
  const [activeRepoId, setActiveRepoId] = useState(null)
  useEffect(() => {
  localStorage.setItem("repos", JSON.stringify(
    repos.map(r => ({ id: r.id, url: r.url, messages: r.messages }))
  ))
}, [repos])
  const activeRepo = repos.find(r => r.id === activeRepoId)

  return (
    <div className="h-screen flex bg-[#0b0f19] text-gray-200">
      <Sidebar
        repos={repos}
        setRepos={setRepos}
        activeRepoId={activeRepoId}
        setActiveRepoId={setActiveRepoId}
      />

      <Chat
        repo={activeRepo}
        setRepos={setRepos}
      />
    </div>
  )
}