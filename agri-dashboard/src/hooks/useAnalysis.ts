import { useState } from 'react';
import { toast } from 'react-toastify';
import type { AnalysisData, AggregateStats, FarmConfig, HistoryLog, AgentStep } from '../types';
import { API_BASE } from '../constants';

export function useAnalysis() {
  const [data, setData] = useState<AnalysisData | null>(null);
  const [loading, setLoading] = useState(false);
  const [hardwareStatus, setHardwareStatus] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<AgentStep>('idle');

  /** Derive AgentStep from streaming state snapshot */
  const deriveStep = (parsed: AnalysisData): AgentStep => {
    if (parsed.decision === 'error') return 'error';
    if (parsed.decision === 'anomaly') return 'awaiting'; // bypass agent steps — direct to HITL
    if (parsed.decision && parsed.human_approved === null) return 'awaiting';
    if (parsed.financial_analysis) return 'awaiting';
    if (parsed.botanist_analysis || parsed.meteorologist_analysis) {
      // Both or either running in parallel
      return 'meteorologist';
    }
    if (parsed.soil_moisture !== undefined) return 'sensors';
    return 'idle';
  };

  const runAnalysis = async (config: FarmConfig) => {
    setLoading(true);
    setHardwareStatus(null);
    setData(null);
    setCurrentStep('sensors');

    try {
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          crop_type: config.cropType,
          farm_area_sqm: config.farmArea,
          target_moisture_threshold: config.moistureThreshold,
          latitude: config.latitude,
          longitude: config.longitude,
          water_salinity: config.waterSalinity,
          plant_growth_stage: config.plantGrowthStage,
        }),
      });

      if (!response.ok) throw new Error(`Server error: ${response.status}`);
      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let done = false;

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          buffer += decoder.decode(value, { stream: true });
          let boundary = buffer.indexOf('\n\n');
          while (boundary !== -1) {
            const chunk = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            if (chunk.startsWith('data: ')) {
              try {
                const parsed: AnalysisData = JSON.parse(chunk.substring(6));
                setData(parsed);
                setCurrentStep(deriveStep(parsed));
                if (parsed.decision === 'error') {
                  toast.error('⚠️ LLM Rate Limit Hit. Please wait 60 seconds.');
                }
              } catch {
                // Ignore partial parse errors
              }
            }
            boundary = buffer.indexOf('\n\n');
          }
        }
      }
      toast.success('🌾 Farm report compiled successfully!');
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : 'Unknown error';
      toast.error(`Connection error: ${msg}`);
      setCurrentStep('error');
    }

    setLoading(false);
    setCurrentStep((prev) => (prev === 'error' ? 'error' : 'awaiting'));
  };

  const handleApproval = async (isApproved: boolean) => {
    if (!data?.thread_id) return;
    try {
      const response = await fetch(`${API_BASE}/api/actuate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thread_id: data.thread_id, is_approved: isApproved }),
      });
      if (!response.ok) throw new Error('Failed to send actuation command');
      const result = await response.json();
      setHardwareStatus(result.message);
      setCurrentStep('done');
      toast.info(isApproved ? '💧 Sprinklers Authorized!' : '🚫 Sprinklers Rejected.');
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : 'Unknown error';
      toast.error(`Actuation error: ${msg}`);
    }
  };

  const submitFeedback = async (logId: number, rating: number) => {
    try {
      await fetch(`${API_BASE}/api/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ log_id: logId, rating }),
      });
      toast.success('⭐ Feedback saved! The AI will learn from this.');
    } catch {
      toast.error('Failed to save feedback.');
    }
  };

  return {
    data,
    loading,
    hardwareStatus,
    currentStep,
    runAnalysis,
    handleApproval,
    submitFeedback,
    reset: () => { setData(null); setHardwareStatus(null); setCurrentStep('idle'); },
  };
}

export async function fetchHistory(): Promise<HistoryLog[]> {
  const res = await fetch(`${API_BASE}/api/history`);
  if (!res.ok) throw new Error('Failed to fetch history');
  const result = await res.json();
  return result.history;
}

export async function fetchStats(): Promise<AggregateStats> {
  const res = await fetch(`${API_BASE}/api/stats`);
  if (!res.ok) throw new Error('Failed to fetch stats');
  return res.json();
}
