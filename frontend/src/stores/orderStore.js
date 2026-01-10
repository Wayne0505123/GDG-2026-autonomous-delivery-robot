import { create } from 'zustand'

export const useOrderStore = create((set) => ({
    currentOrder: null,

    setOrder: (order) => set({ currentOrder: order }),

    clearOrder: () => set({ currentOrder: null }),

    updateOrderState: (state) => set((prev) => ({
        currentOrder: prev.currentOrder
            ? { ...prev.currentOrder, state }
            : null
    }))
}))
