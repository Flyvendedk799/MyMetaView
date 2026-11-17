import { useEffect, useState } from 'react'
import { getCardStudio, saveCardStudio, createPreviewJob, getCardHistory, publishCard, restoreCard, type CardHistoryEntry, type CardStudioState } from '../api/client'
import Button from './ui/Button'

export default function CardEditor({ id, url, domain }: { id: number; url: string; domain: string }) {
  const [draft, setDraft] = useState<CardStudioState | null>(null)
  const [undo, setUndo] = useState<CardStudioState[]>([])
  const [history, setHistory] = useState<CardHistoryEntry[]>([])
  const [autoPublish, setAutoPublish] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  useEffect(() => { let active = true; getCardStudio(id).then(s => { if (active) { setDraft(s); setAutoPublish(s.auto_publish); getCardHistory(id).then(setHistory).catch(e => setMessage(e.message)) } }).catch(e => { if (active) setMessage(e.message) }); return () => { active = false } }, [id])
  function edit(patch: Partial<CardStudioState>) {
    if (!draft) return
    setUndo(u => [...u.slice(-29), draft]); setDraft({ ...draft, ...patch })
  }
  async function save(regenerate = false) {
    if (!draft) return
    setBusy(true); setMessage('')
    try {
      const saved = await saveCardStudio(id, draft); setDraft(saved); setUndo([])
      if (regenerate) { await createPreviewJob({ url, domain, force: true }); setMessage('Regenerating unlocked fields. Follow progress in your gallery.') }
      else setMessage('Draft saved. Review all formats, then publish when ready.')
      setHistory(await getCardHistory(id))
    } catch (e) { setMessage(e instanceof Error ? e.message : 'Could not save') }
    finally { setBusy(false) }
  }
  async function publishOrRestore(oldRevision?: number) {
    if (!draft) return
    setBusy(true); setMessage('')
    try {
      const result = oldRevision ? await restoreCard(id, oldRevision, draft.revision) : await publishCard(id, draft.revision, autoPublish)
      setDraft(result); setUndo([]); setHistory(await getCardHistory(id))
      setMessage(oldRevision ? 'Version restored as a draft. Review and publish it.' : 'Card published. Social platforms may retain an older cached card until they fetch again.')
    } catch(e) { setMessage(e instanceof Error ? e.message : 'Could not update card') }
    finally { setBusy(false) }
  }
  if (!draft) return <p role="status">{message || 'Loading editor…'}</p>
  return <div className="space-y-4">
    <p className="text-sm text-secondary-600">Edit individual elements. Locked fields stay unchanged when you regenerate.</p>
    <fieldset disabled={busy || !draft.can_rerender} className="grid gap-3 md:grid-cols-2">
      {(['title', 'description', 'visual_url', 'logo_url'] as const).map(key => <label key={key} className="text-sm">
        {{ title: 'Headline', description: 'Description', visual_url: 'Image URL', logo_url: 'Logo URL' }[key]}
        <input className="block w-full border rounded p-2" value={draft[key] || ''} onChange={e => edit({ [key]: e.target.value || (key.endsWith('_url') ? null : '') })} />
      </label>)}
      {([['layout', ['typographic','split','stat','profile','editorial','product']], ['panel', ['primary','secondary','dark','light']], ['accent', ['bar','dot','shape']]] as const).map(([key, options]) => <label key={key} className="capitalize text-sm">{key}<select className="block w-full border rounded p-2" value={draft[key]} onChange={e => edit({ [key]: e.target.value })}>{options.map(value => <option key={value}>{value}</option>)}</select></label>)}
      {(['focal_x', 'focal_y'] as const).map(key => <label key={key} className="text-sm">Image focus {key === 'focal_x' ? 'horizontal' : 'vertical'} ({draft[key]}%)<input className="block w-full" type="range" min="0" max="100" value={draft[key]} onChange={e => edit({ [key]: Number(e.target.value) })} /></label>)}
      <div className="flex flex-wrap gap-3 md:col-span-2">{['title','description','layout','visual','logo'].map(key => <label key={key} className="text-sm"><input type="checkbox" checked={draft.locks.includes(key)} onChange={e => edit({ locks: e.target.checked ? [...draft.locks,key] : draft.locks.filter(k => k !== key) })} /> Lock {key}</label>)}</div>
    </fieldset>
    <div className="flex gap-2 flex-wrap">
      <Button disabled={busy || !undo.length} variant="secondary" onClick={() => { setDraft(undo[undo.length-1]); setUndo(u => u.slice(0,-1)) }}>Undo edit</Button>
      <Button loading={busy} disabled={!draft.can_rerender} onClick={() => save()}>Save draft</Button>
      <Button disabled={busy || !draft.can_rerender} variant="secondary" onClick={() => save(true)}>Regenerate unlocked fields</Button>
    </div>
    <div className="border rounded p-3 space-y-2">
      <p className="font-medium">{draft.has_draft ? 'Unpublished changes' : 'Published card is current'}</p>
      <label className="text-sm block"><input type="checkbox" checked={autoPublish} onChange={e => setAutoPublish(e.target.checked)} /> Automatically publish future regenerations</label>
      <Button disabled={busy || undo.length > 0} onClick={() => publishOrRestore()}>Publish saved draft</Button>
      {undo.length > 0 && <p className="text-sm">Save your changes before publishing.</p>}
      {draft.published && <figure><img src={draft.published.image_url} alt="Currently published card" className="max-w-sm w-full" /><figcaption>Currently published: {draft.published.title}</figcaption></figure>}
    </div>
    <details><summary>Version history</summary>{history.map(entry => <div key={entry.revision} className="flex gap-3 items-center py-2"><img src={entry.image_url} alt="" className="w-24" /><span>Version {entry.revision}: {entry.title}</span><Button variant="secondary" disabled={busy} onClick={() => publishOrRestore(entry.revision)}>Restore as draft</Button></div>)}</details>
    <p role="status">{message}</p>
    {!draft.can_rerender && <p>Regenerate this older card from the gallery to enable editing.</p>}
    <div className="grid md:grid-cols-3 gap-4">{Object.entries(draft.images).map(([size, image]) => <figure key={size}><img src={image} alt={`${size} card`} className="w-full border rounded" /><figcaption className="capitalize text-sm">{size} · saved preview</figcaption></figure>)}</div>
  </div>
}
