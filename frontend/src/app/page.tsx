"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Sparkles,
  Database,
  ArrowRight,
  ShieldCheck,
  Zap,
  Bot,
  Search,
  Check,
  Copy,
  Terminal,
  Activity,
  Layers,
  Lock,
  Cpu,
  Server,
  Code2,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export default function HomePage(): React.JSX.Element {
  const [copied, setCopied] = useState(false);

  const sampleSql = `SELECT c.name AS customer_name,
       COUNT(o.id) AS total_orders,
       SUM(o.total_amount) AS total_revenue
FROM customers c
JOIN orders o ON c.id = o.customer_id
WHERE o.created_at >= NOW() - INTERVAL '30 days'
GROUP BY c.name
ORDER BY total_revenue DESC
LIMIT 5;`;

  const copySql = () => {
    navigator.clipboard.writeText(sampleSql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 selection:bg-blue-500/30 selection:text-blue-200">
      {/* Ambient background glow */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none -z-10">
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-gradient-to-b from-blue-600/15 via-indigo-600/10 to-transparent blur-[140px] rounded-full" />
        <div className="absolute top-1/3 -left-40 w-96 h-96 bg-emerald-500/10 blur-[130px] rounded-full" />
        <div className="absolute bottom-10 -right-40 w-96 h-96 bg-blue-500/10 blur-[140px] rounded-full" />
      </div>

      {/* Navigation Header */}
      <header className="sticky top-0 z-50 border-b border-zinc-800/80 bg-zinc-950/75 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white shadow-lg shadow-blue-500/25">
              <Database className="h-5 w-5" />
            </div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg tracking-tight text-white">AskMyDB</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                v1.0
              </span>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-6 text-sm text-zinc-400">
            <a href="#features" className="hover:text-zinc-100 transition-colors">
              Features
            </a>
            <a href="#architecture" className="hover:text-zinc-100 transition-colors">
              Architecture
            </a>
            <a href="#dialects" className="hover:text-zinc-100 transition-colors">
              Supported DBs
            </a>
            <Link
              href="/embeddings-demo"
              className="flex items-center gap-1.5 text-blue-400 hover:text-blue-300 transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5" />
              Live SSE Demo
            </Link>
          </nav>

          <div className="flex items-center gap-3">
            <Link href="/login">
              <Button
                variant="ghost"
                className="text-zinc-300 hover:text-white hover:bg-zinc-800/80 text-sm font-medium"
              >
                Sign In
              </Button>
            </Link>
            <Link href="/register">
              <Button className="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium shadow-md shadow-blue-600/20">
                Get Started
                <ArrowRight className="ml-1.5 h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative pt-16 pb-20 md:pt-24 md:pb-32 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <div className="text-center space-y-6 max-w-4xl mx-auto">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-mono">
            <Sparkles className="w-3.5 h-3.5 text-blue-400 animate-pulse" />
            <span>Agentic Natural Language to Dialect-Safe SQL</span>
          </div>

          {/* Main Title */}
          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-white leading-[1.1]">
            Talk to Your Database in{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-indigo-300 to-emerald-400">
              Plain English.
            </span>
          </h1>

          {/* Subtitle */}
          <p className="text-lg sm:text-xl text-zinc-400 max-w-2xl mx-auto leading-relaxed">
            Connect any SQL database via connection string. Ask complex analytical questions, get
            dialect-precise SQL, verify read-only guardrails, and receive structured answers in seconds.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
            <Link href="/register" className="w-full sm:w-auto">
              <Button className="w-full sm:w-auto h-11 px-6 bg-blue-600 hover:bg-blue-500 text-white font-semibold text-base shadow-xl shadow-blue-600/25">
                Start Querying Free
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>

            <Link href="/embeddings-demo" className="w-full sm:w-auto">
              <Button
                variant="outline"
                className="w-full sm:w-auto h-11 px-6 border-zinc-800 bg-zinc-900/60 hover:bg-zinc-800 hover:text-white text-zinc-300 text-base"
              >
                <Activity className="mr-2 h-4 w-4 text-emerald-400" />
                Live SSE Vector Stream
              </Button>
            </Link>
          </div>

          {/* Micro stats banner */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-12 max-w-3xl mx-auto text-left">
            <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
              <div className="text-2xl font-bold text-white">5+</div>
              <div className="text-xs text-zinc-500 font-medium">SQL Dialects Supported</div>
            </div>
            <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
              <div className="text-2xl font-bold text-emerald-400">384d</div>
              <div className="text-xs text-zinc-500 font-medium">pgvector Schema Embeddings</div>
            </div>
            <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
              <div className="text-2xl font-bold text-blue-400">3-Layer</div>
              <div className="text-xs text-zinc-500 font-medium">Read-Only Guardrails</div>
            </div>
            <div className="p-4 rounded-xl bg-zinc-900/40 border border-zinc-800/60">
              <div className="text-2xl font-bold text-indigo-400">100%</div>
              <div className="text-xs text-zinc-500 font-medium">Project Tenant Isolation</div>
            </div>
          </div>
        </div>

        {/* Interactive Query Simulator Terminal */}
        <div className="mt-16 max-w-5xl mx-auto">
          <div className="relative rounded-2xl border border-zinc-800 bg-zinc-900/90 shadow-2xl overflow-hidden">
            {/* Terminal Window Bar */}
            <div className="px-4 py-3 bg-zinc-950 border-b border-zinc-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 rounded-full bg-red-500/80" />
                <div className="h-3 w-3 rounded-full bg-yellow-500/80" />
                <div className="h-3 w-3 rounded-full bg-green-500/80" />
                <span className="ml-2 text-xs font-mono text-zinc-400 flex items-center gap-1.5">
                  <Terminal className="h-3.5 w-3.5 text-blue-400" />
                  askmydb-agent-runtime ~ PostgreSQL Dialect
                </span>
              </div>
              <span className="text-[11px] font-mono text-zinc-500">Live Simulation</span>
            </div>

            {/* Terminal Content */}
            <div className="p-5 md:p-7 space-y-6 font-mono text-sm">
              {/* Question */}
              <div className="space-y-2">
                <div className="text-xs uppercase tracking-wider text-zinc-500 font-semibold flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-blue-500" />
                  User Natural Language Query
                </div>
                <div className="p-3.5 rounded-xl bg-zinc-950/80 border border-zinc-800 text-zinc-100 flex items-center gap-3">
                  <span className="text-blue-400 font-bold">&gt;</span>
                  <span className="font-sans font-medium text-base text-zinc-200">
                    &quot;Who are our top 5 customer accounts by total revenue over the last 30 days?&quot;
                  </span>
                </div>
              </div>

              {/* Agent Pipeline Steps */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                <div className="p-3 rounded-lg bg-zinc-950/50 border border-zinc-800/80 space-y-1">
                  <div className="text-blue-400 font-semibold flex items-center gap-1.5">
                    <Bot className="h-3.5 w-3.5" /> 1. Intent Node
                  </div>
                  <p className="text-zinc-400 font-sans">
                    Classified as <span className="text-zinc-200 font-mono">aggregation</span> with entity filters.
                  </p>
                </div>

                <div className="p-3 rounded-lg bg-zinc-950/50 border border-zinc-800/80 space-y-1">
                  <div className="text-emerald-400 font-semibold flex items-center gap-1.5">
                    <Search className="h-3.5 w-3.5" /> 2. Vector Schema Linker
                  </div>
                  <p className="text-zinc-400 font-sans">
                    Matched <span className="text-zinc-200 font-mono">orders.total_amount</span> (96.4% cosine score).
                  </p>
                </div>

                <div className="p-3 rounded-lg bg-zinc-950/50 border border-zinc-800/80 space-y-1">
                  <div className="text-indigo-400 font-semibold flex items-center gap-1.5">
                    <ShieldCheck className="h-3.5 w-3.5" /> 3. AST Guardrail
                  </div>
                  <p className="text-zinc-400 font-sans">
                    Parsed via <span className="text-zinc-200 font-mono">sqlglot</span>. Verified read-only SELECT.
                  </p>
                </div>
              </div>

              {/* Generated SQL */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="text-xs uppercase tracking-wider text-zinc-500 font-semibold flex items-center gap-2">
                    <Code2 className="h-3.5 w-3.5 text-indigo-400" />
                    Generated Dialect SQL
                  </div>
                  <button
                    onClick={copySql}
                    className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1 transition"
                  >
                    {copied ? (
                      <>
                        <Check className="h-3.5 w-3.5 text-emerald-400" />
                        <span className="text-emerald-400">Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="h-3.5 w-3.5" />
                        <span>Copy SQL</span>
                      </>
                    )}
                  </button>
                </div>
                <pre className="p-4 rounded-xl bg-zinc-950 border border-zinc-800/80 text-emerald-400 text-xs sm:text-sm overflow-x-auto leading-relaxed">
                  {sampleSql}
                </pre>
              </div>

              {/* Natural Language Summary */}
              <div className="p-4 rounded-xl bg-blue-500/10 border border-blue-500/20 text-zinc-300 font-sans text-sm space-y-1">
                <div className="font-semibold text-blue-300 flex items-center gap-2">
                  <Sparkles className="h-4 w-4" /> AI Natural Language Answer
                </div>
                <p className="text-zinc-300 leading-relaxed">
                  Your highest grossing customer over the past 30 days is{" "}
                  <strong className="text-white">Acme Global</strong> ($48,250.00 across 24 orders),
                  followed by <strong className="text-white">Apex Logistics</strong> ($39,120.00). Total
                  aggregate revenue for the top 5 accounts reached $142,680.00.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 4-Stage Architecture Flow */}
      <section id="architecture" className="py-20 border-t border-zinc-800/80 bg-zinc-900/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
          <div className="text-center space-y-3 max-w-3xl mx-auto">
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white">
              How AskMyDB Works
            </h2>
            <p className="text-zinc-400 text-base">
              A structured agentic pipeline that eliminates hallucinations by anchoring reasoning in your actual schema.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            {/* Step 1 */}
            <div className="p-6 rounded-2xl bg-zinc-900 border border-zinc-800/90 space-y-4 relative">
              <div className="h-10 w-10 rounded-xl bg-blue-500/10 text-blue-400 flex items-center justify-center font-bold font-mono">
                01
              </div>
              <h3 className="font-semibold text-lg text-white">Schema Auto-Discovery</h3>
              <p className="text-zinc-400 text-xs leading-relaxed">
                Connect via encrypted connection string. SQLAlchemy reflection auto-discovers tables, columns, primary keys, and foreign keys.
              </p>
            </div>

            {/* Step 2 */}
            <div className="p-6 rounded-2xl bg-zinc-900 border border-zinc-800/90 space-y-4 relative">
              <div className="h-10 w-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center font-bold font-mono">
                02
              </div>
              <h3 className="font-semibold text-lg text-white">Vector Schema Linking</h3>
              <p className="text-zinc-400 text-xs leading-relaxed">
                Table descriptions and column metadata are embedded into 384d pgvector embeddings. Relevant schema is retrieved dynamically.
              </p>
            </div>

            {/* Step 3 */}
            <div className="p-6 rounded-2xl bg-zinc-900 border border-zinc-800/90 space-y-4 relative">
              <div className="h-10 w-10 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center font-bold font-mono">
                03
              </div>
              <h3 className="font-semibold text-lg text-white">LangGraph SQL Agent</h3>
              <p className="text-zinc-400 text-xs leading-relaxed">
                Intent classification and dialect-specific generation using state-of-the-art LLMs (Claude, OpenAI, Groq, Hugging Face).
              </p>
            </div>

            {/* Step 4 */}
            <div className="p-6 rounded-2xl bg-zinc-900 border border-zinc-800/90 space-y-4 relative">
              <div className="h-10 w-10 rounded-xl bg-purple-500/10 text-purple-400 flex items-center justify-center font-bold font-mono">
                04
              </div>
              <h3 className="font-semibold text-lg text-white">Self-Correction & Output</h3>
              <p className="text-zinc-400 text-xs leading-relaxed">
                Automatic retry loop heals SQL syntax or join errors up to 3 times before streaming plain-English answers & formatted tables.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Bento Grid Features Section */}
      <section id="features" className="py-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
        <div className="text-center space-y-3 max-w-3xl mx-auto">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-white">
            Engineered for Real-World Databases
          </h2>
          <p className="text-zinc-400 text-base">
            Everything you need to deliver self-serve data answers without risking production integrity.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Card 1 */}
          <div className="p-7 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 hover:border-zinc-700 transition space-y-3">
            <div className="h-10 w-10 rounded-xl bg-blue-500/10 text-blue-400 flex items-center justify-center">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <h3 className="font-semibold text-lg text-white">3-Tier Execution Guardrails</h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Read-only AST parsing with sqlglot, 10s query execution timeouts, and strict 1,000 row limits protect your databases from runaway or destructive queries.
            </p>
          </div>

          {/* Card 2 */}
          <div className="p-7 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 hover:border-zinc-700 transition space-y-3">
            <div className="h-10 w-10 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center">
              <Cpu className="h-5 w-5" />
            </div>
            <h3 className="font-semibold text-lg text-white">Self-Healing Retries</h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              If an execution error occurs (missing column alias, wrong join key), the agent diagnoses the database error message and repairs the query automatically.
            </p>
          </div>

          {/* Card 3 */}
          <div className="p-7 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 hover:border-zinc-700 transition space-y-3">
            <div className="h-10 w-10 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
              <Zap className="h-5 w-5" />
            </div>
            <h3 className="font-semibold text-lg text-white">Real-Time SSE Streaming</h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Follow every step in real-time. From intent classification and vector schema search to live SQL output, stay informed with granular progress events.
            </p>
          </div>

          {/* Card 4 */}
          <div className="p-7 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 hover:border-zinc-700 transition space-y-3">
            <div className="h-10 w-10 rounded-xl bg-purple-500/10 text-purple-400 flex items-center justify-center">
              <Layers className="h-5 w-5" />
            </div>
            <h3 className="font-semibold text-lg text-white">Semantic Layer & Auto-Suggest</h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Enrich cryptic abbreviations with business glossary terms and column notes. Use swappable LLMs to auto-generate draft descriptions across your schema.
            </p>
          </div>

          {/* Card 5 */}
          <div className="p-7 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 hover:border-zinc-700 transition space-y-3">
            <div className="h-10 w-10 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center">
              <Bot className="h-5 w-5" />
            </div>
            <h3 className="font-semibold text-lg text-white">Conversational Memory</h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Ask follow-up questions seamlessly (&quot;now filter by active accounts only&quot;). LangGraph PostgreSQL checkpointing retains complete session context.
            </p>
          </div>

          {/* Card 6 */}
          <div className="p-7 rounded-2xl bg-zinc-900/60 border border-zinc-800/80 hover:border-zinc-700 transition space-y-3">
            <div className="h-10 w-10 rounded-xl bg-rose-500/10 text-rose-400 flex items-center justify-center">
              <Lock className="h-5 w-5" />
            </div>
            <h3 className="font-semibold text-lg text-white">Fernet Encrypted Multi-Tenancy</h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              Credentials are encrypted at rest with Fernet cryptographic keys. Every query, schema cache, and chat session is strictly scoped by project ID.
            </p>
          </div>
        </div>
      </section>

      {/* Supported Databases */}
      <section id="dialects" className="py-16 border-t border-zinc-800/80 bg-zinc-900/40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-8">
          <h2 className="text-2xl sm:text-3xl font-bold text-white">
            Connects Directly with Leading SQL Engines
          </h2>

          <div className="flex flex-wrap items-center justify-center gap-4 max-w-4xl mx-auto">
            {["PostgreSQL", "MySQL", "Microsoft SQL Server", "Snowflake", "SQLite", "Amazon RDS", "Supabase"].map(
              (engine) => (
                <div
                  key={engine}
                  className="px-5 py-2.5 rounded-xl bg-zinc-950/80 border border-zinc-800 text-zinc-200 text-sm font-medium flex items-center gap-2 hover:border-blue-500/50 hover:bg-zinc-900 transition"
                >
                  <Server className="h-4 w-4 text-blue-400" />
                  {engine}
                </div>
              )
            )}
          </div>
        </div>
      </section>

      {/* Bottom CTA Banner */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto">
        <div className="rounded-3xl bg-gradient-to-r from-blue-900/30 via-indigo-900/30 to-zinc-900 border border-blue-500/20 p-8 sm:p-14 text-center space-y-6 relative overflow-hidden">
          <div className="absolute -top-24 -right-24 h-64 w-64 rounded-full bg-blue-500/20 blur-[100px] pointer-events-none" />
          <h2 className="text-3xl sm:text-5xl font-extrabold text-white tracking-tight">
            Unlock the Value of Your Data Today
          </h2>
          <p className="text-zinc-400 text-base sm:text-lg max-w-2xl mx-auto">
            Connect your database in seconds and start asking natural language questions with full confidence.
          </p>
          <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link href="/register">
              <Button className="h-11 px-8 bg-blue-600 hover:bg-blue-500 text-white font-semibold text-base shadow-xl shadow-blue-600/30">
                Create Free Account
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
            <Link href="/login">
              <Button
                variant="outline"
                className="h-11 px-8 border-zinc-700 bg-zinc-900/80 hover:bg-zinc-800 text-zinc-200 text-base"
              >
                Sign In
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-zinc-800/80 py-8 bg-zinc-950">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-zinc-500 font-mono">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-blue-500" />
            <span>AskMyDB — Natural Language Database Querying Platform</span>
          </div>
          <div>&copy; 2026 AskMyDB. Multi-tenant agentic NL-to-SQL engine.</div>
        </div>
      </footer>
    </div>
  );
}
