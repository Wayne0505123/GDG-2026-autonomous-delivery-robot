import { useEffect, useRef } from 'react'

export default function LiveMap({ mapData, robotPosition, route }) {
    const canvasRef = useRef(null)

    useEffect(() => {
        if (!mapData || !canvasRef.current) return

        const canvas = canvasRef.current
        const ctx = canvas.getContext('2d')
        const scale = 4
        const offsetX = 50
        const offsetY = 100

        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height)

        // Draw edges (paths)
        ctx.strokeStyle = '#e5e7eb'
        ctx.lineWidth = 8
        ctx.lineCap = 'round'

        if (mapData.edges) {
            mapData.edges.forEach(edge => {
                const from = mapData.nodes.find(n => n.id === edge.from)
                const to = mapData.nodes.find(n => n.id === edge.to)
                if (from && to) {
                    ctx.beginPath()
                    ctx.moveTo(from.x * scale + offsetX, offsetY)
                    ctx.lineTo(to.x * scale + offsetX, offsetY)
                    ctx.stroke()
                }
            })
        }

        // Highlight route if exists
        if (route && route.length > 1) {
            ctx.strokeStyle = '#f97316'
            ctx.lineWidth = 6
            for (let i = 0; i < route.length - 1; i++) {
                const from = mapData.nodes.find(n => n.id === route[i])
                const to = mapData.nodes.find(n => n.id === route[i + 1])
                if (from && to) {
                    ctx.beginPath()
                    ctx.moveTo(from.x * scale + offsetX, offsetY)
                    ctx.lineTo(to.x * scale + offsetX, offsetY)
                    ctx.stroke()
                }
            }
        }

        // Draw nodes
        mapData.nodes.forEach(node => {
            const x = node.x * scale + offsetX
            const y = offsetY

            // Node circle
            ctx.fillStyle = route?.includes(node.id) ? '#f97316' : '#374151'
            ctx.beginPath()
            ctx.arc(x, y, 12, 0, Math.PI * 2)
            ctx.fill()

            // Node label
            ctx.fillStyle = '#374151'
            ctx.font = 'bold 14px sans-serif'
            ctx.textAlign = 'center'
            ctx.fillText(node.name || node.id, x, y + 35)
        })

        // Draw robot
        if (robotPosition) {
            const x = robotPosition.x * scale + offsetX
            const y = offsetY

            // Robot circle
            ctx.fillStyle = '#ef4444'
            ctx.beginPath()
            ctx.arc(x, y, 16, 0, Math.PI * 2)
            ctx.fill()

            // Robot icon
            ctx.fillStyle = 'white'
            ctx.font = '16px sans-serif'
            ctx.textAlign = 'center'
            ctx.textBaseline = 'middle'
            ctx.fillText('🚗', x, y)
        }
    }, [mapData, robotPosition, route])

    return (
        <div className="bg-gray-50 rounded-xl p-4">
            <canvas
                ref={canvasRef}
                width={700}
                height={200}
                className="w-full"
            />
        </div>
    )
}
