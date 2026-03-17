import { useEffect, useRef, useState, useCallback } from 'react';
import api from '../../api';

// ── Helpers ────────────────────────────────────────────────────────────────

function tonalityColor(t) {
  return t === 'Positive' ? 'text-green-600' : t === 'Negative' ? 'text-red-500' : 'text-yellow-600';
}
function tonalityBg(t) {
  return t === 'Positive' ? 'bg-green-100 text-green-700' : t === 'Negative' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700';
}
function tonalityEmoji(t) {
  return t === 'Positive' ? '😊' : t === 'Negative' ? '😟' : '😐';
}
function trendIcon(trend) {
  return trend === 'Improving' ? '📈' : trend === 'Deteriorating' ? '📉' : '➡️';
}
function typeIcon(type) {
  return type === 'Chat' ? '💬' : type === 'Call' ? '📞' : '❓';
}
function scoreBar(score) {
  // score: -1.0 to +1.0 → 0% to 100%
  const pct = Math.round(((score + 1) / 2) * 100);
  const color = score > 0.2 ? 'bg-green-500' : score < -0.2 ? 'bg-red-500' : 'bg-yellow-400';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-500 w-10 text-right">{score > 0 ? '+' : ''}{score.toFixed(2)}</span>
    </div>
  );
}

// ── Interaction Detail Modal ───────────────────────────────────────────────

function InteractionDetailModal({ customerId, customerName, onClose }) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab,     setTab]     = useState('chat'); // 'chat' | 'calls'
  const [openSession, setOpenSession] = useState(null); // expanded chat session id

  useEffect(() => {
    api.get(`/officer/customer/${customerId}/interactions`)
      .then(r => {
        setData(r.data);
        // Default to 'calls' tab if customer has no chat but has calls
        if (r.data.chat_sessions.length === 0 && r.data.calls.length > 0) setTab('calls');
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [customerId]);

  // Close on backdrop click
  const handleBackdrop = (e) => { if (e.target === e.currentTarget) onClose(); };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4"
      onClick={handleBackdrop}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div>
            <h2 className="text-lg font-bold text-gray-800">{customerName}</h2>
            <p className="text-xs text-gray-400">{customerId} · Full Interaction History</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none font-light"
          >
            ✕
          </button>
        </div>

        {/* Tab bar */}
        <div className="flex bg-gray-50 border-b border-gray-100 px-6 gap-4">
          <button
            onClick={() => setTab('chat')}
            className={`py-3 text-sm font-semibold border-b-2 transition-colors ${
              tab === 'chat'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            💬 Chat Sessions {data && `(${data.chat_sessions.length})`}
          </button>
          <button
            onClick={() => setTab('calls')}
            className={`py-3 text-sm font-semibold border-b-2 transition-colors ${
              tab === 'calls'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            📞 Call Recordings {data && `(${data.calls.length})`}
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading && (
            <div className="flex justify-center items-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-4 border-blue-500 border-t-transparent" />
            </div>
          )}

          {/* ── Chat tab ── */}
          {!loading && tab === 'chat' && (
            <div className="space-y-3">
              {data.chat_sessions.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-8">No chat sessions found for this customer.</p>
              ) : (
                data.chat_sessions.map(session => (
                  <div key={session.session_id} className="border border-gray-200 rounded-xl overflow-hidden">
                    {/* Session header — clickable to expand */}
                    <button
                      className="w-full text-left px-4 py-3 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
                      onClick={() => setOpenSession(openSession === session.session_id ? null : session.session_id)}
                    >
                      <div>
                        <p className="text-sm font-semibold text-gray-700">📋 {session.session_title}</p>
                        <p className="text-xs text-gray-400">
                          Started {session.created_at?.slice(0, 16)} · {session.messages.filter(m => m.role === 'user').length} user message(s)
                        </p>
                      </div>
                      <span className="text-gray-400 text-sm">{openSession === session.session_id ? '▲' : '▼'}</span>
                    </button>

                    {/* Chat bubble thread */}
                    {openSession === session.session_id && (
                      <div className="px-4 py-3 space-y-2 bg-white max-h-72 overflow-y-auto">
                        {session.messages.map((msg, idx) => (
                          <div
                            key={idx}
                            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                          >
                            <div
                              className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm leading-relaxed ${
                                msg.role === 'user'
                                  ? 'bg-blue-600 text-white rounded-br-none'
                                  : msg.role === 'assistant'
                                  ? 'bg-gray-100 text-gray-800 rounded-bl-none'
                                  : 'bg-yellow-50 text-gray-500 text-xs italic w-full text-center rounded-xl'
                              }`}
                            >
                              {msg.role === 'system' && <span className="font-medium">System: </span>}
                              {msg.message_text}
                              <p className={`text-[10px] mt-1 ${msg.role === 'user' ? 'text-blue-200' : 'text-gray-400'}`}>
                                {msg.timestamp?.slice(11, 16)}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {/* ── Calls tab ── */}
          {!loading && tab === 'calls' && (
            <div className="space-y-3">
              {data.calls.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-8">No call recordings analyzed for this customer.</p>
              ) : (
                data.calls.map(call => (
                  <div key={call.interaction_id} className="border border-gray-200 rounded-xl overflow-hidden">
                    {/* Call meta header */}
                    <div className={`px-4 py-3 flex items-center justify-between ${tonalityBg(call.tonality_score)}`}>
                      <div>
                        <p className="text-sm font-semibold">
                          {tonalityEmoji(call.tonality_score)} {call.tonality_score} · Score: {call.sentiment_score > 0 ? '+' : ''}{call.sentiment_score?.toFixed(2)}
                        </p>
                        <p className="text-xs opacity-75">{call.interaction_time?.slice(0, 16)}</p>
                      </div>
                    </div>
                    {/* Summary */}
                    {call.interaction_summary && (
                      <div className="px-4 py-2 bg-white border-b border-gray-100">
                        <p className="text-xs text-gray-500 font-medium mb-0.5">AI Summary</p>
                        <p className="text-sm text-gray-700">{call.interaction_summary}</p>
                      </div>
                    )}
                    {/* Full transcript */}
                    {call.conversation_text && (
                      <div className="px-4 py-3 bg-gray-50">
                        <p className="text-xs text-gray-500 font-medium mb-1">📝 Full Transcript</p>
                        <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                          {call.conversation_text}
                        </p>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Customer Sentiment Card ────────────────────────────────────────────────

function CustomerSentimentCard({ data }) {
  const [expanded,    setExpanded]    = useState(false);
  const [showModal,   setShowModal]   = useState(false);

  // Use last-3 sentiment for the card header — reflects current risk
  const headerTonality = data.last3_tonality || data.dominant_tonality;
  const headerTrend    = data.last3_trend    || data.sentiment_trend;
  const headerScore    = data.last3_sentiment ?? data.average_sentiment;

  return (
    <div className="bg-white rounded-xl shadow border border-gray-100 overflow-hidden">
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full text-left px-5 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-2xl">{tonalityEmoji(headerTonality)}</span>
          <div className="min-w-0">
            <p className="font-semibold text-gray-800 text-sm truncate">{data.customer_name}</p>
            <p className="text-xs text-gray-400">
              {data.customer_id} · {data.total_interactions} total interactions
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4 flex-shrink-0 ml-4">
          {/* Last-3 badge */}
          <div className="text-right">
            <span className={`text-xs px-2 py-1 rounded-full font-medium ${tonalityBg(headerTonality)}`}>
              {headerTonality}
            </span>
            <p className="text-[10px] text-gray-400 mt-0.5">last 3</p>
          </div>
          <span className="text-sm" title={`Trend (last 3): ${headerTrend}`}>{trendIcon(headerTrend)}</span>
          <span className="text-gray-400 text-sm">{expanded ? '▲' : '▼'}</span>
        </div>
      </button>

      {/* Score bar — last-3 score */}
      <div className="px-5 pb-1">
        <p className="text-[10px] text-gray-400 mb-0.5">Last 3 interactions sentiment</p>
        {scoreBar(headerScore)}
      </div>

      {/* All-time score — smaller, secondary */}
      <div className="px-5 pb-3">
        <p className="text-[10px] text-gray-400 mb-0.5">All-time average</p>
        {scoreBar(data.average_sentiment)}
      </div>

      {/* Expanded: last 3 interactions detail */}
      {expanded && (
        <div className="border-t border-gray-100 px-5 py-3 space-y-2 bg-gray-50">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Last 3 Interactions
            </p>
            <button
              onClick={() => setShowModal(true)}
              className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-blue-50 transition-colors"
            >
              🔍 View Full History
            </button>
          </div>
          {data.recent_interactions.length === 0 && (
            <p className="text-xs text-gray-400">No interaction history (Chat or Call).</p>
          )}
          {data.recent_interactions.map((i, idx) => (
            <div key={idx} className="bg-white rounded-lg px-4 py-2.5 border border-gray-100 text-xs">
              <div className="flex items-center justify-between mb-1">
                <span className="font-medium text-gray-700">
                  {typeIcon(i.interaction_type)} {i.interaction_type} · {i.interaction_time?.slice(0, 16)}
                </span>
                <span className={`px-2 py-0.5 rounded-full font-medium ${tonalityBg(i.tonality_score)}`}>
                  {tonalityEmoji(i.tonality_score)} {i.tonality_score}
                </span>
              </div>
              <p className="text-gray-500 leading-relaxed">{i.interaction_summary}</p>
              {scoreBar(i.sentiment_score)}
            </div>
          ))}
        </div>
      )}

      {/* Interaction detail modal */}
      {showModal && (
        <InteractionDetailModal
          customerId={data.customer_id}
          customerName={data.customer_name}
          onClose={() => setShowModal(false)}
        />
      )}
    </div>
  );
}

// ── Voice Call Analyzer Card ───────────────────────────────────────────────
// Supports two modes: file upload OR live mic recording

function CallAnalyzerCard({ customers, onAnalyzed }) {
  const fileRef            = useRef(null);
  const mediaRecorderRef   = useRef(null);
  const chunksRef          = useRef([]);
  const timerRef           = useRef(null);

  const [tab,        setTab]        = useState('upload'); // 'upload' | 'record'
  const [customerId, setCustomerId] = useState('');
  const [file,       setFile]       = useState(null);
  const [loading,    setLoading]    = useState(false);
  const [result,     setResult]     = useState(null);
  const [error,      setError]      = useState('');

  // Recording state
  const [recording,   setRecording]   = useState(false);
  const [recordedBlob, setRecordedBlob] = useState(null);
  const [recordedUrl,  setRecordedUrl]  = useState('');
  const [recSeconds,   setRecSeconds]   = useState(0);
  const [micSupported, setMicSupported] = useState(true);

  // Reset results when tab changes
  const switchTab = (t) => { setTab(t); setResult(null); setError(''); setFile(null); setRecordedBlob(null); setRecordedUrl(''); setRecSeconds(0); };

  // ── Recording helpers ──
  const startRecording = useCallback(async () => {
    setError('');
    setRecordedBlob(null);
    setRecordedUrl('');
    setRecSeconds(0);
    chunksRef.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mr;
      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.onstop = () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        const url  = URL.createObjectURL(blob);
        setRecordedBlob(blob);
        setRecordedUrl(url);
      };
      mr.start(250);
      setRecording(true);
      timerRef.current = setInterval(() => setRecSeconds(s => s + 1), 1000);
    } catch (err) {
      if (err.name === 'NotAllowedError') {
        setError('Microphone access denied. Please allow microphone access in your browser.');
      } else {
        setMicSupported(false);
        setError('Microphone not available on this device/browser.');
      }
    }
  }, []);

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop();
    setRecording(false);
    clearInterval(timerRef.current);
  }, []);

  const fmtTime = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

  // ── Submit handler — works for both upload and record tabs ──
  const handleSubmit = async (e) => {
    e.preventDefault();
    const audioSource = tab === 'upload' ? file : recordedBlob;
    if (!customerId || !audioSource) {
      setError(tab === 'upload'
        ? 'Please select a customer and upload an audio file.'
        : 'Please select a customer and record a call first.');
      return;
    }
    setError('');
    setResult(null);
    setLoading(true);

    const formData = new FormData();
    formData.append('customer_id', customerId);
    if (tab === 'upload') {
      formData.append('audio_file', file);
    } else {
      // Send recorded blob as a .webm file
      formData.append('audio_file', recordedBlob, 'recording.webm');
    }

    try {
      const r = await api.post('/officer/sentiment/analyze-call', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(r.data);
      if (onAnalyzed) onAnalyzed(); // 🔄 refresh customer sentiment list
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to analyze call. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow p-6 border border-gray-100">
      <h2 className="text-lg font-bold text-gray-800 mb-1 flex items-center gap-2">
        🎙️ Call Recording Analyzer
      </h2>
      <p className="text-sm text-gray-500 mb-4">
        Transcribed locally with Whisper · Sentiment analysis applied automatically
      </p>

      {/* Tab switcher */}
      <div className="flex bg-gray-100 rounded-xl p-1 mb-5 gap-1">
        <button
          onClick={() => switchTab('upload')}
          className={`flex-1 py-2 text-sm font-semibold rounded-lg transition-colors ${tab === 'upload' ? 'bg-white shadow text-blue-600' : 'text-gray-500 hover:text-gray-700'}`}
        >
          📁 Upload File
        </button>
        <button
          onClick={() => switchTab('record')}
          className={`flex-1 py-2 text-sm font-semibold rounded-lg transition-colors ${tab === 'record' ? 'bg-white shadow text-red-600' : 'text-gray-500 hover:text-gray-700'}`}
        >
          🎤 Record Live
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Customer selector — shared */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Select Customer</label>
          <select
            value={customerId}
            onChange={e => setCustomerId(e.target.value)}
            className="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">— Choose a customer —</option>
            {customers.map(c => (
              <option key={c.customer_id} value={c.customer_id}>
                {c.customer_name} ({c.customer_id})
              </option>
            ))}
          </select>
        </div>

        {/* ── UPLOAD tab ── */}
        {tab === 'upload' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Audio File</label>
            <div
              onClick={() => fileRef.current?.click()}
              className="border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-xl p-6 text-center cursor-pointer transition-colors"
            >
              {file ? (
                <div>
                  <p className="text-sm font-medium text-blue-600">🎵 {file.name}</p>
                  <p className="text-xs text-gray-400 mt-1">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
              ) : (
                <div>
                  <p className="text-3xl mb-2">📂</p>
                  <p className="text-sm text-gray-500">Click to upload or drag & drop</p>
                  <p className="text-xs text-gray-400 mt-1">MP3, WAV, M4A, OGG, FLAC</p>
                </div>
              )}
            </div>
            <input
              ref={fileRef}
              type="file"
              accept=".mp3,.wav,.m4a,.ogg,.flac"
              className="hidden"
              onChange={e => setFile(e.target.files[0] || null)}
            />
          </div>
        )}

        {/* ── RECORD tab ── */}
        {tab === 'record' && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Microphone Recording</label>

            {!micSupported ? (
              <div className="bg-yellow-50 border border-yellow-200 text-yellow-700 text-sm rounded-xl px-4 py-3">
                ⚠️ Your browser does not support microphone recording. Please use Chrome or Edge and try uploading a file instead.
              </div>
            ) : (
              <div className="border-2 border-dashed border-gray-300 rounded-xl p-5 text-center">
                {/* Not yet recorded */}
                {!recording && !recordedBlob && (
                  <div>
                    <p className="text-4xl mb-3">🎤</p>
                    <p className="text-sm text-gray-500 mb-4">Click the button below to start recording your call</p>
                    <button
                      type="button"
                      onClick={startRecording}
                      className="bg-red-500 hover:bg-red-600 text-white font-semibold px-6 py-2.5 rounded-xl text-sm transition-colors"
                    >
                      ⏺ Start Recording
                    </button>
                  </div>
                )}

                {/* Currently recording */}
                {recording && (
                  <div>
                    <div className="flex items-center justify-center gap-3 mb-3">
                      <span className="animate-pulse text-red-500 text-2xl">⏺</span>
                      <span className="font-mono text-xl font-bold text-red-600">{fmtTime(recSeconds)}</span>
                    </div>
                    <p className="text-sm text-gray-500 mb-4">Recording in progress…</p>
                    <button
                      type="button"
                      onClick={stopRecording}
                      className="bg-gray-700 hover:bg-gray-800 text-white font-semibold px-6 py-2.5 rounded-xl text-sm transition-colors"
                    >
                      ⏹ Stop Recording
                    </button>
                  </div>
                )}

                {/* Recording done — show playback + re-record option */}
                {!recording && recordedBlob && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-center gap-2 text-green-600">
                      <span className="text-xl">✅</span>
                      <span className="text-sm font-semibold">Recorded · {fmtTime(recSeconds)}</span>
                    </div>
                    <audio src={recordedUrl} controls className="w-full rounded-lg" />
                    <button
                      type="button"
                      onClick={startRecording}
                      className="text-xs text-gray-400 hover:text-red-500 underline"
                    >
                      🔄 Re-record
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
            ⚠️ {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading || recording}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white font-semibold py-3 rounded-xl text-sm transition-colors"
        >
          {loading ? '⏳ Transcribing & Analyzing…' : '🔍 Analyze Call'}
        </button>
      </form>

      {/* Result */}
      {result && (
        <div className="mt-6 space-y-4">
          <div className={`rounded-xl p-4 ${tonalityBg(result.tonality)}`}>
            <div className="flex items-center justify-between mb-2">
              <span className="font-bold text-base">
                {tonalityEmoji(result.tonality)} {result.tonality} Sentiment
              </span>
              <span className="text-sm font-mono">Score: {result.sentiment_score > 0 ? '+' : ''}{result.sentiment_score.toFixed(2)}</span>
            </div>
            <p className="text-sm">{result.interaction_summary}</p>
            {scoreBar(result.sentiment_score)}
          </div>

          <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">📝 Transcript</p>
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{result.transcript}</p>
          </div>

          <p className="text-xs text-gray-400 text-right">
            Saved to interaction history · Customer: {result.customer_name}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function SentimentAnalysis() {
  const [data,       setData]       = useState(null);
  const [loading,    setLoading]    = useState(true);   // initial page load only
  const [refreshing, setRefreshing] = useState(false);  // silent background refresh
  const [error,      setError]      = useState('');
  const [search,     setSearch]     = useState('');
  const [filter,     setFilter]     = useState('Negative'); // Default: show at-risk customers first

  // Initial load — shows full-page spinner
  useEffect(() => {
    api.get('/officer/sentiment')
      .then(r => setData(r.data))
      .catch(() => setError('Failed to load sentiment data.'))
      .finally(() => setLoading(false));
  }, []);

  // Background refresh after call analysis — NO full-page spinner
  const fetchSentiment = () => {
    setRefreshing(true);
    api.get('/officer/sentiment')
      .then(r => setData(r.data))
      .catch(() => {}) // silent — don't wipe the screen
      .finally(() => setRefreshing(false));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent" />
      </div>
    );
  }
  if (error) return <div className="text-red-500 p-6">{error}</div>;

  const ps = data.portfolio_sentiment;

  // Filter + search customers
  const filtered = (data.customers || []).filter(c => {
    const matchSearch = c.customer_name.toLowerCase().includes(search.toLowerCase()) ||
                        c.customer_id.toLowerCase().includes(search.toLowerCase());
    const matchFilter = filter === 'All' || (c.last3_tonality || c.dominant_tonality) === filter;
    return matchSearch && matchFilter;
  });

  return (
    <div className="space-y-6">

      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-800">🧠 Sentiment Analysis</h1>
        <p className="text-sm text-gray-500 mt-1">
          Based on <span className="font-medium text-blue-600">💬 Live Chat</span> and <span className="font-medium text-blue-600">📞 Uploaded Calls</span> only · Real data, no Email/SMS/WhatsApp
        </p>
      </div>

      {/* ── Portfolio Summary Bar ── */}
      <div className="bg-gradient-to-r from-slate-800 to-slate-700 rounded-2xl p-6 text-white shadow">
        <p className="text-sm text-slate-300 mb-4 font-medium">
          Portfolio Sentiment Overview · {ps.total_interactions} interactions (Chat + Call) · Sorted by highest risk first
        </p>
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div className="bg-green-500 bg-opacity-20 rounded-xl p-4 text-center">
            <p className="text-3xl font-bold text-green-300">{ps.positive_pct}%</p>
            <p className="text-sm text-green-200 mt-1">😊 Positive</p>
            <p className="text-xs text-green-300">{ps.positive} interactions</p>
          </div>
          <div className="bg-yellow-400 bg-opacity-20 rounded-xl p-4 text-center">
            <p className="text-3xl font-bold text-yellow-300">{ps.neutral_pct}%</p>
            <p className="text-sm text-yellow-200 mt-1">😐 Neutral</p>
            <p className="text-xs text-yellow-300">{ps.neutral} interactions</p>
          </div>
          <div className="bg-red-500 bg-opacity-20 rounded-xl p-4 text-center">
            <p className="text-3xl font-bold text-red-300">{ps.negative_pct}%</p>
            <p className="text-sm text-red-200 mt-1">😟 Negative</p>
            <p className="text-xs text-red-300">{ps.negative} interactions</p>
          </div>
        </div>
        {/* Visual bar */}
        <div className="flex h-3 rounded-full overflow-hidden gap-0.5">
          <div className="bg-green-500 transition-all" style={{ width: `${ps.positive_pct}%` }} />
          <div className="bg-yellow-400 transition-all" style={{ width: `${ps.neutral_pct}%` }} />
          <div className="bg-red-500 transition-all"   style={{ width: `${ps.negative_pct}%` }} />
        </div>
      </div>

      {/* ── Two-column layout: Customer Sentiment | Call Analyzer ── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">

        {/* Card 1 – Customer Sentiment List */}
        <div className="space-y-4">
          <div className="bg-white rounded-2xl shadow p-5 border border-gray-100">
            <h2 className="text-lg font-bold text-gray-800 mb-3 flex items-center gap-2">
              👥 Customer Sentiment
              {refreshing && (
                <span className="ml-2 flex items-center gap-1 text-xs text-blue-500 font-normal">
                  <span className="inline-block w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                  Updating…
                </span>
              )}
            </h2>
            {/* Search + filter */}
            <div className="flex gap-2 mb-4">
              <input
                type="text"
                placeholder="Search by name or ID…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="flex-1 border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <select
                value={filter}
                onChange={e => setFilter(e.target.value)}
                className="border border-gray-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="All">All</option>
                <option value="Positive">😊 Positive</option>
                <option value="Neutral">😐 Neutral</option>
                <option value="Negative">😟 Negative</option>
              </select>
            </div>
            <p className="text-xs text-gray-400 mb-3">
              {filtered.length} customer{filtered.length !== 1 ? 's' : ''} · Sorted by lowest sentiment first (highest risk)
            </p>
          </div>

          <div className="space-y-3">
            {filtered.length === 0 ? (
              <div className="bg-white rounded-2xl shadow p-8 text-center text-gray-400 text-sm">
                No customers match your filter.
              </div>
            ) : (
              filtered.map(c => <CustomerSentimentCard key={c.customer_id} data={c} />)
            )}
          </div>
        </div>

        {/* Card 2 – Voice Call Analyzer */}
        <div>
          <CallAnalyzerCard customers={data.customers || []} onAnalyzed={fetchSentiment} />
        </div>

      </div>
    </div>
  );
}
