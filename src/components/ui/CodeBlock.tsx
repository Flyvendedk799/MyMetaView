import { useCallback, useEffect, useRef, useState } from 'react'
import { CheckIcon, ClipboardDocumentIcon } from '@heroicons/react/24/outline'

interface CodeBlockProps {
  code: string
  /** Shown above the block, e.g. a filename or where the code goes. */
  label?: string
  /** Text on the copy button. */
  copyLabel?: string
  /** Let long lines wrap instead of scrolling. Useful for a single long tag. */
  wrap?: boolean
  className?: string
}

/**
 * A code block that is one click away from the clipboard.
 *
 * Falls back to selecting the text when the Clipboard API is unavailable —
 * that happens on any page not served over HTTPS, which includes plenty of
 * local dev setups.
 */
export default function CodeBlock({
  code,
  label,
  copyLabel = 'Copy',
  wrap = false,
  className = '',
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState(false)
  const codeRef = useRef<HTMLElement>(null)
  const resetTimer = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => () => clearTimeout(resetTimer.current), [])

  const selectAll = useCallback(() => {
    const node = codeRef.current
    if (!node) return
    const range = document.createRange()
    range.selectNodeContents(node)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)
  }, [])

  const copy = useCallback(async () => {
    clearTimeout(resetTimer.current)
    try {
      if (!navigator.clipboard) throw new Error('clipboard unavailable')
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setError(false)
    } catch {
      // Select the text so the keyboard shortcut still works.
      selectAll()
      setError(true)
      setCopied(false)
    }
    resetTimer.current = setTimeout(() => {
      setCopied(false)
      setError(false)
    }, 2500)
  }, [code, selectAll])

  return (
    <div className={className}>
      {label && (
        <div className="text-xs font-medium text-secondary-500 mb-1.5">{label}</div>
      )}
      <div className="relative group">
        <pre
          className={`bg-secondary-900 text-secondary-100 rounded-lg p-4 pr-28 text-sm font-mono leading-relaxed ${
            wrap ? 'whitespace-pre-wrap break-all' : 'overflow-x-auto'
          }`}
        >
          <code ref={codeRef}>{code}</code>
        </pre>
        <button
          type="button"
          onClick={copy}
          aria-label={copied ? 'Copied to clipboard' : `${copyLabel} to clipboard`}
          className={`absolute top-2.5 right-2.5 inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-secondary-900 focus:ring-primary ${
            copied
              ? 'bg-success-500 text-white'
              : 'bg-secondary-700 text-secondary-100 hover:bg-secondary-600'
          }`}
        >
          {copied ? (
            <>
              <CheckIcon className="w-3.5 h-3.5" />
              Copied
            </>
          ) : (
            <>
              <ClipboardDocumentIcon className="w-3.5 h-3.5" />
              {copyLabel}
            </>
          )}
        </button>
      </div>
      {error && (
        <p className="text-xs text-secondary-500 mt-1.5" role="status">
          We selected the code for you — press {navigator.platform.includes('Mac') ? '⌘C' : 'Ctrl+C'} to copy.
        </p>
      )}
    </div>
  )
}
