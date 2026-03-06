import { ref, reactive } from 'vue'

export function useMouseEffects() {
  const mousePos = reactive({ x: 0, y: 0 })
  const ripples = ref([])
  let lastRippleTime = 0

  const handleMouseMove = (e) => {
    mousePos.x = e.clientX
    mousePos.y = e.clientY
    
    const now = Date.now()
    if (now - lastRippleTime > 40) {
      const id = now + Math.random()
      ripples.value.push({
        id,
        x: e.clientX,
        y: e.clientY,
        type: 'small'
      })
      lastRippleTime = now
      setTimeout(() => {
        ripples.value = ripples.value.filter(r => r.id !== id)
      }, 600)
    }
  }

  const handleClickRipple = (e) => {
    const id = Date.now()
    ripples.value.push({
      id,
      x: e.clientX,
      y: e.clientY,
      type: 'large'
    })
    setTimeout(() => {
      ripples.value = ripples.value.filter(r => r.id !== id)
    }, 1000)
  }

  return {
    mousePos,
    ripples,
    handleMouseMove,
    handleClickRipple
  }
}
