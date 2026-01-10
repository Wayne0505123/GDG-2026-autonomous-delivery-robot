import { Link, useNavigate } from 'react-router-dom'
import { useCartStore } from '../stores/cartStore'

export default function Cart() {
    const items = useCartStore((state) => state.items)
    const updateQuantity = useCartStore((state) => state.updateQuantity)
    const removeItem = useCartStore((state) => state.removeItem)
    const getTotal = useCartStore((state) => state.getTotal)
    const navigate = useNavigate()

    if (items.length === 0) {
        return (
            <div className="max-w-2xl mx-auto px-4 py-16 text-center">
                <div className="text-6xl mb-4">🛒</div>
                <h2 className="text-2xl font-bold text-gray-800 mb-4">購物車是空的</h2>
                <p className="text-gray-500 mb-8">快去選購美食吧！</p>
                <Link
                    to="/"
                    className="inline-block bg-orange-500 hover:bg-orange-600 text-white px-6 py-3 rounded-lg font-medium transition-colors"
                >
                    開始選購
                </Link>
            </div>
        )
    }

    return (
        <div className="max-w-2xl mx-auto px-4 py-8">
            <h1 className="text-2xl font-bold text-gray-800 mb-6">購物車</h1>

            <div className="bg-white rounded-xl shadow-md overflow-hidden">
                {items.map((item) => (
                    <div
                        key={item.id}
                        className="flex items-center justify-between p-4 border-b border-gray-100 last:border-0"
                    >
                        <div className="flex-1">
                            <h3 className="font-medium text-gray-800">{item.name}</h3>
                            <p className="text-orange-600 font-bold">${item.price}</p>
                        </div>

                        <div className="flex items-center gap-3">
                            <button
                                onClick={() => updateQuantity(item.id, item.quantity - 1)}
                                className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center font-bold text-gray-600 cursor-pointer"
                            >
                                -
                            </button>
                            <span className="w-8 text-center font-medium">{item.quantity}</span>
                            <button
                                onClick={() => updateQuantity(item.id, item.quantity + 1)}
                                className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center font-bold text-gray-600 cursor-pointer"
                            >
                                +
                            </button>
                            <button
                                onClick={() => removeItem(item.id)}
                                className="ml-2 text-red-500 hover:text-red-600 cursor-pointer"
                            >
                                ✕
                            </button>
                        </div>
                    </div>
                ))}

                <div className="p-4 bg-gray-50">
                    <div className="flex justify-between items-center text-lg font-bold">
                        <span>總計</span>
                        <span className="text-orange-600">${getTotal()}</span>
                    </div>
                </div>
            </div>

            <button
                onClick={() => navigate('/checkout')}
                className="w-full mt-6 bg-orange-500 hover:bg-orange-600 text-white py-4 rounded-xl font-bold text-lg transition-colors cursor-pointer"
            >
                前往結帳
            </button>
        </div>
    )
}
