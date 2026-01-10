import { useCartStore } from '../stores/cartStore'

export default function ProductCard({ product }) {
    const addItem = useCartStore((state) => state.addItem)

    return (
        <div className="bg-white rounded-xl shadow-md overflow-hidden hover:shadow-lg transition-shadow">
            <div className="h-40 bg-gradient-to-br from-orange-100 to-orange-200 flex items-center justify-center">
                <span className="text-6xl">
                    {product.name.includes('便當') ? '🍱' :
                        product.name.includes('雞') ? '🍗' :
                            product.name.includes('排骨') ? '🥩' :
                                product.name.includes('紅茶') ? '🧋' :
                                    product.name.includes('綠茶') ? '🍵' : '📦'}
                </span>
            </div>
            <div className="p-4">
                <h3 className="font-bold text-lg text-gray-800">{product.name}</h3>
                <p className="text-gray-500 text-sm mt-1">{product.description}</p>
                <div className="mt-4 flex items-center justify-between">
                    <span className="text-xl font-bold text-orange-600">${product.price}</span>
                    <button
                        onClick={() => addItem(product)}
                        className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg font-medium transition-colors cursor-pointer"
                    >
                        加入購物車
                    </button>
                </div>
            </div>
        </div>
    )
}
