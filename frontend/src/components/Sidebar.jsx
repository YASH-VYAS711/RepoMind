import { useState } from "react"
import { useRef } from "react"

export default function Sidebar({
  repos,
  setRepos,
  activeRepoId,
  setActiveRepoId
}) {
  const [repoUrl, setRepoUrl] = useState("")
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState("")
  const [steps, setSteps] = useState([
    { label: "Cloning repository", status: "pending" },
    { label: "Scanning files", status: "pending" },
    { label: "Chunking code", status: "pending" },
    { label: "Generating embeddings", status: "pending" },
    { label: "Finalizing", status: "pending" },
  ])
  const logRef = useRef()
const updateStep = (keyword) => {
  setSteps((prev) => {
    const newSteps = prev.map(s => ({ ...s }))

    if (keyword.includes("Cloning")) {
      newSteps[0].status = "done"
      newSteps[1].status = "active"
    }

    if (keyword.includes("Scanning")) {
      newSteps[1].status = "done"
      newSteps[2].status = "active"
    }

    if (keyword.includes("Chunking")) {
      newSteps[2].status = "done"
      newSteps[3].status = "active"
    }

    if (keyword.includes("Embedding")) {
      newSteps[3].status = "done"
      newSteps[4].status = "active"
    }

    if (keyword.includes("DONE")) {
      newSteps.forEach((step) => (step.status = "done"))
    }

    return newSteps
  })
}

  const getRepoName = (url) => {
    if (!url) return "repo"
    const parts = url.split("/")
    let name = parts[parts.length - 1]
    return name.replace(".git", "").toLowerCase()
  }
const handleDelete = async (repoId) => {
  try {
    await fetch(`http://127.0.0.1:8000/repos/${repoId}`, {
      method: "DELETE",
    })

    // remove from UI
    setRepos((prev) => prev.filter((r) => r.id !== repoId))

    // reset active repo if deleted
    if (activeRepoId === repoId) {
      setActiveRepoId(null)
    }

  } catch (err) {
    console.error(err)
    alert("Failed to delete repo")
  }
}
  const ingestRepo = async () => {
    setSteps([
  { label: "Cloning repository", status: "active" },
  { label: "Scanning files", status: "pending" },
  { label: "Chunking code", status: "pending" },
  { label: "Generating embeddings", status: "pending" },
  { label: "Finalizing", status: "pending" },
])
    if (!repoUrl) return

    setLoading(true)
    setStatus("🚀 Starting ingestion...\n")

    try {
      const res = await fetch("http://127.0.0.1:8000/ingest/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ repo_url: repoUrl }),
      })

      const reader = res.body.getReader()
      const decoder = new TextDecoder()

      let fullText = ""
      let repoId = null

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        fullText += chunk
        setStatus((prev) => (prev + chunk).slice(-2000))

        updateStep(chunk)
        logRef.current?.scrollIntoView({ behavior: "smooth" })
        // detect DONE safely
        if (fullText.includes("DONE:")) {
          repoId = fullText.split("DONE:")[1].trim()
        }

        if (fullText.includes("ERROR:")) {
          throw new Error(fullText)
        }
      }

      if (repoId) {
        const newRepo = {
          id: repoId,
          url: repoUrl,
          messages: [],
        }

        setRepos((prev) => {
          const exists = prev.find((r) => r.id === repoId)
          if (exists) return prev
          return [newRepo, ...prev]
        })

        setActiveRepoId(repoId)
        setRepoUrl("")
        setStatus("✅ Ingestion complete!")
        
      }

    } catch (err) {
      console.error(err)
      setStatus("❌ Failed to ingest repo")
      alert("Failed to ingest repo")
    }

    setLoading(false)
  }

  return (
    <div className="w-80 border-r border-gray-800 p-4 flex flex-col">

      {/* Title */}
      <div className="flex items-center gap-2 mb-4">
  <img 
    src="/logo.png" 
    alt="RepoMind Logo" 
    className="w-10 h-10 object-contain"
  />
  <h1 className="text-xl font-bold text-green-400">
    RepoMind
  </h1>
</div>

      {/* Input */}
      <input
        value={repoUrl}
        disabled={loading}
        onChange={(e) => setRepoUrl(e.target.value)}
        placeholder="GitHub Repo URL"
        className="bg-gray-900 border border-gray-700 p-2 rounded outline-none focus:border-green-400"
      />

      <button
        onClick={ingestRepo}
        disabled={loading}
        className="mt-2 bg-green-500 hover:bg-green-600 disabled:opacity-50 text-black py-2 rounded font-semibold"
      >
        {loading ? "Ingesting..." : "Add Repo"}
      </button>

      {/* 🔥 Progress Status */}
      {loading && (
  <div className="mt-4 bg-black/30 p-3 rounded border border-gray-700 space-y-2">
    {steps.map((step, i) => (
  <div key={i} className="flex items-center gap-2 text-sm">

    {step.status === "done" && (
      <span className="text-green-400">✔</span>
    )}

    {step.status === "active" && (
      <span className="text-yellow-300 animate-pulse drop-shadow-[0_0_6px_rgba(255,255,0,0.5)]">⏳</span>
    )}

    {step.status === "pending" && (
      <span className="text-gray-500">⬜</span>
    )}

    <span
      className={`${
        step.status === "done"
          ? "text-green-400"
          : step.status === "active"
          ? "text-yellow-300"
          : "text-gray-400"
      }`}
    >
      {step.label}
    </span>
  </div>
))}
<div
  ref={logRef}
  className="text-xs text-gray-500 mt-3 whitespace-pre-line max-h-32 overflow-y-auto border-t border-gray-700 pt-2"
>
  {status}
</div>
  </div>
)}

      {/* Repo List */}
      <div className="mt-6 flex-1 overflow-y-auto space-y-2">
        {repos.map((repo) => (
          <div
  key={repo.id}
  className={`p-3 rounded cursor-pointer text-sm ${
    activeRepoId === repo.id
      ? "bg-green-500 text-black shadow-lg"
      : "bg-gray-800 hover:bg-gray-700"
  }`}
>
  <div
  className="flex justify-between items-center cursor-pointer"
  onClick={() => setActiveRepoId(repo.id)}
>

    {/* LEFT: repo name */}
    <div
      className="font-semibold cursor-pointer"
    >
      {getRepoName(repo.url)}
    </div>

    {/* RIGHT: delete button */}
    <button
      onClick={(e) => {
        e.stopPropagation()
        handleDelete(repo.id)
      }}
      className="text-gray-400 hover:text-red-500 transition"
    >
      ✕
    </button>

  </div>

  <div
    className={`text-xs truncate ${
      activeRepoId === repo.id
        ? "text-black/70"
        : "text-gray-400"
    }`}
  >
    {repo.url}
  </div>
</div>
        ))}
      </div>
    </div>
  )
}