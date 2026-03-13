import { useEffect, useState } from 'react';
import api from '../../api';

const CHANNELS  = ['WhatsApp', 'SMS', 'Email', 'Voice Call'];
const LANGUAGES = ['English', 'Hindi', 'Tamil', 'Telugu', 'Kannada', 'Malayalam', 'Bengali', 'Marathi', 'Gujarati', 'Punjabi'];

const channelIcons = {
  WhatsApp:    '💬',
  SMS:         '📱',
  Email:       '📧',
  'Voice Call':'📞',
};

export default function Preferences() {
  const [pref,    setPref]    = useState({ preferred_channel: 'Email', preferred_language: 'English' });
  const [loading, setLoading] = useState(true);
  const [saving,  setSaving]  = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    api.get('/preferences/')
      .then(r => setPref(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMessage('');
    try {
      await api.post('/preferences/', {
        preferred_channel:  pref.preferred_channel,
        preferred_language: pref.preferred_language,
      });
      setMessage('✅ Preferences saved successfully!');
    } catch (err) {
      setMessage('❌ Failed to save preferences.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-800">📡 Preferred Communication Channel</h1>
      <p className="text-gray-500 text-sm">
        Choose how you'd like the bank to contact you for EMI reminders, grace period updates, and other communications.
      </p>

      {/* Channel Selection */}
      <div className="bg-white rounded-2xl shadow p-6">
        <h2 className="text-base font-semibold text-gray-700 mb-4">Communication Channel</h2>
        <div className="grid grid-cols-2 gap-3">
          {CHANNELS.map(ch => (
            <button
              key={ch}
              onClick={() => setPref(p => ({ ...p, preferred_channel: ch }))}
              className={`flex items-center gap-3 p-4 rounded-xl border-2 transition-all text-left ${
                pref.preferred_channel === ch
                  ? 'border-blue-500 bg-blue-50 text-blue-700'
                  : 'border-gray-200 hover:border-gray-300 text-gray-600'
              }`}
            >
              <span className="text-2xl">{channelIcons[ch]}</span>
              <span className="font-medium text-sm">{ch}</span>
              {pref.preferred_channel === ch && (
                <span className="ml-auto text-blue-500">✓</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Language Selection */}
      <div className="bg-white rounded-2xl shadow p-6">
        <h2 className="text-base font-semibold text-gray-700 mb-4">Preferred Language</h2>
        <div className="grid grid-cols-3 gap-2">
          {LANGUAGES.map(lang => (
            <button
              key={lang}
              onClick={() => setPref(p => ({ ...p, preferred_language: lang }))}
              className={`py-2.5 px-3 rounded-xl border-2 text-sm font-medium transition-all ${
                pref.preferred_language === lang
                  ? 'border-blue-500 bg-blue-50 text-blue-700'
                  : 'border-gray-200 hover:border-gray-300 text-gray-600'
              }`}
            >
              {lang}
            </button>
          ))}
        </div>
      </div>

      {/* Current Setting */}
      <div className="bg-blue-50 rounded-2xl p-4 flex items-center gap-4">
        <span className="text-3xl">{channelIcons[pref.preferred_channel]}</span>
        <div>
          <p className="text-sm text-gray-500">Current preference</p>
          <p className="font-semibold text-gray-800">
            {pref.preferred_channel} • {pref.preferred_language}
          </p>
        </div>
      </div>

      {message && (
        <div className={`px-4 py-3 rounded-xl text-sm font-medium ${
          message.startsWith('✅')
            ? 'bg-green-50 text-green-700 border border-green-200'
            : 'bg-red-50 text-red-700 border border-red-200'
        }`}>
          {message}
        </div>
      )}

      <button
        onClick={handleSave}
        disabled={saving}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-semibold py-3 rounded-xl transition-colors"
      >
        {saving ? 'Saving...' : 'Save Preferences'}
      </button>
    </div>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent"></div>
    </div>
  );
}