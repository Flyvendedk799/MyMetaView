import { useRef } from 'react'
import { motion, useScroll, useTransform } from 'framer-motion'
import { DataSphere } from './DataSphere'
import { ActionHub } from './ActionHub'
import { LiveDataSandbox } from './LiveDataSandbox'

export function Scrollytelling() {
  const containerRef = useRef<HTMLDivElement>(null)
  
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start end", "end start"]
  })

  // We can use transform to drive internal animations, but framer-motion's whileInView is simpler for features
  
  const customEase = [0.85, 0, 0.15, 1]

  const features = [
    {
      title: "Interactive Data-Sphere",
      description: "Explore your metadata in a fully interactive 3D space, powered by WebGL.",
      component: <DataSphere />
    },
    {
      title: "Context-Aware Action Hub",
      description: "Intelligent actions that adapt to your content, guiding users naturally.",
      component: <ActionHub />
    },
    {
      title: "Real-time Live Data Sandbox",
      description: "Watch your changes propagate instantly with live ripple effects.",
      component: <LiveDataSandbox />
    }
  ]

  return (
    <div ref={containerRef} className="py-24 space-y-32">
      {features.map((feature, index) => (
        <motion.div 
          key={index}
          initial={{ opacity: 0, y: 100 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.8, ease: customEase }}
          className={`flex flex-col ${index % 2 === 1 ? 'lg:flex-row-reverse' : 'lg:flex-row'} items-center gap-12 max-w-7xl mx-auto px-6`}
        >
          <div className="flex-1 w-full text-left">
            <h3 className="text-3xl sm:text-4xl font-display font-semibold text-paper mb-4">{feature.title}</h3>
            <p className="text-lg text-paper/70 leading-relaxed max-w-lg">{feature.description}</p>
          </div>
          <div className="flex-1 w-full">
            {feature.component}
          </div>
        </motion.div>
      ))}
    </div>
  )
}
