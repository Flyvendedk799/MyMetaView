import { useEffect, useState } from 'react'
import { Lottie } from 'lottie-react'

export function ActionHub() {
  const [animationData, setAnimationData] = useState<any>(null)

  useEffect(() => {
    fetch('https://assets.mymetaview.com/lottie/action-hub-morph.json')
      .then(res => res.json())
      .then(data => setAnimationData(data))
      .catch(err => console.error('Failed to load lottie', err))
  }, [])

  if (!animationData) {
    return <div className="w-full h-full min-h-[300px] flex items-center justify-center bg-paper/5 rounded-2xl animate-pulse">Loading Animation...</div>
  }

  return (
    <div className="relative w-full h-full min-h-[300px] flex items-center justify-center">
      <div className="absolute inset-0 bg-primary-500/10 blur-3xl rounded-full scale-75" />
      <Lottie
        src={animationData}
        loop={true}
        autoplay={true}
        className="w-full max-w-[400px]"
      />
    </div>
  )
}
