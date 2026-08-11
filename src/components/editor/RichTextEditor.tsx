import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Link from '@tiptap/extension-link'
import Image from '@tiptap/extension-image'
import Placeholder from '@tiptap/extension-placeholder'
import Underline from '@tiptap/extension-underline'
import TextAlign from '@tiptap/extension-text-align'
import { useEffect } from 'react'
import EditorToolbar from './EditorToolbar'

interface RichTextEditorProps {
  content: string
  onChange: (content: string) => void
  placeholder?: string
  onInsertImage?: () => void
  minHeight?: string
  disabled?: boolean
}

export default function RichTextEditor({
  content,
  onChange,
  placeholder = 'Start writing...',
  onInsertImage,
  minHeight = '300px',
  disabled = false,
}: RichTextEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3, 4],
        },
      }),
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          class: 'text-primary underline hover:text-primary/80',
        },
      }),
      Image.configure({
        HTMLAttributes: {
          class: 'max-w-full h-auto rounded-lg my-4',
        },
      }),
      Placeholder.configure({
        placeholder,
      }),
      Underline,
      TextAlign.configure({
        types: ['heading', 'paragraph'],
      }),
    ],
    content,
    editable: !disabled,
    onUpdate: ({ editor }) => {
      onChange(editor.getHTML())
    },
  })

  // Update content when prop changes (e.g., loading existing content)
  useEffect(() => {
    if (editor && content !== editor.getHTML()) {
      editor.commands.setContent(content)
    }
  }, [content, editor])

  // Update editable state
  useEffect(() => {
    if (editor) {
      editor.setEditable(!disabled)
    }
  }, [disabled, editor])

  const handleInsertImage = () => {
    if (onInsertImage) {
      onInsertImage()
    }
  }

  // Function to insert image URL (called from parent after media picker)
  const insertImage = (url: string, alt?: string) => {
    if (editor) {
      editor.chain().focus().setImage({ src: url, alt: alt || '' }).run()
    }
  }

  // Expose insertImage method via ref would be better, but for simplicity we'll use a callback pattern
  // The parent can call editor.commands.setImage directly if needed

  return (
    <div className={`border border-secondary-300 rounded-lg overflow-hidden ${disabled ? 'opacity-60' : ''}`}>
      <EditorToolbar editor={editor} onInsertImage={handleInsertImage} />
      <EditorContent
        editor={editor}
        className="prose prose-sm sm:prose max-w-none"
        style={{ minHeight }}
      />
      <style>{`
        .ProseMirror {
          padding: 1rem;
          min-height: ${minHeight};
          outline: none;
        }
        .ProseMirror p.is-editor-empty:first-child::before {
          content: attr(data-placeholder);
          float: left;
          color: #9ca3af;
          pointer-events: none;
          height: 0;
        }
        .ProseMirror h1 {
          font-size: 2rem;
          font-weight: 700;
          margin-top: 1.5rem;
          margin-bottom: 1rem;
        }
        .ProseMirror h2 {
          font-size: 1.5rem;
          font-weight: 600;
          margin-top: 1.25rem;
          margin-bottom: 0.75rem;
        }
        .ProseMirror h3 {
          font-size: 1.25rem;
          font-weight: 600;
          margin-top: 1rem;
          margin-bottom: 0.5rem;
        }
        .ProseMirror h4 {
          font-size: 1.125rem;
          font-weight: 600;
          margin-top: 1rem;
          margin-bottom: 0.5rem;
        }
        .ProseMirror p {
          margin-bottom: 1rem;
        }
        .ProseMirror ul,
        .ProseMirror ol {
          padding-left: 1.5rem;
          margin-bottom: 1rem;
        }
        .ProseMirror li {
          margin-bottom: 0.25rem;
        }
        .ProseMirror blockquote {
          border-left: 4px solid #e5e7eb;
          padding-left: 1rem;
          margin-left: 0;
          margin-right: 0;
          font-style: italic;
          color: #6b7280;
        }
        .ProseMirror code {
          background: #f3f4f6;
          padding: 0.2rem 0.4rem;
          border-radius: 0.25rem;
          font-size: 0.875em;
          font-family: ui-monospace, monospace;
        }
        .ProseMirror pre {
          background: #1f2937;
          color: #f9fafb;
          padding: 1rem;
          border-radius: 0.5rem;
          overflow-x: auto;
          margin: 1rem 0;
        }
        .ProseMirror pre code {
          background: none;
          padding: 0;
          color: inherit;
        }
        .ProseMirror img {
          max-width: 100%;
          height: auto;
          border-radius: 0.5rem;
          margin: 1rem 0;
        }
        .ProseMirror hr {
          border: none;
          border-top: 2px solid #e5e7eb;
          margin: 2rem 0;
        }
        .ProseMirror a {
          color: #f97316;
          text-decoration: underline;
        }
        .ProseMirror a:hover {
          color: #ea580c;
        }
      `}</style>
    </div>
  )
}

// Export a hook for getting editor instance if needed
export { useEditor }

