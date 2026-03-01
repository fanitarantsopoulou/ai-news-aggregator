<template>
  <div class="shell">
    <!-- Scanline overlay for CRT effect -->
    <div class="scanlines" aria-hidden="true"></div>

    <div class="container">
      <!-- ── Header ── -->
      <header class="header">
        <div class="header-left">
          <span class="logo-bracket">[</span>
          <span class="logo-text">AI<em>NEWS</em></span>
          <span class="logo-bracket">]</span>
          <span class="logo-sub">/ aggregator v1.0</span>
        </div>
        <div class="header-right">
          <span class="status-dot" :class="{ active: lastFetchTime }"></span>
          <span class="status-label">{{ lastFetchTime ? 'INDEXED ' + lastFetchTime : 'STANDBY' }}</span>
        </div>
      </header>

      <!-- ── Search bar ── -->
      <section class="search-section">
        <label class="search-label" for="topic-input">
          <span class="prompt">&gt;&nbsp;</span>ENTER TOPIC QUERY
        </label>
        <div class="search-row">
          <input
            id="topic-input"
            v-model="topic"
            class="search-input"
            type="text"
            placeholder="e.g. 6G networks, quantum computing, LLM inference..."
            autocomplete="off"
            spellcheck="false"
            :disabled="loading"
            @keydown.enter="fetchSummary"
          />
          <button
            class="search-btn"
            :disabled="loading || !topic.trim()"
            @click="fetchSummary"
          >
            <span v-if="!loading">RUN&nbsp;&#x25B6;</span>
            <span v-else class="btn-spinner"></span>
          </button>
        </div>
      </section>

      <!-- ── Error state ── -->
      <Transition name="fade">
        <div v-if="error" class="error-banner" role="alert">
          <span class="error-icon">&#x26A0;</span>
          <span>{{ error }}</span>
          <button class="error-dismiss" @click="error = null">&#x2715;</button>
        </div>
      </Transition>

      <!-- ── Skeleton / loading state ── -->
      <Transition name="fade">
        <div v-if="loading" class="result-card skeleton-card" aria-busy="true" aria-label="Generating summary…">
          <div class="skeleton-header">
            <div class="skel skel-tag"></div>
            <div class="skel skel-meta"></div>
          </div>
          <div class="skel skel-line w80"></div>
          <div class="skel skel-line w95"></div>
          <div class="skel skel-line w70"></div>
          <div class="skeleton-sources">
            <div class="skel skel-source"></div>
            <div class="skel skel-source w60"></div>
            <div class="skel skel-source w75"></div>
          </div>
          <p class="skeleton-label">⚙ Querying vector store &amp; LLM…</p>
        </div>
      </Transition>

      <!-- ── Result card ── -->
      <Transition name="slide-up">
        <div v-if="result && !loading" class="result-card">

          <!-- Card header -->
          <div class="result-header">
            <div class="result-topic-row">
              <span class="tag">SUMMARY</span>
              <h2 class="result-topic">{{ result.topic }}</h2>
            </div>
            <div class="result-meta">
              <span class="meta-chip">{{ result.chunks_retrieved }} chunks</span>
              <span class="meta-chip">{{ result.sources.length }} sources</span>
            </div>
          </div>

          <!-- Divider -->
          <div class="divider"></div>

          <!-- Summary body -->
          <div class="summary-body">
            <span class="summary-icon">&#9654;</span>
            <p class="summary-text">{{ result.summary }}</p>
          </div>

          <!-- Sources -->
          <div class="sources-section">
            <p class="sources-heading">SOURCE DOCUMENTS</p>
            <ul class="sources-list">
              <li
                v-for="(src, i) in result.sources"
                :key="src.url"
                class="source-item"
              >
                <span class="source-index">{{ String(i + 1).padStart(2, '0') }}</span>
                <a :href="src.url" target="_blank" rel="noopener noreferrer" class="source-link">
                  {{ src.title }}
                  <span class="source-arrow">&#x2197;</span>
                </a>
              </li>
            </ul>
          </div>

        </div>
      </Transition>

      <!-- ── Empty state ── -->
      <Transition name="fade">
        <div v-if="!result && !loading && !error" class="empty-state">
          <div class="empty-grid" aria-hidden="true">
            <span v-for="n in 64" :key="n" class="empty-dot" :style="{ animationDelay: `${(n * 137) % 3000}ms` }">·</span>
          </div>
          <p class="empty-label">Enter a topic and press <kbd>RUN</kbd> or <kbd>↵ Enter</kbd></p>
        </div>
      </Transition>

      <!-- ── Footer ── -->
      <footer class="footer">
        <span>Powered by LangChain + ChromaDB</span>
        <span class="footer-sep">·</span>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const topic   = ref('')
const loading = ref(false)
const result  = ref(null)
const error   = ref(null)
const lastFetchTime = ref('')

async function fetchSummary() {
  if (!topic.value.trim() || loading.value) return

  loading.value = true
  result.value  = null
  error.value   = null

  try {
    const url = `http://localhost:8000/api/summary?topic=${encodeURIComponent(topic.value.trim())}`
    const res = await fetch(url)

    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail || `Server returned ${res.status}`)
    }

    result.value = await res.json()
    lastFetchTime.value = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch (err) {
    error.value = err.message || 'An unexpected error occurred.'
  } finally {
    loading.value = false
  }
}
</script>

<style>
/* ─── Fonts ─────────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,300;0,400;0,500;1,400&family=Syne:wght@700;800&display=swap');

/* ─── CSS Variables ─────────────────────────────────────────────────────── */
:root {
  --bg:        #0a0a0a;
  --surface:   #111111;
  --surface2:  #181818;
  --border:    #2a2a2a;
  --amber:     #f5a623;
  --amber-dim: #a86f10;
  --green:     #39d353;
  --red:       #ff5f57;
  --text:      #d4d0c8;
  --text-dim:  #666;
  --mono:      'DM Mono', 'Courier New', monospace;
  --display:   'Syne', sans-serif;
  --radius:    4px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, #app {
  height: 100%;
  background: var(--bg);
  color: var(--text);
  font-family: var(--mono);
  font-size: 14px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}

/* ─── CRT Scanlines ─────────────────────────────────────────────────────── */
.shell {
  position: relative;
  min-height: 100vh;
}
.scanlines {
  pointer-events: none;
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0,0,0,.08) 2px,
    rgba(0,0,0,.08) 4px
  );
}

/* ─── Layout ────────────────────────────────────────────────────────────── */
.container {
  max-width: 780px;
  margin: 0 auto;
  padding: 48px 24px 80px;
  display: flex;
  flex-direction: column;
  gap: 32px;
}

/* ─── Header ────────────────────────────────────────────────────────────── */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border);
  padding-bottom: 16px;
}
.header-left {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.logo-bracket { color: var(--amber); font-size: 22px; font-weight: 500; }
.logo-text {
  font-family: var(--display);
  font-size: 22px;
  font-weight: 800;
  color: #fff;
  letter-spacing: 1px;
}
.logo-text em { font-style: normal; color: var(--amber); }
.logo-sub { color: var(--text-dim); font-size: 12px; }
.header-right { display: flex; align-items: center; gap: 8px; font-size: 11px; color: var(--text-dim); }
.status-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--text-dim);
  transition: background .3s;
}
.status-dot.active { background: var(--green); box-shadow: 0 0 6px var(--green); }

/* ─── Search ────────────────────────────────────────────────────────────── */
.search-section { display: flex; flex-direction: column; gap: 10px; }
.search-label {
  font-size: 11px;
  letter-spacing: 2px;
  color: var(--amber);
  text-transform: uppercase;
}
.prompt { opacity: .6; }

.search-row { display: flex; gap: 10px; }

.search-input {
  flex: 1;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text);
  font-family: var(--mono);
  font-size: 14px;
  padding: 12px 16px;
  outline: none;
  transition: border-color .2s, box-shadow .2s;
  caret-color: var(--amber);
}
.search-input::placeholder { color: var(--text-dim); }
.search-input:focus {
  border-color: var(--amber-dim);
  box-shadow: 0 0 0 2px rgba(245,166,35,.1);
}
.search-input:disabled { opacity: .5; cursor: not-allowed; }

.search-btn {
  background: var(--amber);
  color: #000;
  border: none;
  border-radius: var(--radius);
  font-family: var(--mono);
  font-weight: 500;
  font-size: 13px;
  letter-spacing: 1.5px;
  padding: 12px 24px;
  cursor: pointer;
  transition: background .15s, transform .1s;
  display: flex;
  align-items: center;
  white-space: nowrap;
}
.search-btn:hover:not(:disabled) { background: #ffc04d; }
.search-btn:active:not(:disabled) { transform: scale(.97); }
.search-btn:disabled { opacity: .4; cursor: not-allowed; }

/* ─── Button spinner ─────────────────────────────────────────────────────── */
.btn-spinner {
  display: inline-block;
  width: 14px; height: 14px;
  border: 2px solid rgba(0,0,0,.3);
  border-top-color: #000;
  border-radius: 50%;
  animation: spin .7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ─── Error banner ───────────────────────────────────────────────────────── */
.error-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(255,95,87,.08);
  border: 1px solid rgba(255,95,87,.35);
  border-radius: var(--radius);
  padding: 12px 16px;
  color: var(--red);
  font-size: 13px;
}
.error-icon { font-size: 16px; flex-shrink: 0; }
.error-dismiss {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--red);
  cursor: pointer;
  font-size: 14px;
  opacity: .7;
  flex-shrink: 0;
}
.error-dismiss:hover { opacity: 1; }

/* ─── Result card ────────────────────────────────────────────────────────── */
.result-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.result-header {
  padding: 20px 24px 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.result-topic-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.tag {
  font-size: 10px;
  letter-spacing: 2px;
  font-weight: 500;
  color: var(--amber);
  border: 1px solid var(--amber-dim);
  border-radius: 2px;
  padding: 2px 8px;
  flex-shrink: 0;
}
.result-topic {
  font-family: var(--display);
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  word-break: break-word;
}
.result-meta { display: flex; gap: 8px; }
.meta-chip {
  font-size: 11px;
  color: var(--text-dim);
  border: 1px solid var(--border);
  border-radius: 2px;
  padding: 2px 8px;
}

.divider { height: 1px; background: var(--border); margin: 20px 0 0; }

/* ─── Summary body ───────────────────────────────────────────────────────── */
.summary-body {
  display: flex;
  gap: 14px;
  padding: 24px;
}
.summary-icon { color: var(--amber); font-size: 10px; margin-top: 5px; flex-shrink: 0; }
.summary-text {
  font-size: 14.5px;
  line-height: 1.85;
  color: var(--text);
}

/* ─── Sources ────────────────────────────────────────────────────────────── */
.sources-section {
  border-top: 1px solid var(--border);
  padding: 16px 24px 20px;
  background: var(--surface2);
}
.sources-heading {
  font-size: 10px;
  letter-spacing: 2px;
  color: var(--text-dim);
  margin-bottom: 12px;
}
.sources-list { list-style: none; display: flex; flex-direction: column; gap: 8px; }
.source-item { display: flex; align-items: baseline; gap: 12px; }
.source-index { font-size: 11px; color: var(--text-dim); min-width: 22px; }
.source-link {
  color: var(--amber);
  text-decoration: none;
  font-size: 13px;
  word-break: break-all;
  transition: color .15s;
}
.source-link:hover { color: #ffc04d; text-decoration: underline; }
.source-arrow { font-size: 12px; margin-left: 3px; }

/* ─── Skeleton loader ────────────────────────────────────────────────────── */
.skeleton-card { padding: 24px; display: flex; flex-direction: column; gap: 14px; }
.skeleton-header { display: flex; gap: 14px; align-items: center; margin-bottom: 4px; }

.skel {
  background: linear-gradient(90deg, var(--surface2) 25%, var(--border) 50%, var(--surface2) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.6s ease-in-out infinite;
  border-radius: 3px;
}
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.skel-tag  { height: 20px; width: 72px; }
.skel-meta { height: 18px; width: 120px; }
.skel-line { height: 14px; width: 100%; }
.w80 { width: 80%; }
.w95 { width: 95%; }
.w70 { width: 70%; }
.w60 { width: 60%; }
.w75 { width: 75%; }

.skeleton-sources { display: flex; flex-direction: column; gap: 8px; margin-top: 6px; }
.skel-source { height: 12px; width: 90%; }

.skeleton-label {
  font-size: 11px;
  color: var(--text-dim);
  letter-spacing: 1px;
  margin-top: 4px;
  animation: pulse 1.8s ease-in-out infinite;
}
@keyframes pulse { 0%, 100% { opacity: .4; } 50% { opacity: 1; } }

/* ─── Empty state ────────────────────────────────────────────────────────── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  padding: 48px 0;
}
.empty-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 10px;
  opacity: .25;
}
.empty-dot {
  color: var(--amber);
  font-size: 16px;
  text-align: center;
  animation: blink 3s ease-in-out infinite;
}
@keyframes blink { 0%, 80%, 100% { opacity: .2; } 40% { opacity: 1; } }
.empty-label { font-size: 13px; color: var(--text-dim); }
kbd {
  border: 1px solid var(--border);
  border-radius: 3px;
  padding: 1px 6px;
  font-family: var(--mono);
  font-size: 12px;
  color: var(--amber);
}

/* ─── Footer ─────────────────────────────────────────────────────────────── */
.footer {
  margin-top: auto;
  font-size: 11px;
  color: var(--text-dim);
  display: flex;
  gap: 10px;
  justify-content: center;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}
.footer-sep { opacity: .4; }

/* ─── Transitions ────────────────────────────────────────────────────────── */
.fade-enter-active, .fade-leave-active { transition: opacity .25s ease; }
.fade-enter-from, .fade-leave-to       { opacity: 0; }

.slide-up-enter-active { transition: opacity .3s ease, transform .3s ease; }
.slide-up-leave-active { transition: opacity .2s ease; }
.slide-up-enter-from   { opacity: 0; transform: translateY(12px); }
.slide-up-leave-to     { opacity: 0; }

/* ─── Responsive ─────────────────────────────────────────────────────────── */
@media (max-width: 600px) {
  .container     { padding: 28px 16px 60px; }
  .search-row    { flex-direction: column; }
  .search-btn    { width: 100%; justify-content: center; }
  .header-right  { display: none; }
  .result-header { padding: 16px 16px 0; }
  .summary-body  { padding: 16px; }
  .sources-section { padding: 14px 16px 16px; }
}
</style>