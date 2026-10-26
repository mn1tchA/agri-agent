import { create } from 'zustand';
import { apiClient } from '../api/client';
import type { AlertLogItem, Farm, ValveCommand } from '../types';

interface FarmState {
  farms: Farm[];
  selectedFarm: Farm | null;
  alerts: AlertLogItem[];
  valves: ValveCommand[];
  isLoading: boolean;
  error: string | null;

  fetchFarms: () => Promise<void>;
  selectFarm: (farm: Farm) => void;
  createFarm: (payload: Partial<Farm>) => Promise<Farm>;
  updateFarm: (id: number, payload: Partial<Farm>) => Promise<Farm>;
  deleteFarm: (id: number) => Promise<boolean>;
  fetchAlerts: () => Promise<void>;
  fetchValves: () => Promise<void>;
  emergencyStopValves: () => Promise<void>;
}

export const useFarmStore = create<FarmState>((set, get) => ({
  farms: [],
  selectedFarm: null,
  alerts: [],
  valves: [],
  isLoading: false,
  error: null,

  fetchFarms: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await apiClient.get<Farm[]>('/api/v1/farms');
      set({ farms: data, isLoading: false });
      if (data.length > 0 && !get().selectedFarm) {
        set({ selectedFarm: data[0] });
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch farms';
      set({ isLoading: false, error: msg });
    }
  },

  selectFarm: (farm: Farm) => {
    set({ selectedFarm: farm });
  },

  createFarm: async (payload: Partial<Farm>) => {
    set({ isLoading: true, error: null });
    try {
      const created = await apiClient.post<Farm>('/api/v1/farms', payload);
      const updated = [...get().farms, created];
      set({ farms: updated, selectedFarm: created, isLoading: false });
      return created;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create farm';
      set({ isLoading: false, error: msg });
      throw err;
    }
  },

  updateFarm: async (id: number, payload: Partial<Farm>) => {
    set({ isLoading: true, error: null });
    try {
      const updated = await apiClient.put<Farm>(`/api/v1/farms/${id}`, payload);
      const list = get().farms.map((f) => (f.id === id ? updated : f));
      set({
        farms: list,
        selectedFarm: get().selectedFarm?.id === id ? updated : get().selectedFarm,
        isLoading: false,
      });
      return updated;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update farm';
      set({ isLoading: false, error: msg });
      throw err;
    }
  },

  deleteFarm: async (id: number) => {
    set({ isLoading: true, error: null });
    try {
      await apiClient.delete(`/api/v1/farms/${id}`);
      const remaining = get().farms.filter((f) => f.id !== id);
      set({
        farms: remaining,
        selectedFarm: remaining.length > 0 ? remaining[0] : null,
        isLoading: false,
      });
      return true;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to delete farm';
      set({ isLoading: false, error: msg });
      return false;
    }
  },

  fetchAlerts: async () => {
    try {
      const selected = get().selectedFarm;
      const path = selected ? `/api/v1/alerts?farm_id=${selected.id}` : '/api/v1/alerts';
      const data = await apiClient.get<AlertLogItem[]>(path);
      set({ alerts: data });
    } catch (err) {
      console.warn('Failed to fetch alerts:', err);
    }
  },

  fetchValves: async () => {
    try {
      const selected = get().selectedFarm;
      const path = selected ? `/api/v1/valves?farm_id=${selected.id}` : '/api/v1/valves';
      const data = await apiClient.get<ValveCommand[]>(path);
      set({ valves: data });
    } catch (err) {
      console.warn('Failed to fetch valve logs:', err);
    }
  },

  emergencyStopValves: async () => {
    try {
      await apiClient.post('/api/v1/valves/emergency-stop', {});
      await get().fetchValves();
    } catch (err) {
      console.error('Failed to halt valves:', err);
      throw err;
    }
  },
}));
