import { ref, reactive, nextTick } from 'vue'

export function useImageCropper(editForm) {
  const showCropModal = ref(false)
  const rawImageBuf = ref(null)
  const cropCanvas = ref(null)
  const cropperState = reactive({
    img: new Image(),
    x: 0,
    y: 0,
    scale: 1,
    dragging: false,
    startX: 0,
    startY: 0
  })

  const drawCropCanvas = () => {
    const canvas = cropCanvas.value
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const size = 300
    canvas.width = size
    canvas.height = size

    ctx.clearRect(0, 0, size, size)

    const img = cropperState.img
    const aspect = img.width / img.height
    let drawW, drawH
    if (aspect > 1) {
      drawW = size * cropperState.scale * aspect
      drawH = size * cropperState.scale
    } else {
      drawW = size * cropperState.scale
      drawH = size * cropperState.scale / aspect
    }

    ctx.drawImage(img, cropperState.x - drawW/2 + size/2, cropperState.y - drawH/2 + size/2, drawW, drawH)

    // Mask
    ctx.fillStyle = 'rgba(0, 0, 0, 0.6)'
    ctx.beginPath()
    ctx.rect(0, 0, size, size)
    ctx.arc(size/2, size/2, size/2 * 0.9, 0, Math.PI * 2, true)
    ctx.fill()

    // Border
    ctx.strokeStyle = '#ff69b4'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.arc(size/2, size/2, size/2 * 0.9, 0, Math.PI * 2)
    ctx.stroke()
  }

  const handleImageUpload = (e) => {
    const file = e.target.files[0]
    if (file) {
      if (file.size > 2 * 1024 * 1024) {
        alert('图片大小不能超过 2MB')
        return
      }
      const reader = new FileReader()
      reader.onload = (event) => {
        rawImageBuf.value = event.target.result
        cropperState.img = new Image()
        cropperState.img.src = event.target.result
        cropperState.img.onload = () => {
          cropperState.x = 0
          cropperState.y = 0
          cropperState.scale = 1
          showCropModal.value = true
          nextTick(() => drawCropCanvas())
        }
      }
      reader.readAsDataURL(file)
    }
    e.target.value = ''
  }

  const handleCropMouseDown = (e) => {
    cropperState.dragging = true
    cropperState.startX = e.clientX - cropperState.x
    cropperState.startY = e.clientY - cropperState.y
  }

  const handleCropMouseMove = (e) => {
    if (cropperState.dragging) {
      cropperState.x = e.clientX - cropperState.startX
      cropperState.y = e.clientY - cropperState.startY
      drawCropCanvas()
    }
  }

  const handleCropMouseUp = () => {
    cropperState.dragging = false
  }

  const handleCropWheel = (e) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? 0.9 : 1.1
    cropperState.scale *= delta
    drawCropCanvas()
  }

  const confirmCrop = () => {
    const canvas = document.createElement('canvas')
    const size = 400
    canvas.width = size
    canvas.height = size
    const ctx = canvas.getContext('2d')

    const img = cropperState.img
    const aspect = img.width / img.height
    let drawW, drawH
    if (aspect > 1) {
      drawW = size * cropperState.scale * aspect
      drawH = size * cropperState.scale
    } else {
      drawW = size * cropperState.scale
      drawH = size * cropperState.scale / aspect
    }

    ctx.drawImage(img, (cropperState.x * (size/300)) - drawW/2 + size/2, (cropperState.y * (size/300)) - drawH/2 + size/2, drawW, drawH)

    canvas.toBlob((blob) => {
      editForm.imageFile = new File([blob], "avatar.webp", { type: "image/webp" })
      editForm.imagePreview = URL.createObjectURL(blob)
      showCropModal.value = false
    }, 'image/webp')
  }

  const cancelCrop = () => {
    showCropModal.value = false
  }

  return {
    showCropModal,
    rawImageBuf,
    cropCanvas,
    cropperState,
    handleImageUpload,
    drawCropCanvas,
    handleCropMouseDown,
    handleCropMouseMove,
    handleCropMouseUp,
    handleCropWheel,
    confirmCrop,
    cancelCrop
  }
}
