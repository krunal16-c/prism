"use client";

import { useState, ReactNode } from "react";
import axios from "axios";
import { X, Calculator, TrendingUp, Users, ShieldCheck, DollarSign, ArrowRight, CheckCircle2 } from "lucide-react";
import { motion } from "framer-motion";
import clsx from "clsx";

interface OptimizerProps {
  onClose: () => void;
}

export default function Optimizer({ onClose }: OptimizerProps) {
  const [budget, setBudget] = useState(50000000);
  const [priorities, setPriorities] = useState({
    cost_efficiency: 50,
    regional_equity: 50,
    climate_resilience: 50,
    population_impact: 50,
  });
  const [results, setResults] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleOptimize = async () => {
    setLoading(true);
    try {
      const response = await axios.post("http://localhost:8000/api/optimize", {
        budget,
        priorities,
      });
      setResults(response.data);
    } catch (error) {
      console.error("Error optimizing:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleSliderChange = (key: string, value: number) => {
    setPriorities((prev) => ({ ...prev, [key]: value }));
  };

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(val);
  };

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center z-[2000] p-4">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col border border-slate-200"
      >
        {/* Header */}
        <div className="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 text-blue-700 rounded-lg">
              <Calculator size={24} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-900">Budget Optimizer</h2>
              <p className="text-sm text-slate-500">Multi-criteria resource allocation engine</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-full text-slate-400 hover:text-slate-600 transition-colors">
            <X size={24} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto flex flex-col md:flex-row">
          {/* Controls Panel */}
          <div className="w-full md:w-1/3 p-6 border-r border-slate-100 bg-slate-50/30 space-y-8">
            
            {/* Budget Input */}
            <div className="space-y-3">
              <label className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                <DollarSign size={16} /> Total Budget Allocation
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 font-medium">$</span>
                <input
                  type="number"
                  value={budget}
                  onChange={(e) => setBudget(Number(e.target.value))}
                  className="w-full pl-8 pr-4 py-2.5 bg-white border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none font-mono text-slate-900"
                />
              </div>
              <p className="text-xs text-slate-500 text-right">{formatCurrency(budget)}</p>
            </div>

            {/* Sliders */}
            <div className="space-y-6">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Strategic Priorities</h3>
              
              <SliderControl 
                label="Cost Efficiency" 
                icon={<TrendingUp size={16} />} 
                value={priorities.cost_efficiency} 
                onChange={(v) => handleSliderChange("cost_efficiency", v)} 
                color="bg-green-500"
              />
              <SliderControl 
                label="Regional Equity" 
                icon={<Users size={16} />} 
                value={priorities.regional_equity} 
                onChange={(v) => handleSliderChange("regional_equity", v)} 
                color="bg-purple-500"
              />
              <SliderControl 
                label="Climate Resilience" 
                icon={<ShieldCheck size={16} />} 
                value={priorities.climate_resilience} 
                onChange={(v) => handleSliderChange("climate_resilience", v)} 
                color="bg-teal-500"
              />
              <SliderControl 
                label="Population Impact" 
                icon={<Users size={16} />} 
                value={priorities.population_impact} 
                onChange={(v) => handleSliderChange("population_impact", v)} 
                color="bg-orange-500"
              />
            </div>

            <button
              onClick={handleOptimize}
              disabled={loading}
              className="w-full py-3 bg-slate-900 hover:bg-slate-800 text-white rounded-xl font-semibold shadow-lg shadow-slate-900/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2"
            >
              {loading ? (
                <>Processing...</>
              ) : (
                <>Run Optimization <ArrowRight size={18} /></>
              )}
            </button>
          </div>

          {/* Results Panel */}
          <div className="flex-1 p-6 bg-white">
            {!results ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-400 space-y-4">
                <div className="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center">
                  <Calculator size={32} className="opacity-20" />
                </div>
                <p className="text-sm">Configure parameters and run optimization to see results.</p>
              </div>
            ) : (
              <motion.div 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="space-y-6"
              >
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <ResultCard label="Assets Funded" value={results.assets_funded_count} subtext={`of ${results.total_assets_considered}`} />
                  <ResultCard label="Total Cost" value={formatCurrency(results.total_cost)} highlight />
                  <ResultCard label="Risk Reduction" value={`-${results.total_risk_reduction.toFixed(1)}`} color="text-green-600" />
                  <ResultCard label="Pop. Protected" value={results.population_protected.toLocaleString()} />
                </div>

                <div className="bg-slate-50 rounded-xl p-4 border border-slate-100">
                  <h3 className="text-sm font-semibold text-slate-700 mb-4">Regional Distribution</h3>
                  <div className="space-y-3">
                    {Object.entries(results.regional_distribution).map(([region, count]: [string, any]) => (
                      <div key={region} className="flex items-center gap-3">
                        <span className="text-xs font-medium text-slate-500 w-8">{region.substring(0, 2).toUpperCase()}</span>
                        <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden">
                          <motion.div 
                            initial={{ width: 0 }}
                            animate={{ width: `${(count / results.assets_funded_count) * 100}%` }}
                            className="h-full bg-blue-500 rounded-full"
                          />
                        </div>
                        <span className="text-xs font-bold text-slate-700 w-8 text-right">{count}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <h3 className="text-sm font-semibold text-slate-700 mb-4">Top Funded Projects</h3>
                  <div className="border border-slate-100 rounded-xl overflow-hidden">
                    <table className="w-full text-sm text-left">
                      <thead className="bg-slate-50 text-slate-500 font-medium">
                        <tr>
                          <th className="p-3 pl-4">Asset</th>
                          <th className="p-3">Cost</th>
                          <th className="p-3 text-right pr-4">Score</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {results.allocations.slice(0, 5).map((alloc: any) => (
                          <tr key={alloc.asset_id} className="hover:bg-slate-50/50">
                            <td className="p-3 pl-4 font-medium text-slate-700">{alloc.asset_name}</td>
                            <td className="p-3 text-slate-600">{formatCurrency(alloc.cost)}</td>
                            <td className="p-3 text-right pr-4 font-mono text-xs text-blue-600 bg-blue-50 rounded px-1.5 py-0.5 w-fit ml-auto">
                              {alloc.score.toFixed(1)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </motion.div>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
}

interface SliderControlProps {
  label: string;
  icon: ReactNode;
  value: number;
  onChange: (value: number) => void;
  color?: string;
}

function SliderControl({ label, icon, value, onChange, color }: SliderControlProps) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center text-sm">
        <span className="flex items-center gap-2 text-slate-600 font-medium">{icon} {label}</span>
        <span className="font-bold text-slate-900">{value}%</span>
      </div>
      <input
        type="range"
        min="0"
        max="100"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className={clsx("w-full h-2 rounded-lg appearance-none cursor-pointer bg-slate-200 accent-slate-900", color && `accent-${color.split('-')[1]}-500`)}
      />
    </div>
  );
}

interface ResultCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  highlight?: boolean;
  color?: string;
}

function ResultCard({ label, value, subtext, highlight, color }: ResultCardProps) {
  return (
    <div className={clsx("p-4 rounded-xl border", highlight ? "bg-blue-50 border-blue-100" : "bg-white border-slate-100")}>
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className={clsx("text-lg font-bold", color ? color : "text-slate-900")}>{value}</p>
      {subtext && <p className="text-[10px] text-slate-400">{subtext}</p>}
    </div>
  );
}
