import Link from "next/link";
import { Sparkles, Database, ArrowRight, Activity, Terminal } from "lucide-react";

export default function Home() {
  return (
    <div className="flex flex-col min-h-screen items-center justify-center bg-zinc-950 text-zinc-100 font-sans p-6">
      <main className="w-full max-w-3xl space-y-8 text-center sm:text-left">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-mono">
          <Activity className="w-3.5 h-3.5" /> NL-DB Query Platform — Phase 2 Live
        </div>

        <div className="space-y-3">
          <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl">
            Semantic Layer & <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-indigo-400 to-emerald-400">
              Real-Time Vector Embeddings
            </span>
          </h1>
          <p className="text-lg text-zinc-400 max-w-xl">
            Introspect target databases, generate composite 384-dimensional pgvector embeddings with live Server-Sent Events, and test schema vector similarity search.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 text-left">
          <Link
            href="/embeddings-demo"
            className="group p-5 rounded-2xl bg-zinc-900 border border-zinc-800 hover:border-blue-500/50 hover:bg-zinc-900/80 transition shadow-xl"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="p-2.5 bg-blue-500/20 text-blue-400 rounded-xl">
                <Sparkles className="w-5 h-5" />
              </div>
              <ArrowRight className="w-4 h-4 text-zinc-500 group-hover:text-blue-400 group-hover:translate-x-1 transition" />
            </div>
            <h3 className="font-semibold text-white text-base group-hover:text-blue-400 transition">
              Live SSE Embedding Stream
            </h3>
            <p className="text-xs text-zinc-400 mt-1">
              Watch real-time progress as database tables and columns are converted into vector embeddings.
            </p>
          </Link>

          <div className="p-5 rounded-2xl bg-zinc-900/50 border border-zinc-800/80 text-left">
            <div className="flex items-center justify-between mb-3">
              <div className="p-2.5 bg-emerald-500/20 text-emerald-400 rounded-xl">
                <Database className="w-5 h-5" />
              </div>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Active
              </span>
            </div>
            <h3 className="font-semibold text-zinc-200 text-base">
              Hugging Face + pgvector
            </h3>
            <p className="text-xs text-zinc-400 mt-1">
              Embedding model `BAAI/bge-small-en-v1.5` storing 384d vectors with cosine distance matching.
            </p>
          </div>
        </div>

        <div className="pt-6 border-t border-zinc-800/80 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-zinc-500 font-mono">
          <span>Backend API: http://localhost:8000</span>
          <span>FastAPI + Next.js 16 + Tailwind CSS</span>
        </div>
      </main>
    </div>
  );
}
