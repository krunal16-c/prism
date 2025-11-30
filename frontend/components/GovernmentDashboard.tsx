"use client";

import { useState, useEffect, useCallback, useRef, ComponentType } from "react";
import { X, Building2, DollarSign, AlertTriangle, TrendingUp, ChevronDown, MapPin, RefreshCw, ExternalLink, Clock, Database, Zap } from "lucide-react";
import { 
  PieChart as RePieChart, 
  Pie, 
  Cell, 
  Tooltip,
  ResponsiveContainer,
  Legend
} from "recharts";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";
import dynamic from "next/dynamic";
import { 
  DashboardSummary, 
  BridgeLocation, 
  RegionsResponse,
  CacheStatus,
  CONDITION_COLORS,
  CONDITION_BG_COLORS,
  CONDITION_TEXT_COLORS
} from "@/types";
import axios from "axios";

// Helper function to format currency values cleanly
function formatCurrency(value: number, suffix: 'B' | 'M' | 'K' = 'M'): string {
  // Round to 1 decimal place to avoid floating point issues
  const rounded = Math.round(value * 10) / 10;
  
  // Format with commas for thousands
  const formatted = rounded.toLocaleString('en-CA', {
    minimumFractionDigits: rounded % 1 === 0 ? 0 : 1,
    maximumFractionDigits: 1
  });
  
  return `$${formatted}${suffix}`;
}

// Type for the GovernmentMap props
interface GovernmentMapProps {
  bridges: BridgeLocation[];
  region: string;
}

// Dynamically import the map component to avoid SSR issues
const GovernmentMap = dynamic<GovernmentMapProps>(
  () => import("./GovernmentMap").then((mod) => mod.default as ComponentType<GovernmentMapProps>),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full flex items-center justify-center bg-slate-100 rounded-xl" role="status" aria-label="Loading map">
        <div className="text-slate-400 flex items-center gap-2">
          <RefreshCw className="animate-spin" size={20} />
          <span>Loading map...</span>
        </div>
      </div>
    ),
  }
);

interface GovernmentDashboardProps {
  onClose: () => void;
  initialRegion?: string;
}

export default function GovernmentDashboard({ onClose, initialRegion = "Ontario" }: GovernmentDashboardProps) {
  const [regions, setRegions] = useState<string[]>([]);
  const [selectedRegion, setSelectedRegion] = useState<string>(initialRegion);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [bridges, setBridges] = useState<BridgeLocation[]>([]);
  const [cacheStatus, setCacheStatus] = useState<CacheStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const API_BASE = "http://localhost:8000/api";

  // Fetch available regions
  useEffect(() => {
    const fetchRegions = async () => {
      try {
        const response = await axios.get<RegionsResponse>(`${API_BASE}/dashboard/regions`);
        setRegions(response.data.regions);
      } catch (err) {
        console.error("Failed to fetch regions:", err);
      }
    };
    fetchRegions();
  }, []);

  // Fetch dashboard data when region changes
  const fetchDashboardData = useCallback(async (region: string, forceRefresh: boolean = false) => {
    if (forceRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);
    
    try {
      const refreshParam = forceRefresh ? "?force_refresh=true" : "";
      
      const [summaryRes, bridgesRes, cacheRes] = await Promise.all([
        axios.get<DashboardSummary>(`${API_BASE}/dashboard/summary/${encodeURIComponent(region)}${refreshParam}`),
        axios.get(`${API_BASE}/dashboard/bridges/${encodeURIComponent(region)}?limit=200${forceRefresh ? "&force_refresh=true" : ""}`),
        axios.get<CacheStatus>(`${API_BASE}/cache/status?region=${encodeURIComponent(region)}`)
      ]);
      
      setSummary(summaryRes.data);
      setBridges(bridgesRes.data.bridges);
      setCacheStatus(cacheRes.data);
      
      // Update URL with region parameter
      const url = new URL(window.location.href);
      url.searchParams.set("region", region);
      window.history.replaceState({}, "", url.toString());
      
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || `Failed to load data for ${region}`;
      setError(errorMessage);
      setSummary(null);
      setBridges([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // Handle manual refresh from MCP
  const handleRefresh = useCallback(() => {
    fetchDashboardData(selectedRegion, true);
  }, [selectedRegion, fetchDashboardData]);

  useEffect(() => {
    fetchDashboardData(selectedRegion);
  }, [selectedRegion, fetchDashboardData]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Handle keyboard navigation
  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      if (dropdownOpen) {
        setDropdownOpen(false);
      } else {
        onClose();
      }
    }
  };

  // Prepare pie chart data
  const pieChartData = summary?.condition_breakdown.map(item => ({
    name: item.condition,
    value: item.count,
    percentage: item.percentage,
    color: CONDITION_COLORS[item.condition] || CONDITION_COLORS["Unknown"]
  })) || [];

  // Custom tooltip for pie chart
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white p-3 rounded-lg shadow-lg border border-slate-200" role="tooltip">
          <p className="font-semibold text-slate-900">{data.name}</p>
          <p className="text-sm text-slate-600">{data.value.toLocaleString()} bridges</p>
          <p className="text-sm font-medium" style={{ color: data.color }}>{data.percentage}%</p>
        </div>
      );
    }
    return null;
  };

  return (
    <div 
      className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-[2000] p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="dashboard-title"
      onKeyDown={handleKeyDown}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-7xl max-h-[95vh] overflow-hidden flex flex-col"
      >
        {/* Header */}
        <header className="p-6 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white">
          <div className="flex justify-between items-start">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-blue-100 text-blue-700 rounded-xl" aria-hidden="true">
                <Building2 size={28} />
              </div>
              <div>
                <h1 id="dashboard-title" className="text-2xl font-bold text-slate-900">
                  Live Government Data Dashboard
                </h1>
                <p className="text-sm text-slate-500 mt-1">
                  Infrastructure condition monitoring for Canadian provinces
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              {/* Cache Status Indicator */}
              {cacheStatus && (
                <div 
                  className={clsx(
                    "flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium",
                    cacheStatus.valid 
                      ? "bg-green-50 text-green-700 border border-green-200"
                      : "bg-amber-50 text-amber-700 border border-amber-200"
                  )}
                  title={cacheStatus.valid 
                    ? `Cached ${cacheStatus.age_hours?.toFixed(1)}h ago` 
                    : "Cache expired"
                  }
                >
                  <Database size={14} />
                  <span>
                    {cacheStatus.valid 
                      ? `Cached ${Math.round(cacheStatus.age_hours || 0)}h ago`
                      : "Refreshing..."
                    }
                  </span>
                </div>
              )}
              
              {/* Refresh Button */}
              <button
                onClick={handleRefresh}
                disabled={refreshing}
                className={clsx(
                  "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all",
                  "border focus:outline-none focus:ring-2 focus:ring-blue-500",
                  refreshing
                    ? "bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed"
                    : "bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100"
                )}
                aria-label={refreshing ? "Refreshing data..." : "Refresh data from Statistics Canada"}
              >
                <RefreshCw 
                  size={16} 
                  className={clsx(refreshing && "animate-spin")} 
                />
                <span className="hidden sm:inline">
                  {refreshing ? "Syncing..." : "Refresh"}
                </span>
              </button>
              
              {/* Region Selector */}
              <div className="relative" ref={dropdownRef}>
                <label htmlFor="region-select" className="sr-only">Select Region</label>
                <button
                  id="region-select"
                  onClick={() => setDropdownOpen(!dropdownOpen)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      setDropdownOpen(!dropdownOpen);
                    }
                  }}
                  className="flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 rounded-xl hover:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all min-w-[200px] justify-between"
                  aria-haspopup="listbox"
                  aria-expanded={dropdownOpen}
                  aria-label={`Selected region: ${selectedRegion}`}
                >
                  <span className="font-medium text-slate-700">{selectedRegion}</span>
                  <ChevronDown 
                    size={18} 
                    className={clsx("text-slate-400 transition-transform", dropdownOpen && "rotate-180")} 
                    aria-hidden="true"
                  />
                </button>
                
                <AnimatePresence>
                  {dropdownOpen && (
                    <motion.ul
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      className="absolute top-full mt-2 left-0 right-0 bg-white border border-slate-200 rounded-xl shadow-lg max-h-64 overflow-auto z-50"
                      role="listbox"
                      aria-label="Select a region"
                      tabIndex={-1}
                    >
                      {regions.map((region, index) => (
                        <li
                          key={region}
                          role="option"
                          aria-selected={region === selectedRegion}
                          tabIndex={0}
                          onClick={() => {
                            setSelectedRegion(region);
                            setDropdownOpen(false);
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              setSelectedRegion(region);
                              setDropdownOpen(false);
                            }
                          }}
                          className={clsx(
                            "px-4 py-2.5 cursor-pointer transition-colors focus:outline-none focus:bg-blue-50",
                            region === selectedRegion
                              ? "bg-blue-50 text-blue-700 font-medium"
                              : "text-slate-700 hover:bg-slate-50",
                            index === 0 && "rounded-t-xl",
                            index === regions.length - 1 && "rounded-b-xl"
                          )}
                        >
                          {region}
                        </li>
                      ))}
                    </motion.ul>
                  )}
                </AnimatePresence>
              </div>
              
              {/* Close Button */}
              <button 
                onClick={onClose}
                className="p-2 hover:bg-slate-100 rounded-full text-slate-400 hover:text-slate-600 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
                aria-label="Close dashboard"
              >
                <X size={24} aria-hidden="true" />
              </button>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 overflow-auto p-6 bg-slate-50">
          {loading ? (
            <div className="flex items-center justify-center h-96" role="status" aria-label="Loading dashboard data">
              <div className="text-center">
                <RefreshCw className="animate-spin mx-auto text-blue-500 mb-4" size={40} aria-hidden="true" />
                <p className="text-slate-500">Loading {selectedRegion} data...</p>
              </div>
            </div>
          ) : error ? (
            <div 
              className="flex items-center justify-center h-96" 
              role="alert" 
              aria-live="polite"
            >
              <div className="text-center bg-red-50 p-8 rounded-2xl border border-red-100 max-w-md">
                <AlertTriangle className="mx-auto text-red-500 mb-4" size={48} aria-hidden="true" />
                <h3 className="text-lg font-semibold text-red-700 mb-2">Data Unavailable</h3>
                <p className="text-red-600">{error}</p>
                <button
                  onClick={() => fetchDashboardData(selectedRegion)}
                  className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2"
                >
                  Try Again
                </button>
              </div>
            </div>
          ) : summary && (
            <>
              {/* Key Metrics Cards */}
              <section aria-labelledby="metrics-heading">
                <h2 id="metrics-heading" className="sr-only">Key Infrastructure Metrics for {selectedRegion}</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                  <MetricCard
                    icon={<Building2 size={24} />}
                    iconBg="bg-blue-100"
                    iconColor="text-blue-600"
                    label="Total Bridges"
                    value={summary.total_bridges.toLocaleString()}
                    description={`Bridges in ${selectedRegion}`}
                  />
                  
                  <MetricCard
                    icon={<AlertTriangle size={24} />}
                    iconBg="bg-red-100"
                    iconColor="text-red-600"
                    label="Critical Condition"
                    value={summary.condition_breakdown.find(c => c.condition === "Critical")?.count.toLocaleString() || "0"}
                    description={`${summary.condition_breakdown.find(c => c.condition === "Critical")?.percentage.toFixed(1) || "0"}% of total`}
                    highlight="red"
                  />
                  
                  <MetricCard
                    icon={<DollarSign size={24} />}
                    iconBg="bg-green-100"
                    iconColor="text-green-600"
                    label="Replacement Value"
                    value={formatCurrency(summary.replacement_value_billions, 'B')}
                    description="Total estimated value (CAD)"
                  />
                  
                  <MetricCard
                    icon={<TrendingUp size={24} />}
                    iconBg="bg-amber-100"
                    iconColor="text-amber-600"
                    label="Priority Investment"
                    value={formatCurrency(summary.priority_investment_millions, 'M')}
                    description="Recommended investment (CAD)"
                  />
                </div>
              </section>

              {/* Charts and Map Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Condition Breakdown */}
                <section 
                  className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100"
                  aria-labelledby="condition-chart-heading"
                >
                  <h3 id="condition-chart-heading" className="text-lg font-semibold text-slate-900 mb-4">
                    Condition Breakdown
                  </h3>
                  
                  {/* Accessible data table for screen readers */}
                  <div className="sr-only">
                    <table>
                      <caption>Bridge condition breakdown for {selectedRegion}</caption>
                      <thead>
                        <tr>
                          <th>Condition</th>
                          <th>Count</th>
                          <th>Percentage</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.condition_breakdown.map(item => (
                          <tr key={item.condition}>
                            <td>{item.condition}</td>
                            <td>{item.count} bridges</td>
                            <td>{item.percentage}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  
                  <div className="h-64" aria-hidden="true">
                    <ResponsiveContainer width="100%" height="100%">
                      <RePieChart>
                        <Pie
                          data={pieChartData}
                          cx="50%"
                          cy="50%"
                          innerRadius={50}
                          outerRadius={80}
                          paddingAngle={2}
                          dataKey="value"
                          nameKey="name"
                        >
                          {pieChartData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip content={<CustomTooltip />} />
                        <Legend 
                          verticalAlign="bottom" 
                          height={36}
                          formatter={(value: string) => (
                            <span className="text-sm text-slate-600">{value}</span>
                          )}
                        />
                      </RePieChart>
                    </ResponsiveContainer>
                  </div>
                  
                  {/* Visual legend with counts */}
                  <div className="mt-4 space-y-2">
                    {summary.condition_breakdown.map(item => (
                      <div key={item.condition} className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <span 
                            className={clsx("w-3 h-3 rounded-full", CONDITION_BG_COLORS[item.condition])}
                            aria-hidden="true"
                          />
                          <span className="text-slate-600">{item.condition}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-slate-900">{item.count.toLocaleString()}</span>
                          <span className="text-slate-400">({item.percentage}%)</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>

                {/* Map Section */}
                <section 
                  className="lg:col-span-2 bg-white rounded-2xl p-6 shadow-sm border border-slate-100"
                  aria-labelledby="map-heading"
                >
                  <div className="flex items-center justify-between mb-4">
                    <h3 id="map-heading" className="text-lg font-semibold text-slate-900 flex items-center gap-2">
                      <MapPin size={20} className="text-blue-500" aria-hidden="true" />
                      Bridge Locations
                    </h3>
                    <span className="text-sm text-slate-500">
                      Showing {bridges.length} of {summary.total_bridges.toLocaleString()} bridges
                    </span>
                  </div>
                  
                  {/* Screen reader description */}
                  <p className="sr-only">
                    Interactive map showing {bridges.length} bridge locations in {selectedRegion}. 
                    Bridges are color-coded by condition: green for good, yellow for fair, 
                    orange for poor, and red for critical condition.
                  </p>
                  
                  <div className="h-80 rounded-xl overflow-hidden border border-slate-200">
                    <GovernmentMap bridges={bridges} region={selectedRegion} />
                  </div>
                  
                  {/* Map Legend */}
                  <div className="mt-4 flex flex-wrap gap-4" aria-label="Map legend">
                    {Object.entries(CONDITION_COLORS).filter(([k]) => k !== "Unknown").map(([condition, color]) => (
                      <div key={condition} className="flex items-center gap-2">
                        <span 
                          className="w-3 h-3 rounded-full border border-white shadow-sm"
                          style={{ backgroundColor: color }}
                          aria-hidden="true"
                        />
                        <span className="text-xs text-slate-600">{condition}</span>
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            </>
          )}
        </main>

        {/* Footer with data source and cache status */}
        <footer className="p-4 border-t border-slate-200 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-4 text-sm">
            <div className="flex items-center gap-3 text-slate-500">
              <span className="px-2 py-1 bg-blue-50 text-blue-700 rounded-md font-medium text-xs">
                Statistics Canada
              </span>
              <span>• Official Government Data</span>
              {summary?.reference_year && (
                <span className="text-slate-400">• Reference Year: {summary.reference_year}</span>
              )}
            </div>
            
            {summary && (
              <div className="flex items-center gap-4">
                {/* Cache age indicator */}
                {summary.is_cached && typeof summary.cache_age_hours === 'number' && (
                  <span className="flex items-center gap-1.5 text-slate-400">
                    <Clock size={14} />
                    <span>
                      Synced {summary.cache_age_hours < 1 
                        ? "< 1 hour ago" 
                        : `${Math.round(summary.cache_age_hours)}h ago`
                      }
                    </span>
                  </span>
                )}
                <span className="text-slate-400">
                  Last Updated: {summary.last_updated}
                </span>
                {summary.data_source_url && (
                  <a 
                    href={summary.data_source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-blue-600 hover:text-blue-700 transition-colors focus:outline-none focus:underline"
                    aria-label="View data source (opens in new tab)"
                  >
                    <span>View Source</span>
                    <ExternalLink size={14} aria-hidden="true" />
                  </a>
                )}
              </div>
            )}
          </div>
        </footer>
      </motion.div>
    </div>
  );
}

// Metric Card Component
interface MetricCardProps {
  icon: React.ReactNode;
  iconBg: string;
  iconColor: string;
  label: string;
  value: string;
  description: string;
  highlight?: "red" | "green" | "amber";
}

function MetricCard({ icon, iconBg, iconColor, label, value, description, highlight }: MetricCardProps) {
  return (
    <article 
      className={clsx(
        "bg-white rounded-xl p-5 shadow-sm border transition-shadow hover:shadow-md",
        highlight === "red" ? "border-red-100" : "border-slate-100"
      )}
      aria-label={`${label}: ${value}`}
    >
      <div className="flex items-start justify-between">
        <div className={clsx("p-2.5 rounded-lg", iconBg, iconColor)} aria-hidden="true">
          {icon}
        </div>
      </div>
      <div className="mt-4">
        <p className="text-sm font-medium text-slate-500">{label}</p>
        <p 
          className={clsx(
            "text-2xl font-bold mt-1",
            highlight === "red" ? "text-red-600" : "text-slate-900"
          )}
        >
          {value}
        </p>
        <p className="text-xs text-slate-400 mt-1">{description}</p>
      </div>
    </article>
  );
}
