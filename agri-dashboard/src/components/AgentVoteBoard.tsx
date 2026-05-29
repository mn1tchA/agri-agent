import { type AgentVote } from '../types';
import { Shield } from 'lucide-react';

interface AgentVoteBoardProps {
  votes: Record<string, AgentVote> | string | undefined;
}

export function AgentVoteBoard({ votes }: AgentVoteBoardProps) {
  // Parse votes if they are passed as JSON string (from SQLite)
  let parsedVotes: Record<string, AgentVote> = {};
  if (votes) {
    if (typeof votes === 'string') {
      try {
        parsedVotes = JSON.parse(votes);
      } catch {
        parsedVotes = {};
      }
    } else {
      parsedVotes = votes;
    }
  }

  // Fallback default agents list if none present
  const agents = [
    { key: 'agronomist', label: 'Agronomist', icon: '🧬', color: 'border-emerald-500/20 text-emerald-400 bg-emerald-500/5' },
    { key: 'pedologist', label: 'Pedologist', icon: '🪨', color: 'border-amber-500/20 text-amber-400 bg-amber-500/5' },
    { key: 'economist', label: 'Economist', icon: '📈', color: 'border-purple-500/20 text-purple-400 bg-purple-500/5' },
    { key: 'meteorologist', label: 'Meteorologist', icon: '🌦️', color: 'border-blue-500/20 text-blue-400 bg-blue-500/5' },
    { key: 'botanist', label: 'Botanist', icon: '🍃', color: 'border-teal-500/20 text-teal-400 bg-teal-500/5' },
    { key: 'harvest', label: 'Harvest Advisor', icon: '🌾', color: 'border-pink-500/20 text-pink-400 bg-pink-500/5' },
  ];

  return (
    <div className="glass-panel border border-white/[0.06] p-5 rounded-2xl animate-fade-in">
      <div className="flex items-center gap-2 mb-4">
        <Shield className="w-4.5 h-4.5 text-emerald-400" />
        <h3 className="text-sm font-semibold font-display text-white">Consensus Vote Board</h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {agents.map((agent) => {
          const voteInfo = parsedVotes[agent.key] || { vote: 'abstain', confidence: 0.0, weight: 0.0 };
          const vote = voteInfo.vote?.toLowerCase() ?? 'abstain';
          const confidencePct = Math.round(voteInfo.confidence * 100);
          const weight = voteInfo.weight ?? 0.0;

          // Compute style based on vote
          const badgeStyles =
            vote === 'irrigate' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25' :
            vote === 'wait' ? 'bg-amber-500/10 text-amber-400 border-amber-500/25' :
            'bg-slate-500/10 text-slate-400 border-slate-500/25';

          return (
            <div key={agent.key} className="flex flex-col border border-white/[0.05] rounded-xl p-3 bg-white/[0.02]">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-semibold text-white flex items-center gap-1.5">
                  <span className="text-base">{agent.icon}</span>
                  {agent.label}
                </span>
                <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 border rounded-full ${badgeStyles}`}>
                  {vote === 'micro_irrigate' ? 'Micro' : vote}
                </span>
              </div>

              {/* Slider for confidence */}
              {vote !== 'abstain' ? (
                <div className="mt-1">
                  <div className="flex justify-between text-[10px] text-slate-400 mb-1">
                    <span>Confidence</span>
                    <span className="font-mono">{confidencePct}%</span>
                  </div>
                  <div className="h-1 rounded-full bg-slate-900 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${vote === 'irrigate' ? 'bg-emerald-500' : 'bg-amber-500'}`}
                      style={{ width: `${confidencePct}%` }}
                    />
                  </div>
                </div>
              ) : (
                <div className="text-[10px] text-slate-500 italic mt-1">Abstained from decision</div>
              )}

              {/* Weight details */}
              <div className="flex justify-between items-center text-[10px] text-slate-400 mt-2.5 pt-2.5 border-t border-white/[0.04]">
                <span>Voting Weight</span>
                <span className="font-semibold text-white font-mono">{(weight * 100).toFixed(0)}%</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
