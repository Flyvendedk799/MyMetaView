import { useEffect, useState } from 'react'
import { Lottie } from 'lottie-react'

export function LiveDataSandbox() {
  const [animationData, setAnimationData] = useState<any>(null)

  useEffect(() => {
    fetch('https://assets.mymetaview.com/lottie/sandbox-ripple.json')
      .then(res => res.json())
      .then(data => setAnimationData(data))
      .catch(err => console.error('Failed to load lottie', err))
  }, [])

  if (!animationData) {
    return <div className="w-full h-full min-h-[300px] flex items-center justify-center bg-paper/5 rounded-2xl animate-pulse">Loading Sandbox...</div>
  }

  return (
    <div className="relative w-full h-full min-h-[300px] flex items-center justify-center overflow-hidden bg-ink/50 border border-paper/10 rounded-2xl p-6">
      <div className="absolute inset-0 bg-accent-500/10 blur-3xl rounded-full scale-110" />
      <Lottie
        src={animationData}
        loop={true}
        autoplay={true}
        className="w-full max-w-[500px] z-10"
      />
    </div>
  )
}
