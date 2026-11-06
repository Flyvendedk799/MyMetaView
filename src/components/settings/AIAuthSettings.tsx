import React, { useState, useEffect } from 'react'
import Card from '../ui/Card'
import Button from '../ui/Button'
import {
  getAiAuthStatus,
  startClaudeLogin,
  completeClaudeLogin,
  disconnectClaude,
  startAntigravityLogin,
  completeAntigravityLogin,
  disconnectAntigravity,
  setAntigravityProject,
  saveAiKey,
  deleteAiKey
} from '../../api/client'
import type { AiAuthFullStatus } from '../../api/types'

interface AIAuthSettingsProps {
  scope: 'org' | 'user'
  orgId?: number
}

export default function AIAuthSettings({ scope, orgId }: AIAuthSettingsProps) {
  const [activeTab, setActiveTab] = useState<'claude' | 'antigravity' | 'keys'>('claude')
  const [status, setStatus] = useState<AiAuthFullStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Auth flow states
  const [claudeAuthUrl, setClaudeAuthUrl] = useState<string | null>(null)
  const [claudeStateValue, setClaudeStateValue] = useState<string | null>(null)
  const [claudeVerifierValue, setClaudeVerifierValue] = useState<string | null>(null)
  const [claudeCodeState, setClaudeCodeState] = useState('')
  const [antigravityAuthUrl, setAntigravityAuthUrl] = useState<string | null>(null)
  const [antigravityStateValue, setAntigravityStateValue] = useState<string | null>(null)
  const [antigravityVerifierValue, setAntigravityVerifierValue] = useState<string | null>(null)
  const [antigravityCodeState, setAntigravityCodeState] = useState('')
  const [projectIdInput, setProjectIdInput] = useState('')

  // Key states
  const [keys, setKeys] = useState({
    anthropic: '',
    openai: '',
    gemini: ''
  })
  const [savingKey, setSavingKey] = useState<string | null>(null)

  const loadStatus = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await getAiAuthStatus(scope, orgId)
      setStatus(data)
      if (data.antigravity.project_id) {
        setProjectIdInput(data.antigravity.project_id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load AI credentials')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadStatus()
  }, [scope, orgId])

  // Claude actions
  const handleStartClaude = async () => {
    try {
      setError(null)
      const res = await startClaudeLogin(scope, orgId)
      setClaudeAuthUrl(res.url)
      setClaudeStateValue(res.state)
      setClaudeVerifierValue(res.verifier)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start Claude login')
    }
  }

  // Helper to parse pasted redirect URL or code#state
  const parseCodeState = (raw: string, fallbackState?: string | null) => {
    const trimmed = raw.trim();
    if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
      try {
        const url = new URL(trimmed);
        const code = url.searchParams.get('code');
        const state = url.searchParams.get('state');
        if (code && state) return { code, state };
      } catch (e) {
        // ignore
      }
    }
    const parts = trimmed.split('#');
    return { code: parts[0], state: parts[1] || fallbackState };
  };

  const handleCompleteClaude = async () => {
    try {
      setError(null)
      const { code, state } = parseCodeState(claudeCodeState, claudeStateValue);
      if (!code || !state || !claudeVerifierValue) throw new Error('Invalid format. Please paste the full redirect URL or code#state')
      await completeClaudeLogin(code, state, claudeVerifierValue, scope, orgId)
      setClaudeAuthUrl(null)
      setClaudeCodeState('')
      await loadStatus()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to complete Claude login')
    }
  }

  const handleDisconnectClaude = async () => {
    try {
      setError(null)
      await disconnectClaude(scope, orgId)
      await loadStatus()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect Claude')
    }
  }

  // Antigravity actions
  const handleStartAntigravity = async () => {
    try {
      setError(null)
      const res = await startAntigravityLogin(scope, orgId)
      setAntigravityAuthUrl(res.url)
      setAntigravityStateValue(res.state)
      setAntigravityVerifierValue(res.verifier)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start Antigravity login')
    }
  }

  const handleCompleteAntigravity = async () => {
    try {
      setError(null)
      const { code, state } = parseCodeState(antigravityCodeState, antigravityStateValue);
      if (!code || !state || !antigravityVerifierValue) throw new Error('Invalid format. Please paste the full redirect URL or code#state')
      await completeAntigravityLogin(code, state, antigravityVerifierValue, scope, orgId)
      setAntigravityAuthUrl(null)
      setAntigravityCodeState('')
      await loadStatus()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to complete Antigravity login')
    }
  }

  const handleDisconnectAntigravity = async () => {
    try {
      setError(null)
      await disconnectAntigravity(scope, orgId)
      await loadStatus()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to disconnect Antigravity')
    }
  }

  const handleUpdateProject = async () => {
    try {
      setError(null)
      await setAntigravityProject(projectIdInput || null, scope, orgId)
      await loadStatus()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update project ID')
    }
  }

  // Key actions
  const handleSaveKey = async (provider: 'anthropic' | 'openai' | 'gemini') => {
    try {
      setError(null)
      setSavingKey(provider)
      if (keys[provider]) {
        await saveAiKey(provider, keys[provider], scope, orgId)
        setKeys(prev => ({ ...prev, [provider]: '' }))
        await loadStatus()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to save ${provider} key`)
    } finally {
      setSavingKey(null)
    }
  }

  const handleDeleteKey = async (provider: 'anthropic' | 'openai' | 'gemini') => {
    try {
      setError(null)
      setSavingKey(provider)
      await deleteAiKey(provider, scope, orgId)
      await loadStatus()
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to delete ${provider} key`)
    } finally {
      setSavingKey(null)
    }
  }

  if (loading) {
    return <div className="text-secondary-500 py-4">Loading AI credentials...</div>
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-error-50 border border-error-200 text-error-800 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      <div className="flex space-x-1 border-b border-secondary-200">
        <button
          onClick={() => setActiveTab('claude')}
          className={`px-4 py-2 border-b-2 font-medium text-sm ${
            activeTab === 'claude'
              ? 'border-primary-500 text-primary-600'
              : 'border-transparent text-secondary-500 hover:text-secondary-700 hover:border-secondary-300'
          }`}
        >
          Claude Subscription
        </button>
        <button
          onClick={() => setActiveTab('antigravity')}
          className={`px-4 py-2 border-b-2 font-medium text-sm ${
            activeTab === 'antigravity'
              ? 'border-primary-500 text-primary-600'
              : 'border-transparent text-secondary-500 hover:text-secondary-700 hover:border-secondary-300'
          }`}
        >
          Google AI (Antigravity)
        </button>
        <button
          onClick={() => setActiveTab('keys')}
          className={`px-4 py-2 border-b-2 font-medium text-sm ${
            activeTab === 'keys'
              ? 'border-primary-500 text-primary-600'
              : 'border-transparent text-secondary-500 hover:text-secondary-700 hover:border-secondary-300'
          }`}
        >
          API Keys
        </button>
      </div>

      <div className="pt-4">
        {activeTab === 'claude' && (
          <div className="space-y-4">
            <h3 className="text-lg font-medium text-secondary-900">Claude Integration</h3>
            <p className="text-sm text-secondary-600">
              Connect your Anthropic Claude account to use your own subscription.
            </p>
            
            {status?.claude.connected ? (
              <div className="bg-success-50 border border-success-200 rounded-lg p-4">
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="font-medium text-success-800">Connected to Claude</h4>
                    <p className="text-sm text-success-700 mt-1">
                      Plan: {status.claude.plan || 'Unknown'}
                    </p>
                    {status.claude.expires_at && (
                      <p className="text-xs text-success-600 mt-1">
                        Expires: {new Date(status.claude.expires_at * 1000).toLocaleString()}
                      </p>
                    )}
                  </div>
                  <Button variant="secondary" onClick={handleDisconnectClaude}>
                    Disconnect
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {!claudeAuthUrl ? (
                  <Button onClick={handleStartClaude}>Connect Claude Account</Button>
                ) : (
                  <div className="space-y-4">
                    <p className="text-sm text-secondary-700">
                      1. Click the link below to authorize with Claude:
                      <br />
                      <a href={claudeAuthUrl} target="_blank" rel="noreferrer" className="text-primary-600 hover:underline break-all mt-2 block">
                        {claudeAuthUrl}
                      </a>
                    </p>
                    <div className="space-y-2">
                      <label className="block text-sm font-medium text-secondary-700">
                        2. Paste the code or redirect URL here:
                      </label>
                      <input
                        type="text"
                        className="w-full px-3 py-2 border border-secondary-300 rounded-md shadow-sm focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                        value={claudeCodeState}
                        onChange={(e) => setClaudeCodeState(e.target.value)}
                        placeholder="e.g. 4/xxx... or https://..."
                      />
                    </div>
                    <div className="flex space-x-3">
                      <Button onClick={handleCompleteClaude} disabled={!claudeCodeState}>
                        Complete Login
                      </Button>
                      <Button variant="secondary" onClick={() => setClaudeAuthUrl(null)}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === 'antigravity' && (
          <div className="space-y-4">
            <h3 className="text-lg font-medium text-secondary-900">Google AI (Antigravity)</h3>
            <p className="text-sm text-secondary-600">
              Connect your Google account to use Gemini models via Antigravity.
            </p>
            
            {status?.antigravity.connected ? (
              <div className="space-y-4">
                <div className="bg-success-50 border border-success-200 rounded-lg p-4">
                  <div className="flex justify-between items-start">
                    <div>
                      <h4 className="font-medium text-success-800">Connected</h4>
                      <p className="text-sm text-success-700 mt-1">
                        Email: {status.antigravity.email || 'Unknown'}
                      </p>
                      {status.antigravity.expires_at && (
                        <p className="text-xs text-success-600 mt-1">
                          Expires: {new Date(status.antigravity.expires_at * 1000).toLocaleString()}
                        </p>
                      )}
                    </div>
                    <Button variant="secondary" onClick={handleDisconnectAntigravity}>
                      Disconnect
                    </Button>
                  </div>
                </div>
                
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-secondary-700">
                    GCP Project ID (optional)
                  </label>
                  <div className="flex space-x-2">
                    <input
                      type="text"
                      className="flex-1 px-3 py-2 border border-secondary-300 rounded-md shadow-sm focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                      value={projectIdInput}
                      onChange={(e) => setProjectIdInput(e.target.value)}
                      placeholder="my-gcp-project-123"
                    />
                    <Button variant="secondary" onClick={handleUpdateProject}>
                      Save Project
                    </Button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {!antigravityAuthUrl ? (
                  <Button onClick={handleStartAntigravity}>Connect Google Account</Button>
                ) : (
                  <div className="space-y-4">
                    <p className="text-sm text-secondary-700">
                      1. Click the link below to authorize with Google:
                      <br />
                      <a href={antigravityAuthUrl} target="_blank" rel="noreferrer" className="text-primary-600 hover:underline break-all mt-2 block">
                        {antigravityAuthUrl}
                      </a>
                    </p>
                    <div className="space-y-2">
                      <label className="block text-sm font-medium text-secondary-700">
                        2. Paste the code or redirect URL here:
                      </label>
                      <input
                        type="text"
                        className="w-full px-3 py-2 border border-secondary-300 rounded-md shadow-sm focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                        value={antigravityCodeState}
                        onChange={(e) => setAntigravityCodeState(e.target.value)}
                        placeholder="e.g. 4/xxx... or https://..."
                      />
                    </div>
                    <div className="flex space-x-3">
                      <Button onClick={handleCompleteAntigravity} disabled={!antigravityCodeState}>
                        Complete Login
                      </Button>
                      <Button variant="secondary" onClick={() => setAntigravityAuthUrl(null)}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === 'keys' && (
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-medium text-secondary-900">API Keys</h3>
              <p className="text-sm text-secondary-600">
                Provide your own API keys as a fallback or primary method.
              </p>
            </div>

            {(['anthropic', 'openai', 'gemini'] as const).map(provider => (
              <div key={provider} className="space-y-2">
                <label className="block text-sm font-medium text-secondary-700 capitalize">
                  {provider} Key
                </label>
                <div className="flex space-x-2">
                  <input
                    type="password"
                    className="flex-1 px-3 py-2 border border-secondary-300 rounded-md shadow-sm focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                    value={keys[provider]}
                    onChange={(e) => setKeys(prev => ({ ...prev, [provider]: e.target.value }))}
                    placeholder={status?.keys[provider] ? `Saved: ${status.keys[provider]}` : `Enter ${provider} API key`}
                  />
                  <Button 
                    variant="primary" 
                    onClick={() => handleSaveKey(provider)}
                    disabled={!keys[provider] || savingKey === provider}
                  >
                    Save
                  </Button>
                  {status?.keys[provider] && (
                    <Button 
                      variant="secondary" 
                      onClick={() => handleDeleteKey(provider)}
                      disabled={savingKey === provider}
                    >
                      Delete
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
