"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import {
  DollarSign,
  TrendingUp,
  AlertTriangle,
  Download,
  RefreshCw,
  ChevronRight,
  Building2,
  Target,
  Zap,
  BarChart3,
  Map,
  FileText,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Types
interface Bridge {
  id: string;
  name: string;
  region: string;
  latitude: number;
  longitude: number;
  condition: string;
  risk_score: number;
  estimated_repair_cost: number;
  cost_display: string;
  cost_range_low: number;
  cost_range_high: number;
  risk_cost_ratio: number;
  highway: string | null;
  structure_type: string | null;
  year_built: string | null;
  is_critical: boolean;
  is_high_risk: boolean;
  justification: string;
  rank?: number;
}

interface RoadSection {
  id: string;
  type: "road";
  highway: string;
  section_description: string;
  region: string;
  section_from: string | null;
  section_to: string | null;
  km_start: number | null;
  km_end: number | null;
  length_km: number;
  latitude: number | null;
  longitude: number | null;
  condition: string;
  pci: number | null;
  dmi: number | null;
  iri: number | null;
  pavement_type: string | null;
  aadt: number | null;
  risk_score: number;
  estimated_repair_cost: number;
  cost_display: string;
  cost_per_km: number;
  cost_range_low: number;
  cost_range_high: number;
  risk_cost_ratio: number;
  is_critical: boolean;
  is_high_risk: boolean;
  justification: string;
  rank?: number;
}

interface OptimizationSummary {
  bridges_selected: number;
  roads_selected: number;
  total_infrastructure_selected: number;
  total_cost: number;
  cost_display: string;
  budget_remaining: number;
  budget_utilization_percent: number;
  total_risk_reduction: number;
  risk_reduction_percent: number;
  avg_risk_score: number;
  critical_bridges_funded: number;
  critical_bridges_unfunded: number;
  critical_roads_funded: number;
  critical_roads_unfunded: number;
}

interface OptimizationResult {
  region: string;
  budget: number;
  budget_display: string;
  selected_bridges: Bridge[];
  selected_roads: RoadSection[];
  summary: OptimizationSummary;
  unfunded_critical_bridges: Bridge[];
  unfunded_critical_roads: RoadSection[];
  warnings: string[];
  algorithm: string;
}

interface ComparisonResult {
  region: string;
  budget: number;
  ai_optimized: {
    bridges_repaired: number;
    total_spent: number;
    budget_utilization: number;
    risk_reduction: number;
    risk_reduction_percent: number;
    avg_risk_score: number;
    bridges: Bridge[];
    critical_funded: number;
  };
  traditional: {
    bridges_repaired: number;
    total_spent: number;
    risk_reduction: number;
    risk_reduction_percent: number;
    avg_risk_score: number;
    bridges: Bridge[];
  };
  improvement: {
    percent: number;
    description: string;
  };
}

interface HighRiskBridgesResult {
  region: string;
  total_high_risk_bridges: number;
  critical_bridges: number;
  total_repair_cost: number;
  total_repair_cost_display: string;
  critical_repair_cost: number;
  critical_repair_cost_display: string;
  bridges: Bridge[];
}

interface HighRiskRoadsResult {
  region: string;
  total_high_risk_roads: number;
  critical_roads: number;
  total_repair_cost: number;
  total_repair_cost_display: string;
  critical_repair_cost: number;
  critical_repair_cost_display: string;
  total_length_km: number;
  roads: RoadSection[];
}

interface HighRiskInfrastructureResult {
  region: string;
  summary: {
    total_infrastructure_count: number;
    total_critical_count: number;
    total_repair_cost: number;
    total_repair_cost_display: string;
    total_critical_repair_cost: number;
    total_critical_repair_cost_display: string;
  };
  bridges: HighRiskBridgesResult;
  roads: HighRiskRoadsResult;
}

// Regions list
const REGIONS = [
  "Ontario",
  "Quebec",
  "British Columbia",
  "Alberta",
  "Manitoba",
  "Saskatchewan",
  "Nova Scotia",
  "New Brunswick",
  "Newfoundland and Labrador",
  "Prince Edward Island",
  "Northwest Territories",
  "Yukon",
  "Nunavut",
];

// Budget presets
const BUDGET_PRESETS = [
  { label: "$25M", value: 25_000_000 },
  { label: "$50M", value: 50_000_000 },
  { label: "$75M", value: 75_000_000 },
  { label: "$100M", value: 100_000_000 },
  { label: "$150M", value: 150_000_000 },
  { label: "$200M", value: 200_000_000 },
];

export default function FundingOptimizer() {
  // State
  const [region, setRegion] = useState("Ontario");
  const [budget, setBudget] = useState(50_000_000);
  const [includeMediumRisk, setIncludeMediumRisk] = useState(false);
  const [includeRoads, setIncludeRoads] = useState(true);
  const [displayMode, setDisplayMode] = useState<"compact" | "full">("compact");
  
  // Data state
  const [optimization, setOptimization] = useState<OptimizationResult | null>(null);
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [highRiskBridges, setHighRiskBridges] = useState<HighRiskBridgesResult | null>(null);
  const [highRiskRoads, setHighRiskRoads] = useState<HighRiskRoadsResult | null>(null);
  const [highRiskInfra, setHighRiskInfra] = useState<HighRiskInfrastructureResult | null>(null);
  
  // Loading state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Active view
  const [activeView, setActiveView] = useState<"optimization" | "comparison" | "all-infrastructure">("optimization");
  
  // Infrastructure filter for all-infrastructure view
  const [infraFilter, setInfraFilter] = useState<"all" | "bridges" | "roads">("all");
  
  // Debounce timer
  const [debounceTimer, setDebounceTimer] = useState<NodeJS.Timeout | null>(null);

  // Fetch optimization results
  const fetchOptimization = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const [optRes, compRes] = await Promise.all([
        fetch(
          `${API_BASE}/api/funding/optimize?region=${encodeURIComponent(region)}&budget=${budget}&include_medium_risk=${includeMediumRisk}&include_roads=${includeRoads}`
        ),
        fetch(
          `${API_BASE}/api/funding/compare?region=${encodeURIComponent(region)}&budget=${budget}`
        ),
      ]);
      
      if (!optRes.ok || !compRes.ok) {
        throw new Error("Failed to fetch optimization data");
      }
      
      const optData = await optRes.json();
      const compData = await compRes.json();
      
      setOptimization(optData);
      setComparison(compData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [region, budget, includeMediumRisk, includeRoads]);

  // Fetch all high-risk infrastructure
  const fetchHighRiskInfrastructure = useCallback(async () => {
    try {
      const [bridgesRes, roadsRes, infraRes] = await Promise.all([
        fetch(`${API_BASE}/api/funding/bridges?region=${encodeURIComponent(region)}`),
        fetch(`${API_BASE}/api/funding/roads?region=${encodeURIComponent(region)}`),
        fetch(`${API_BASE}/api/funding/infrastructure?region=${encodeURIComponent(region)}`),
      ]);
      
      if (bridgesRes.ok) {
        const data = await bridgesRes.json();
        setHighRiskBridges(data);
      }
      if (roadsRes.ok) {
        const data = await roadsRes.json();
        setHighRiskRoads(data);
      }
      if (infraRes.ok) {
        const data = await infraRes.json();
        setHighRiskInfra(data);
      }
    } catch (err) {
      console.error("Error fetching high-risk infrastructure:", err);
    }
  }, [region]);

  // Initial load
  useEffect(() => {
    fetchOptimization();
    fetchHighRiskInfrastructure();
  }, [region]); // Only on region change

  // Debounced budget change
  useEffect(() => {
    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }
    
    const timer = setTimeout(() => {
      fetchOptimization();
    }, 500); // 500ms debounce
    
    setDebounceTimer(timer);
    
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [budget, includeMediumRisk, includeRoads]);

  // Handle budget slider change
  const handleBudgetChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value, 10);
    setBudget(value);
  };

  // Format currency
  const formatCurrency = (value: number): string => {
    if (value >= 1_000_000_000) {
      return `$${(value / 1_000_000_000).toFixed(1)}B`;
    }
    if (value >= 1_000_000) {
      return `$${(value / 1_000_000).toFixed(1)}M`;
    }
    return `$${value.toLocaleString()}`;
  };

  // Export CSV
  const handleExportCSV = async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/funding/export?region=${encodeURIComponent(region)}&budget=${budget}&format=csv&include_roads=${includeRoads}`
      );
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `Budget_Proposal_${region}_${new Date().toISOString().split("T")[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.error("Export failed:", err);
    }
  };

  // Export JSON
  const handleExportJSON = async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/funding/export?region=${encodeURIComponent(region)}&budget=${budget}&format=json&include_roads=${includeRoads}`
      );
      if (res.ok) {
        const data = await res.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `Budget_Proposal_${region}_${new Date().toISOString().split("T")[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.error("Export failed:", err);
    }
  };

  // Get condition color
  const getConditionColor = (condition: string) => {
    switch (condition.toLowerCase()) {
      case "critical":
        return "bg-red-100 text-red-800";
      case "poor":
        return "bg-orange-100 text-orange-800";
      case "fair":
        return "bg-yellow-100 text-yellow-800";
      case "good":
        return "bg-green-100 text-green-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  // Render KPI Card
  const KPICard = ({
    icon,
    label,
    value,
    subValue,
    color = "blue",
    animate = false,
  }: {
    icon: React.ReactNode;
    label: string;
    value: string | number;
    subValue?: string;
    color?: string;
    animate?: boolean;
  }) => {
    const colorClasses = {
      blue: "bg-blue-50 text-blue-600",
      green: "bg-green-50 text-green-600",
      orange: "bg-orange-50 text-orange-600",
      red: "bg-red-50 text-red-600",
      purple: "bg-purple-50 text-purple-600",
    };

    return (
      <motion.div
        initial={animate ? { scale: 0.95, opacity: 0 } : false}
        animate={{ scale: 1, opacity: 1 }}
        className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm"
      >
        <div className="flex items-start justify-between">
          <div className={clsx("p-2 rounded-lg", colorClasses[color as keyof typeof colorClasses])}>
            {icon}
          </div>
        </div>
        <div className="mt-4">
          <p className="text-2xl font-bold text-slate-900">{value}</p>
          <p className="text-sm text-slate-500 mt-1">{label}</p>
          {subValue && (
            <p className="text-xs text-slate-400 mt-1">{subValue}</p>
          )}
        </div>
      </motion.div>
    );
  };

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
              <Target className="text-indigo-600" size={28} />
              Funding Scenario Optimizer
            </h1>
            <p className="text-slate-500 mt-1">
              AI-powered infrastructure investment optimization
            </p>
          </div>
          
          {/* Region Selector */}
          <div className="flex items-center gap-3">
            <select
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="px-4 py-2 rounded-lg border border-slate-200 bg-white text-slate-700 font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              {REGIONS.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
            
            <button
              onClick={() => {
                fetchOptimization();
                fetchHighRiskInfrastructure();
              }}
              disabled={loading}
              className="p-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            >
              <RefreshCw size={20} className={loading ? "animate-spin" : ""} />
            </button>
          </div>
        </div>

        {/* Budget Control Panel */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
          <div className="flex flex-col lg:flex-row lg:items-center gap-6">
            {/* Budget Slider */}
            <div className="flex-1">
              <div className="flex items-center justify-between mb-3">
                <label className="text-sm font-semibold text-slate-700">
                  Available Budget
                </label>
                <div className="flex items-center gap-2">
                  <DollarSign size={18} className="text-green-600" />
                  <span className="text-2xl font-bold text-slate-900">
                    {formatCurrency(budget)}
                  </span>
                </div>
              </div>
              
              <input
                type="range"
                min={0}
                max={200_000_000}
                step={1_000_000}
                value={budget}
                onChange={handleBudgetChange}
                className="w-full h-3 rounded-full appearance-none cursor-pointer bg-gradient-to-r from-slate-200 via-indigo-200 to-indigo-400"
                style={{
                  background: `linear-gradient(to right, #6366f1 0%, #6366f1 ${(budget / 200_000_000) * 100}%, #e2e8f0 ${(budget / 200_000_000) * 100}%, #e2e8f0 100%)`,
                }}
              />
              
              <div className="flex justify-between mt-2 text-xs text-slate-400">
                <span>$0</span>
                <span>$50M</span>
                <span>$100M</span>
                <span>$150M</span>
                <span>$200M</span>
              </div>
            </div>
            
            {/* Quick Presets */}
            <div className="flex flex-wrap gap-2">
              {BUDGET_PRESETS.map((preset) => (
                <button
                  key={preset.value}
                  onClick={() => setBudget(preset.value)}
                  className={clsx(
                    "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                    budget === preset.value
                      ? "bg-indigo-600 text-white"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  )}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>
          
          {/* Options */}
          <div className="flex flex-wrap items-center gap-6 mt-4 pt-4 border-t border-slate-100">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={includeRoads}
                onChange={(e) => setIncludeRoads(e.target.checked)}
                className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span className="text-sm text-slate-600">
                Include Road Sections
              </span>
            </label>
            
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={includeMediumRisk}
                onChange={(e) => setIncludeMediumRisk(e.target.checked)}
                className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span className="text-sm text-slate-600">
                Include Medium-Risk (55-70 score)
              </span>
            </label>
          </div>
          
          {/* Infrastructure Summary */}
          <div className="flex flex-wrap items-center gap-4 mt-3 text-sm text-slate-500">
            {highRiskBridges && (
              <div>
                <span className="font-medium text-slate-700">
                  {highRiskBridges.total_high_risk_bridges}
                </span>{" "}
                bridges ({highRiskBridges.critical_bridges} critical) •{" "}
                <span className="font-medium text-slate-700">
                  {highRiskBridges.total_repair_cost_display}
                </span>
              </div>
            )}
            {highRiskRoads && (
              <div>
                <span className="font-medium text-slate-700">
                  {highRiskRoads.total_high_risk_roads}
                </span>{" "}
                road sections ({highRiskRoads.critical_roads} critical) •{" "}
                <span className="font-medium text-slate-700">
                  {highRiskRoads.total_repair_cost_display}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Warnings */}
        <AnimatePresence>
          {optimization?.warnings && optimization.warnings.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="bg-amber-50 border border-amber-200 rounded-xl p-4"
            >
              {optimization.warnings.map((warning, i) => (
                <div key={i} className="flex items-start gap-3">
                  <AlertTriangle className="text-amber-600 flex-shrink-0 mt-0.5" size={20} />
                  <div>
                    <p className="text-amber-800 font-medium">{warning}</p>
                    {optimization.unfunded_critical_bridges.length > 0 && (
                      <p className="text-amber-700 text-sm mt-1">
                        Recommendation: Increase budget to{" "}
                        <span className="font-semibold">
                          {formatCurrency(
                            budget +
                              optimization.unfunded_critical_bridges.reduce(
                                (sum, b) => sum + b.estimated_repair_cost,
                                0
                              )
                          )}
                        </span>{" "}
                        to address all critical bridges.
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* KPI Summary */}
        {optimization && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <KPICard
              icon={<Building2 size={20} />}
              label="Infrastructure Selected"
              value={optimization.summary.total_infrastructure_selected || (optimization.summary.bridges_selected + optimization.summary.roads_selected)}
              subValue={`${optimization.summary.bridges_selected} bridges, ${optimization.summary.roads_selected} roads`}
              color="blue"
              animate
            />
            <KPICard
              icon={<DollarSign size={20} />}
              label="Budget Used"
              value={optimization.summary.cost_display}
              subValue={`${optimization.summary.budget_utilization_percent}% utilized`}
              color="green"
              animate
            />
            <KPICard
              icon={<TrendingUp size={20} />}
              label="Risk Reduction"
              value={`${optimization.summary.risk_reduction_percent}%`}
              subValue={`${optimization.summary.total_risk_reduction.toFixed(0)} total points`}
              color="purple"
              animate
            />
            <KPICard
              icon={<AlertTriangle size={20} />}
              label="Critical Bridges"
              value={`${optimization.summary.critical_bridges_funded}/${optimization.summary.critical_bridges_funded + optimization.summary.critical_bridges_unfunded}`}
              subValue={
                optimization.summary.critical_bridges_unfunded > 0
                  ? `${optimization.summary.critical_bridges_unfunded} unfunded`
                  : "All funded"
              }
              color={optimization.summary.critical_bridges_unfunded > 0 ? "red" : "green"}
              animate
            />
            <KPICard
              icon={<AlertTriangle size={20} />}
              label="Critical Roads"
              value={`${optimization.summary.critical_roads_funded}/${optimization.summary.critical_roads_funded + optimization.summary.critical_roads_unfunded}`}
              subValue={
                optimization.summary.critical_roads_unfunded > 0
                  ? `${optimization.summary.critical_roads_unfunded} unfunded`
                  : "All funded"
              }
              color={optimization.summary.critical_roads_unfunded > 0 ? "orange" : "green"}
              animate
            />
          </div>
        )}

        {/* View Tabs */}
        <div className="flex gap-2 border-b border-slate-200">
          {[
            { id: "optimization", label: "AI Optimized Selection", icon: <Zap size={16} /> },
            { id: "comparison", label: "AI vs Traditional", icon: <BarChart3 size={16} /> },
            { id: "all-infrastructure", label: "All High-Risk Infrastructure", icon: <Map size={16} /> },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveView(tab.id as typeof activeView)}
              className={clsx(
                "flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors",
                activeView === tab.id
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              )}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
          
          {/* Export Buttons */}
          <div className="ml-auto flex items-center gap-2 pb-2">
            <button
              onClick={handleExportCSV}
              className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-slate-600 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
            >
              <Download size={16} />
              CSV
            </button>
            <button
              onClick={handleExportJSON}
              className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-slate-600 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
            >
              <FileText size={16} />
              JSON
            </button>
          </div>
        </div>

        {/* Content Area */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <RefreshCw className="animate-spin text-indigo-600" size={32} />
              <span className="ml-3 text-slate-600">Optimizing...</span>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center py-20 text-red-600">
              <AlertTriangle size={24} className="mr-2" />
              {error}
            </div>
          ) : activeView === "optimization" ? (
            /* AI Optimized Selection View */
            <div>
              <div className="p-4 bg-gradient-to-r from-indigo-50 to-purple-50 border-b border-slate-100">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-slate-900">
                      AI-Optimized Infrastructure Selection
                    </h3>
                    <p className="text-sm text-slate-500">
                      Infrastructure ranked by Risk-to-Cost Ratio (RCR) for maximum impact
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-slate-500">Algorithm</p>
                    <p className="font-medium text-indigo-600">
                      {optimization?.algorithm}
                    </p>
                  </div>
                </div>
              </div>
              
              {/* Selected Bridges */}
              {optimization?.selected_bridges && optimization.selected_bridges.length > 0 && (
                <div>
                  <div className="px-4 py-2 bg-blue-50 border-b border-blue-100">
                    <h4 className="text-sm font-semibold text-blue-800">
                      🌉 Bridges ({optimization.selected_bridges.length})
                    </h4>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-slate-50 border-b border-slate-200">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Rank
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Bridge
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Condition
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Risk Score
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Est. Cost
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            RCR
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Justification
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {optimization.selected_bridges.map((bridge, idx) => (
                          <motion.tr
                            key={bridge.id}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: idx * 0.03 }}
                            className={clsx(
                              "hover:bg-slate-50 transition-colors",
                              bridge.is_critical && "bg-red-50/50"
                            )}
                          >
                            <td className="px-4 py-3">
                              <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-indigo-100 text-indigo-700 font-bold text-sm">
                                {bridge.rank}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <div>
                                <p className="font-medium text-slate-900">
                                  {bridge.name}
                                </p>
                                <p className="text-xs text-slate-500">
                                  {bridge.id}
                                  {bridge.highway && ` • ${bridge.highway}`}
                                </p>
                              </div>
                            </td>
                            <td className="px-4 py-3">
                              <span
                                className={clsx(
                                  "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
                                  getConditionColor(bridge.condition)
                                )}
                              >
                                {bridge.condition}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2">
                                <div className="w-16 h-2 bg-slate-100 rounded-full overflow-hidden">
                                  <div
                                    className={clsx(
                                      "h-full rounded-full",
                                      bridge.risk_score >= 85
                                        ? "bg-red-500"
                                        : bridge.risk_score >= 70
                                        ? "bg-orange-500"
                                        : "bg-yellow-500"
                                    )}
                                    style={{ width: `${bridge.risk_score}%` }}
                                  />
                                </div>
                                <span className="font-medium text-slate-900">
                                  {bridge.risk_score}
                                </span>
                              </div>
                            </td>
                            <td className="px-4 py-3">
                              <p className="font-medium text-slate-900">
                                {bridge.cost_display}
                              </p>
                              <p className="text-xs text-slate-400">
                                ±20%: {formatCurrency(bridge.cost_range_low)} -{" "}
                                {formatCurrency(bridge.cost_range_high)}
                              </p>
                            </td>
                            <td className="px-4 py-3">
                              <span
                                className={clsx(
                                  "font-bold",
                                  bridge.risk_cost_ratio >= 20
                                ? "text-green-600"
                                : bridge.risk_cost_ratio >= 15
                                ? "text-blue-600"
                                : "text-slate-600"
                            )}
                          >
                            {bridge.risk_cost_ratio.toFixed(1)}
                          </span>
                        </td>
                        <td className="px-4 py-3 max-w-xs">
                          <p className="text-sm text-slate-600 truncate">
                            {bridge.justification}
                          </p>
                        </td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
              </div>
              )}
              
              {/* No bridges message */}
              {optimization?.selected_bridges?.length === 0 && includeRoads === false && (
                <div className="py-10 text-center text-slate-500">
                  <Building2 size={48} className="mx-auto mb-4 text-slate-300" />
                  <p>No bridges selected. Increase budget to see recommendations.</p>
                </div>
              )}
              
              {/* Selected Roads */}
              {optimization?.selected_roads && optimization.selected_roads.length > 0 && (
                <div>
                  <div className="px-4 py-2 bg-amber-50 border-b border-amber-100 border-t">
                    <h4 className="text-sm font-semibold text-amber-800">
                      🛣️ Road Sections ({optimization.selected_roads.length})
                    </h4>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-slate-50 border-b border-slate-200">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Rank
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Highway / Section
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Condition
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Risk Score
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Length
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Est. Cost
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            RCR
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Justification
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {optimization.selected_roads.map((road, idx) => (
                          <motion.tr
                            key={road.id}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: idx * 0.03 }}
                            className={clsx(
                              "hover:bg-slate-50 transition-colors",
                              road.is_critical && "bg-red-50/50"
                            )}
                          >
                            <td className="px-4 py-3">
                              <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-amber-100 text-amber-700 font-bold text-sm">
                                {road.rank}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <div>
                                <p className="font-medium text-slate-900">
                                  Highway {road.highway}
                                </p>
                                <p className="text-xs text-slate-500">
                                  {road.section_description}
                                </p>
                              </div>
                            </td>
                            <td className="px-4 py-3">
                              <span
                                className={clsx(
                                  "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
                                  getConditionColor(road.condition)
                                )}
                              >
                                {road.condition}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2">
                                <div className="w-16 h-2 bg-slate-100 rounded-full overflow-hidden">
                                  <div
                                    className={clsx(
                                      "h-full rounded-full",
                                      road.risk_score >= 85
                                        ? "bg-red-500"
                                        : road.risk_score >= 70
                                        ? "bg-orange-500"
                                        : "bg-yellow-500"
                                    )}
                                    style={{ width: `${road.risk_score}%` }}
                                  />
                                </div>
                                <span className="font-medium text-slate-900">
                                  {road.risk_score}
                                </span>
                              </div>
                            </td>
                            <td className="px-4 py-3">
                              <p className="font-medium text-slate-900">
                                {road.length_km.toFixed(1)} km
                              </p>
                            </td>
                            <td className="px-4 py-3">
                              <p className="font-medium text-slate-900">
                                {road.cost_display}
                              </p>
                              <p className="text-xs text-slate-400">
                                ${(road.cost_per_km / 1000).toFixed(0)}K/km
                              </p>
                            </td>
                            <td className="px-4 py-3">
                              <span
                                className={clsx(
                                  "font-bold",
                                  road.risk_cost_ratio >= 20
                                    ? "text-green-600"
                                    : road.risk_cost_ratio >= 15
                                    ? "text-blue-600"
                                    : "text-slate-600"
                                )}
                              >
                                {road.risk_cost_ratio.toFixed(1)}
                              </span>
                            </td>
                            <td className="px-4 py-3 max-w-xs">
                              <p className="text-sm text-slate-600 truncate">
                                {road.justification}
                              </p>
                            </td>
                          </motion.tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              
              {/* No infrastructure message */}
              {optimization?.selected_bridges?.length === 0 && optimization?.selected_roads?.length === 0 && (
                <div className="py-20 text-center text-slate-500">
                  <Building2 size={48} className="mx-auto mb-4 text-slate-300" />
                  <p>No infrastructure selected. Increase budget to see recommendations.</p>
                </div>
              )}
            </div>
          ) : activeView === "comparison" ? (
            /* AI vs Traditional Comparison View */
            comparison && (
              <div className="p-6">
                {/* Improvement Banner */}
                <div
                  className={clsx(
                    "rounded-xl p-6 mb-6 text-center",
                    comparison.improvement.percent > 0
                      ? "bg-gradient-to-r from-green-500 to-emerald-600"
                      : "bg-gradient-to-r from-slate-500 to-slate-600"
                  )}
                >
                  <p className="text-white/80 text-sm font-medium uppercase tracking-wide">
                    AI Optimization Improvement
                  </p>
                  <p className="text-4xl font-bold text-white mt-2">
                    {comparison.improvement.percent > 0 ? "+" : ""}
                    {comparison.improvement.percent}%
                  </p>
                  <p className="text-white/90 mt-2">
                    {comparison.improvement.description}
                  </p>
                </div>

                {/* Side by Side Comparison */}
                <div className="grid md:grid-cols-2 gap-6">
                  {/* Traditional Approach */}
                  <div className="border border-slate-200 rounded-xl overflow-hidden">
                    <div className="bg-slate-100 px-4 py-3 border-b border-slate-200">
                      <h4 className="font-semibold text-slate-700 flex items-center gap-2">
                        <XCircle size={18} className="text-slate-400" />
                        Traditional Approach
                      </h4>
                      <p className="text-xs text-slate-500">
                        Sort by age (oldest first)
                      </p>
                    </div>
                    <div className="p-4 space-y-4">
                      <div className="flex justify-between">
                        <span className="text-slate-600">Bridges Repaired</span>
                        <span className="font-bold text-slate-900">
                          {comparison.traditional.bridges_repaired}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Budget Spent</span>
                        <span className="font-bold text-slate-900">
                          {formatCurrency(comparison.traditional.total_spent)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Risk Reduction</span>
                        <span className="font-bold text-slate-900">
                          {comparison.traditional.risk_reduction_percent}%
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Avg Risk Score</span>
                        <span className="font-bold text-slate-900">
                          {comparison.traditional.avg_risk_score}
                        </span>
                      </div>
                      
                      {/* Risk Reduction Bar */}
                      <div className="pt-4 border-t border-slate-100">
                        <p className="text-xs text-slate-500 mb-2">
                          Risk Reduction Visual
                        </p>
                        <div className="h-4 bg-slate-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-slate-400 rounded-full transition-all duration-500"
                            style={{
                              width: `${comparison.traditional.risk_reduction_percent}%`,
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* AI Approach */}
                  <div className="border border-indigo-200 rounded-xl overflow-hidden bg-indigo-50/30">
                    <div className="bg-indigo-100 px-4 py-3 border-b border-indigo-200">
                      <h4 className="font-semibold text-indigo-700 flex items-center gap-2">
                        <CheckCircle2 size={18} className="text-indigo-600" />
                        AI-Optimized Approach
                      </h4>
                      <p className="text-xs text-indigo-600">
                        Sort by Risk-to-Cost Ratio
                      </p>
                    </div>
                    <div className="p-4 space-y-4">
                      <div className="flex justify-between">
                        <span className="text-slate-600">Bridges Repaired</span>
                        <span className="font-bold text-indigo-700">
                          {comparison.ai_optimized.bridges_repaired}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Budget Spent</span>
                        <span className="font-bold text-indigo-700">
                          {formatCurrency(comparison.ai_optimized.total_spent)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Risk Reduction</span>
                        <span className="font-bold text-indigo-700">
                          {comparison.ai_optimized.risk_reduction_percent}%
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-600">Avg Risk Score</span>
                        <span className="font-bold text-indigo-700">
                          {comparison.ai_optimized.avg_risk_score}
                        </span>
                      </div>
                      
                      {/* Risk Reduction Bar */}
                      <div className="pt-4 border-t border-indigo-100">
                        <p className="text-xs text-indigo-500 mb-2">
                          Risk Reduction Visual
                        </p>
                        <div className="h-4 bg-indigo-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-indigo-500 rounded-full transition-all duration-500"
                            style={{
                              width: `${comparison.ai_optimized.risk_reduction_percent}%`,
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Detailed Comparison Table */}
                <div className="mt-6 border border-slate-200 rounded-xl overflow-hidden">
                  <div className="bg-slate-50 px-4 py-3 border-b border-slate-200">
                    <h4 className="font-semibold text-slate-700">
                      Metric Comparison
                    </h4>
                  </div>
                  <table className="w-full">
                    <thead className="bg-slate-50 border-b border-slate-200">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                          Metric
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-semibold text-slate-500 uppercase">
                          Traditional
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-semibold text-indigo-600 uppercase">
                          AI Optimized
                        </th>
                        <th className="px-4 py-3 text-center text-xs font-semibold text-slate-500 uppercase">
                          Difference
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      <tr>
                        <td className="px-4 py-3 font-medium text-slate-700">
                          Bridges Repaired
                        </td>
                        <td className="px-4 py-3 text-center text-slate-600">
                          {comparison.traditional.bridges_repaired}
                        </td>
                        <td className="px-4 py-3 text-center font-medium text-indigo-600">
                          {comparison.ai_optimized.bridges_repaired}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span
                            className={clsx(
                              "font-medium",
                              comparison.ai_optimized.bridges_repaired >
                                comparison.traditional.bridges_repaired
                                ? "text-green-600"
                                : "text-slate-500"
                            )}
                          >
                            +
                            {comparison.ai_optimized.bridges_repaired -
                              comparison.traditional.bridges_repaired}
                          </span>
                        </td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-medium text-slate-700">
                          Risk Reduction
                        </td>
                        <td className="px-4 py-3 text-center text-slate-600">
                          {comparison.traditional.risk_reduction.toFixed(0)}
                        </td>
                        <td className="px-4 py-3 text-center font-medium text-indigo-600">
                          {comparison.ai_optimized.risk_reduction.toFixed(0)}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span className="font-medium text-green-600">
                            +
                            {(
                              comparison.ai_optimized.risk_reduction -
                              comparison.traditional.risk_reduction
                            ).toFixed(0)}
                          </span>
                        </td>
                      </tr>
                      <tr>
                        <td className="px-4 py-3 font-medium text-slate-700">
                          Average Risk Score
                        </td>
                        <td className="px-4 py-3 text-center text-slate-600">
                          {comparison.traditional.avg_risk_score}
                        </td>
                        <td className="px-4 py-3 text-center font-medium text-indigo-600">
                          {comparison.ai_optimized.avg_risk_score}
                        </td>
                        <td className="px-4 py-3 text-center">
                          <span
                            className={clsx(
                              "font-medium",
                              comparison.ai_optimized.avg_risk_score >
                                comparison.traditional.avg_risk_score
                                ? "text-green-600"
                                : "text-slate-500"
                            )}
                          >
                            {comparison.ai_optimized.avg_risk_score >
                            comparison.traditional.avg_risk_score
                              ? "+"
                              : ""}
                            {(
                              comparison.ai_optimized.avg_risk_score -
                              comparison.traditional.avg_risk_score
                            ).toFixed(1)}
                          </span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )
          ) : (
            /* All High-Risk Infrastructure View */
            <div>
              <div className="p-4 bg-slate-50 border-b border-slate-200">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold text-slate-900">
                      All High-Risk Infrastructure in {region}
                    </h3>
                    <p className="text-sm text-slate-500">
                      {(highRiskBridges?.total_high_risk_bridges || 0) + (highRiskRoads?.total_high_risk_roads || 0)} items with
                      risk score &gt; 70
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-slate-500">
                      Total Cost to Repair All
                    </p>
                    <p className="text-xl font-bold text-slate-900">
                      {formatCurrency((highRiskBridges?.total_repair_cost || 0) + (highRiskRoads?.total_repair_cost || 0))}
                    </p>
                  </div>
                </div>
                
                {/* Infrastructure Filter */}
                <div className="flex gap-2 mt-3">
                  {[
                    { id: "all", label: "All" },
                    { id: "bridges", label: `Bridges (${highRiskBridges?.total_high_risk_bridges || 0})` },
                    { id: "roads", label: `Roads (${highRiskRoads?.total_high_risk_roads || 0})` },
                  ].map((filter) => (
                    <button
                      key={filter.id}
                      onClick={() => setInfraFilter(filter.id as typeof infraFilter)}
                      className={clsx(
                        "px-3 py-1 text-sm rounded-lg transition-colors",
                        infraFilter === filter.id
                          ? "bg-indigo-600 text-white"
                          : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
                      )}
                    >
                      {filter.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Bridges Table */}
              {(infraFilter === "all" || infraFilter === "bridges") && highRiskBridges && highRiskBridges.bridges.length > 0 && (
                <div>
                  <div className="px-4 py-2 bg-blue-50 border-b border-blue-100">
                    <h4 className="text-sm font-semibold text-blue-800">
                      🌉 Bridges ({highRiskBridges.total_high_risk_bridges}) - {highRiskBridges.total_repair_cost_display}
                    </h4>
                  </div>
                  <div className="overflow-x-auto max-h-[350px] overflow-y-auto">
                    <table className="w-full">
                      <thead className="bg-slate-50 border-b border-slate-200 sticky top-0">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Bridge
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Condition
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Risk Score
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Est. Cost
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            RCR
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Year Built
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {highRiskBridges.bridges.map((bridge) => (
                          <tr
                            key={bridge.id}
                            className={clsx(
                              "hover:bg-slate-50 transition-colors",
                              bridge.is_critical && "bg-red-50/50"
                            )}
                          >
                            <td className="px-4 py-3">
                              <div>
                                <p className="font-medium text-slate-900">
                                  {bridge.name}
                                </p>
                                <p className="text-xs text-slate-500">
                                  {bridge.id}
                                  {bridge.highway && ` • ${bridge.highway}`}
                                </p>
                              </div>
                            </td>
                            <td className="px-4 py-3">
                              <span
                                className={clsx(
                                  "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
                                  getConditionColor(bridge.condition)
                                )}
                              >
                                {bridge.condition}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2">
                                <span
                                  className={clsx(
                                    "font-bold",
                                    bridge.risk_score >= 85
                                      ? "text-red-600"
                                      : bridge.risk_score >= 70
                                      ? "text-orange-600"
                                      : "text-yellow-600"
                                  )}
                                >
                                  {bridge.risk_score}
                                </span>
                                {bridge.is_critical && (
                                  <span className="px-1.5 py-0.5 bg-red-100 text-red-700 text-xs font-medium rounded">
                                    CRITICAL
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="px-4 py-3 font-medium text-slate-900">
                              {bridge.cost_display}
                            </td>
                            <td className="px-4 py-3">
                              <span
                                className={clsx(
                                  "font-bold",
                                  bridge.risk_cost_ratio >= 20
                                    ? "text-green-600"
                                    : bridge.risk_cost_ratio >= 15
                                    ? "text-blue-600"
                                    : "text-slate-600"
                                )}
                              >
                                {bridge.risk_cost_ratio.toFixed(1)}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-slate-600">
                              {bridge.year_built || "Unknown"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Roads Table */}
              {(infraFilter === "all" || infraFilter === "roads") && highRiskRoads && highRiskRoads.roads.length > 0 && (
                <div>
                  <div className="px-4 py-2 bg-amber-50 border-b border-amber-100 border-t">
                    <h4 className="text-sm font-semibold text-amber-800">
                      🛣️ Road Sections ({highRiskRoads.total_high_risk_roads}) - {highRiskRoads.total_repair_cost_display} ({highRiskRoads.total_length_km?.toFixed(1)} km)
                    </h4>
                  </div>
                  <div className="overflow-x-auto max-h-[350px] overflow-y-auto">
                    <table className="w-full">
                      <thead className="bg-slate-50 border-b border-slate-200 sticky top-0">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Highway / Section
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Condition
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Risk Score
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Length
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            Est. Cost
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            RCR
                          </th>
                          <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                            PCI
                          </th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {highRiskRoads.roads.map((road) => (
                          <tr
                            key={road.id}
                            className={clsx(
                              "hover:bg-slate-50 transition-colors",
                              road.is_critical && "bg-red-50/50"
                            )}
                          >
                            <td className="px-4 py-3">
                              <div>
                                <p className="font-medium text-slate-900">
                                  Highway {road.highway}
                                </p>
                                <p className="text-xs text-slate-500">
                                  {road.section_description}
                                </p>
                              </div>
                            </td>
                            <td className="px-4 py-3">
                              <span
                                className={clsx(
                                  "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
                                  getConditionColor(road.condition)
                                )}
                              >
                                {road.condition}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2">
                                <span
                                  className={clsx(
                                    "font-bold",
                                    road.risk_score >= 85
                                      ? "text-red-600"
                                      : road.risk_score >= 70
                                      ? "text-orange-600"
                                      : "text-yellow-600"
                                  )}
                                >
                                  {road.risk_score}
                                </span>
                                {road.is_critical && (
                                  <span className="px-1.5 py-0.5 bg-red-100 text-red-700 text-xs font-medium rounded">
                                    CRITICAL
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="px-4 py-3 text-slate-900">
                              {road.length_km?.toFixed(1)} km
                            </td>
                            <td className="px-4 py-3 font-medium text-slate-900">
                              {road.cost_display}
                            </td>
                            <td className="px-4 py-3">
                              <span
                                className={clsx(
                                  "font-bold",
                                  road.risk_cost_ratio >= 20
                                    ? "text-green-600"
                                    : road.risk_cost_ratio >= 15
                                    ? "text-blue-600"
                                    : "text-slate-600"
                                )}
                              >
                                {road.risk_cost_ratio?.toFixed(1)}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-slate-600">
                              {road.pci !== null ? road.pci.toFixed(0) : "N/A"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              
              {/* No data message */}
              {!highRiskBridges?.bridges?.length && !highRiskRoads?.roads?.length && (
                <div className="py-20 text-center text-slate-500">
                  <Building2 size={48} className="mx-auto mb-4 text-slate-300" />
                  <p>No high-risk infrastructure found in this region.</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
