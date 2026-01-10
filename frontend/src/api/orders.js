const API_BASE = '/api'

export async function createOrder(mapId, fromNode, toNode) {
    const res = await fetch(`${API_BASE}/orders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            map_id: mapId,
            from_node: fromNode,
            to_node: toNode
        })
    })
    return res.json()
}

export async function getOrder(orderId) {
    const res = await fetch(`${API_BASE}/orders/${orderId}`)
    return res.json()
}
