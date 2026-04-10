import { useState } from "react"
import axios from "axios"

export default function Sidebar({
  repos,
  setRepos,
  activeRepoId,
  setActiveRepoId
}) {
  const [repoUrl, setRepoUrl] = useState("")
  const [loading, setLoading] = useState(false)

    const getRepoName = (url) => {
        if (!url) return "repo"
        const parts = url.split("/")
        let name = parts[parts.length - 1]
        return name.replace(".git", "").toLowerCase()
    }
  const ingestRepo = async () => {
  if (!repoUrl) return

  setLoading(true)
  try {
    const res = await axios.post("http://127.0.0.1:8000/ingest", {
      repo_url: repoUrl,
    })

    const newRepo = {
      id: res.data.repo_id,
      url: repoUrl,
      messages: [],
    }

    setRepos(prev => {
      const exists = prev.find(r => r.id === newRepo.id)
      if (exists) {
        setActiveRepoId(exists.id)
        return prev // 🚫 don't add duplicate
      }
      return [newRepo, ...prev]
    })

    setActiveRepoId(newRepo.id)
    setRepoUrl("")

  } catch (err) {
    console.error(err)
    alert("Failed to ingest repo")
  }
  setLoading(false)
}

  return (
    <div className="w-80 border-r border-gray-800 p-4 flex flex-col">

      {/* Title */}
      <h1 className="text-xl font-bold text-green-400 mb-4">
        RepoMind
      </h1>

      {/* Input */}
      <input
        value={repoUrl}
        onChange={(e) => setRepoUrl(e.target.value)}
        placeholder="GitHub Repo URL"
        className="bg-gray-900 border border-gray-700 p-2 rounded outline-none focus:border-green-400"
      />

      <button
        onClick={ingestRepo}
        className="mt-2 bg-green-500 hover:bg-green-600 text-black py-2 rounded font-semibold"
      >
        {loading ? "Ingesting..." : "Add Repo"}
      </button>

      {/* Repo List */}
      <div className="mt-6 flex-1 overflow-y-auto space-y-2">
        {repos.map((repo) => (
          <div
            key={repo.id}
            onClick={() => setActiveRepoId(repo.id)}
            className={`p-3 rounded cursor-pointer text-sm ${
              activeRepoId === repo.id
                ? "bg-green-500 text-black shadow-lg"
                : "bg-gray-800 hover:bg-gray-700"
            }`}
          >
            <div className="font-semibold">
              {getRepoName(repo.url)}
            </div>
            <div className={`text-xs truncate ${
  activeRepoId === repo.id
    ? "text-black/70"
    : "text-gray-400"
}`}>
              {repo.url}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}