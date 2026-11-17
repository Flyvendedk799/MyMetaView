import { useEffect, useState } from 'react'
import { fetchDomains, getCoverage, saveCoverage, scanCoverage, type CoverageState } from '../api/client'
import type { Domain } from '../api/types'
import Button from '../components/ui/Button'

export default function Coverage() {
  const [domains,setDomains]=useState<Domain[]>([])
  const [id,setId]=useState(0)
  const [data,setData]=useState<CoverageState|null>(null)
  const [message,setMessage]=useState('')
  const [busy,setBusy]=useState(false)
  useEffect(()=>{fetchDomains().then(rows=>{setDomains(rows);setId(rows[0]?.id||0)}).catch(e=>setMessage(e.message))},[])
  useEffect(()=>{if(!id)return;let active=true;const load=()=>getCoverage(id).then(s=>{if(active)setData(s)}).catch(e=>{if(active)setMessage(e.message)});setData(null);load();const timer=setInterval(load,10000);return()=>{active=false;clearInterval(timer)}},[id])
  async function action(scan=false){if(!data)return;setBusy(true);try{if(scan){await scanCoverage(id);setMessage('Site scan queued. This page updates automatically.')}else{await saveCoverage(id,!data.enabled,data.interval_hours);setData({...data,enabled:!data.enabled});setMessage(data.enabled?'Automatic refresh paused.':'Automatic refresh enabled. New and changed pages will be generated.')}}catch(e){setMessage(e instanceof Error?e.message:'Could not save')}finally{setBusy(false)}}
  return <div className="space-y-5"><h1 className="text-3xl font-bold">Site coverage</h1><p>Discover pages, keep cards current, and recover pages that need attention.</p>
    <label>Domain<select aria-label="Coverage domain" className="block border rounded p-2" value={id} onChange={e=>setId(Number(e.target.value))}>{domains.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
    {!domains.length&&<p>Connect and verify a domain to begin.</p>}
    {data&&<><div className="flex items-center gap-3 flex-wrap"><label>Check every <select aria-label="Refresh interval" value={data.interval_hours} onChange={e=>setData({...data,interval_hours:Number(e.target.value)})}>{[6,12,24,48,168].map(h=><option key={h} value={h}>{h} hours</option>)}</select></label><Button disabled={busy} onClick={()=>action()}>{data.enabled?'Pause automatic refresh':'Enable automatic refresh'}</Button><Button disabled={busy} variant="secondary" onClick={()=>action(true)}>Scan site now</Button></div><p className="text-sm">Automatic scans follow each card’s publishing policy and preserve locked fields. Scans cover up to 2,000 discovered URLs.</p>
    {data.error&&<p role="alert">{data.error}</p>}
    <div className="flex gap-3 flex-wrap">{['missing','queued','generating','ready','stale','failed','removed'].map(state=><span key={state} className="border rounded px-3 py-2 capitalize">{state}: {data.pages.filter(p=>p.state===state).length}</span>)}</div>
    <div className="overflow-auto"><table className="w-full text-sm text-left"><thead><tr><th>Page</th><th>Status</th><th>Details</th></tr></thead><tbody>{data.pages.map(p=><tr key={p.id} className="border-t"><td className="py-3">{p.url}{p.canonical_url&&p.canonical_url!==p.url&&<p className="text-xs">Canonical: {p.canonical_url}</p>}</td><td>{p.state}</td><td>{p.error||''}</td></tr>)}</tbody></table></div></>}
    <p role="status">{message}</p></div>
}
