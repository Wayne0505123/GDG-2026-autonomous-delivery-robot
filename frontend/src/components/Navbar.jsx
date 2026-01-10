import { Link } from 'react-router-dom'
import { useCartStore } from '../stores/cartStore'

export default function Navbar() {
    const itemCount = useCartStore((state) => state.getItemCount())

    return (
        <nav className="bg-white shadow-md sticky top-0 z-50">
            <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
                <Link to="/" className="text-2xl font-bold text-orange-600 flex items-center gap-2">
                    {/* <span></span> */}
                    <span>DeliveryBot</span>
                </Link>
                <Link
                    to="/cart"
                    className="relative bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg font-medium transition-colors"
                >
                    🛒
                    {itemCount > 0 && (
                        <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs w-6 h-6 rounded-full flex items-center justify-center font-bold">
                            {itemCount}
                        </span>
                    )}
                </Link>
            </div>
        </nav>
    )
}
