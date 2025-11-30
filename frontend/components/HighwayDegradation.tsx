"use client";

import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell, PieChart, Pie, Legend, AreaChart, Area
} from "recharts";
import {
  X, TrendingDown, AlertTriangle, DollarSign, Clock, Truck,
  Activity, ChevronDown, RefreshCw, Database, Zap, Play, Pause,
  Fuel, Car, Calendar, ArrowDown, ArrowUp, Construction, Snowflake,
  ThermometerSnowflake, Route, ArrowLeftRight, Package, BadgeDollarSign
} from "lucide-react";
import clsx from "clsx";
import { 
  RoadSegment, RoadForecast, EconomicImpact, ForecastSummary,
  WinterVulnerability, WinterForecastSummary, PreWinterIntervention,
  BundleOpportunity, DirectionalAnalysis, CorridorSummary
} from "@/types";

interface HighwayDegradationProps {
  onClose: () => void;
}

const API_BASE = "http://localhost:8000";

// PCI condition colors matching Government Dashboard style
const CONDITION_COLORS: Record<string, string> = {
  "Good": "#22c55e",
  "Fair": "#f59e0b", 
  "Poor": "#f97316",
  "Critical": "#ef4444",
};

const CONDITION_BG_COLORS: Record<string, string> = {
  "Good": "bg-green-50",
  "Fair": "bg-amber-50",
  "Poor": "bg-orange-50", 
  "Critical": "bg-red-50",
};

const CONDITION_TEXT_COLORS: Record<string, string> = {
  "Good": "text-green-700",
  "Fair": "text-amber-700",
  "Poor": "text-orange-700",
  "Critical": "text-red-700",
};

const formatCurrency = (value: number, suffix: 'B' | 'M' | 'K' = 'M'): string => {
  const rounded = Math.round(value * 10) / 10;
  const formatted = rounded.toLocaleString('en-CA', {
    minimumFractionDigits: rounded % 1 === 0 ? 0 : 1,
    maximumFractionDigits: 1
  });
  return `$${formatted}${suffix}`;
};

const getPCICondition = (pci: number): string => {
  if (pci >= 80) return "Good";
  if (pci >= 60) return "Fair";
  if (pci >= 40) return "Poor";
  return "Critical";
};

const getPCIColor = (pci: number): string => {
  if (pci >= 80) return CONDITION_COLORS["Good"];
  if (pci >= 60) return CONDITION_COLORS["Fair"];
  if (pci >= 40) return CONDITION_COLORS["Poor"];
  return CONDITION_COLORS["Critical"];
};

// Calculate degraded PCI based on year
const calculateDegradedPCI = (currentPCI: number, years: number, pavementType: string = "AC"): number => {
  const baseRates: Record<string, number> = {
    "AC": -4.5, "PCC": -2.5, "COMP": -3.5, "ST": -6.0, "GRAVEL": -8.0,
  };
  const baseRate = baseRates[pavementType] || -5.0;
  let pci = currentPCI;
  
  for (let y = 0; y < years; y++) {
    let factor = 1.0;
    if (pci < 40) factor = 2.2;
    else if (pci < 50) factor = 1.8;
    else if (pci < 60) factor = 1.5;
    else if (pci < 70) factor = 1.2;
    pci = Math.max(0, pci + baseRate * factor);
  }
  return Math.round(pci * 10) / 10;
};

export default function HighwayDegradation({ onClose }: HighwayDegradationProps) {
  const [provinces] = useState([
    "Ontario", "British Columbia", "Alberta", "Saskatchewan", "Manitoba",
    "Quebec", "New Brunswick", "Nova Scotia", "Prince Edward Island", "Newfoundland and Labrador"
  ]);
  const [selectedProvince, setSelectedProvince] = useState("Ontario");
  const [highways, setHighways] = useState<string[]>([]);
  const [selectedHighway, setSelectedHighway] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "forecast" | "economic" | "winter" | "corridor">("overview");
  
  // Year slider state
  const [selectedYear, setSelectedYear] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  
  // Data states
  const [allRoadConditions, setAllRoadConditions] = useState<RoadSegment[]>([]);
  const [forecasts, setForecasts] = useState<RoadForecast[]>([]);
  const [forecastSummary, setForecastSummary] = useState<ForecastSummary | null>(null);
  const [allEconomicImpacts, setAllEconomicImpacts] = useState<EconomicImpact[]>([]);
  
  // Winter Resilience States (Feature 11)
  const [winterVulnerabilities, setWinterVulnerabilities] = useState<WinterVulnerability[]>([]);
  const [winterSummary, setWinterSummary] = useState<WinterForecastSummary | null>(null);
  const [winterInterventions, setWinterInterventions] = useState<PreWinterIntervention[]>([]);
  const [winterLoading, setWinterLoading] = useState(false);
  
  // Corridor Optimization States (Feature 12)
  const [bundles, setBundles] = useState<BundleOpportunity[]>([]);
  const [directionalAnalyses, setDirectionalAnalyses] = useState<DirectionalAnalysis[]>([]);
  const [corridorSummary, setCorridorSummary] = useState<CorridorSummary | null>(null);
  const [corridorLoading, setCorridorLoading] = useState(false);
  
  // Dropdown states
  const [provinceDropdownOpen, setProvinceDropdownOpen] = useState(false);
  const [highwayDropdownOpen, setHighwayDropdownOpen] = useState(false);
  const provinceDropdownRef = useRef<HTMLDivElement>(null);
  const highwayDropdownRef = useRef<HTMLDivElement>(null);

  // Fetch highways when province changes
  useEffect(() => {
    const fetchHighways = async () => {
      try {
        const res = await axios.get(`${API_BASE}/api/roads/highways/${selectedProvince}`);
        setHighways(res.data.highways || []);
        if (res.data.highways?.length > 0) {
          setSelectedHighway(res.data.highways[0]);
        }
      } catch (err) {
        console.error("Failed to fetch highways:", err);
        setHighways([]);
      }
    };
    if (selectedProvince) {
      fetchHighways();
    }
  }, [selectedProvince]);

  // Fetch all data
  const fetchData = useCallback(async (forceRefresh: boolean = false) => {
    if (!selectedProvince) return;
    
    if (forceRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    
    try {
      const [conditionsRes, economicRes] = await Promise.all([
        axios.get(`${API_BASE}/api/roads/conditions`, {
          params: { province: selectedProvince, limit: 2000 }
        }),
        axios.get(`${API_BASE}/api/roads/economic-impact`, {
          params: { province: selectedProvince }
        })
      ]);
      
      setAllRoadConditions(conditionsRes.data.roads || []);
      setAllEconomicImpacts(economicRes.data.impacts || []);
    } catch (err) {
      console.error("Failed to fetch data:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedProvince]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Fetch forecast when highway changes
  useEffect(() => {
    const fetchForecast = async () => {
      if (!selectedHighway || !selectedProvince) return;
      try {
        const forecastRes = await axios.get(
          `${API_BASE}/api/roads/forecast/${encodeURIComponent(selectedHighway)}`,
          { params: { province: selectedProvince, years: 10 } }
        );
        setForecasts(forecastRes.data.sections || []);
        setForecastSummary(forecastRes.data.summary || null);
      } catch (err) {
        console.error("Failed to fetch forecast:", err);
      }
    };
    fetchForecast();
  }, [selectedHighway, selectedProvince]);

  // Fetch Winter Resilience data when tab becomes active
  useEffect(() => {
    if (activeTab !== "winter" || !selectedProvince || !selectedHighway) return;
    
    const fetchWinterData = async () => {
      setWinterLoading(true);
      try {
        const [vulnRes, summaryRes, interventionsRes] = await Promise.all([
          axios.get(`${API_BASE}/api/roads/winter/vulnerability`, {
            params: { province: selectedProvince, highway: selectedHighway }
          }),
          axios.get(`${API_BASE}/api/roads/winter/forecast-summary`, {
            params: { province: selectedProvince, highway: selectedHighway }
          }),
          axios.get(`${API_BASE}/api/roads/winter/interventions`, {
            params: { province: selectedProvince, highway: selectedHighway }
          })
        ]);
        
        setWinterVulnerabilities(vulnRes.data.vulnerabilities || []);
        setWinterSummary(summaryRes.data.summary || null);
        setWinterInterventions(interventionsRes.data.interventions || []);
      } catch (err) {
        console.error("Failed to fetch winter data:", err);
      } finally {
        setWinterLoading(false);
      }
    };
    fetchWinterData();
  }, [activeTab, selectedProvince, selectedHighway]);

  // Fetch Corridor Optimization data when tab becomes active
  useEffect(() => {
    if (activeTab !== "corridor" || !selectedProvince || !selectedHighway) return;
    
    const fetchCorridorData = async () => {
      setCorridorLoading(true);
      try {
        const [bundlesRes, directionalRes, summaryRes] = await Promise.all([
          axios.get(`${API_BASE}/api/roads/corridor/bundles`, {
            params: { province: selectedProvince, highway: selectedHighway }
          }),
          axios.get(`${API_BASE}/api/roads/corridor/directional-analysis`, {
            params: { province: selectedProvince, highway: selectedHighway }
          }),
          axios.get(`${API_BASE}/api/roads/corridor/summary`, {
            params: { province: selectedProvince, highway: selectedHighway }
          })
        ]);
        
        setBundles(bundlesRes.data.bundles || []);
        setDirectionalAnalyses(directionalRes.data.analyses || []);
        setCorridorSummary(summaryRes.data.summary || null);
      } catch (err) {
        console.error("Failed to fetch corridor data:", err);
      } finally {
        setCorridorLoading(false);
      }
    };
    fetchCorridorData();
  }, [activeTab, selectedProvince, selectedHighway]);

  // Auto-play year slider
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setSelectedYear(y => {
        if (y >= 10) {
          setIsPlaying(false);
          return 10;
        }
        return y + 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [isPlaying]);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (provinceDropdownRef.current && !provinceDropdownRef.current.contains(event.target as Node)) {
        setProvinceDropdownOpen(false);
      }
      if (highwayDropdownRef.current && !highwayDropdownRef.current.contains(event.target as Node)) {
        setHighwayDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Filter data by selected highway
  const roadConditions = useMemo(() => {
    if (!selectedHighway) return allRoadConditions;
    return allRoadConditions.filter(r => r.highway === selectedHighway);
  }, [allRoadConditions, selectedHighway]);

  const economicImpacts = useMemo(() => {
    if (!selectedHighway) return allEconomicImpacts;
    return allEconomicImpacts.filter(i => i.highway === selectedHighway);
  }, [allEconomicImpacts, selectedHighway]);

  // Project road segments to selected year
  const projectedRoadSegments = useMemo(() => {
    return roadConditions.map(road => {
      const projectedPCI = calculateDegradedPCI(road.pci, selectedYear, road.pavement_type);
      return {
        ...road,
        originalPCI: road.pci,
        pci: projectedPCI,
        condition: getPCICondition(projectedPCI),
      };
    });
  }, [roadConditions, selectedYear]);

  // Summary statistics
  const stats = useMemo(() => {
    if (!projectedRoadSegments.length) return null;
    
    const total = projectedRoadSegments.length;
    const byCondition = {
      Good: projectedRoadSegments.filter(r => r.pci >= 80).length,
      Fair: projectedRoadSegments.filter(r => r.pci >= 60 && r.pci < 80).length,
      Poor: projectedRoadSegments.filter(r => r.pci >= 40 && r.pci < 60).length,
      Critical: projectedRoadSegments.filter(r => r.pci < 40).length,
    };
    const avgPCI = projectedRoadSegments.reduce((sum, r) => sum + r.pci, 0) / total;
    const criticalCount = byCondition.Poor + byCondition.Critical;
    
    // Calculate economic totals
    const adjustedEconomicImpacts = economicImpacts.map(impact => {
      const projectedPCI = calculateDegradedPCI(impact.pci, selectedYear);
      const pciDrop = impact.pci - projectedPCI;
      const costMultiplier = 1 + (pciDrop / 20);
      return {
        ...impact,
        total_annual_cost: impact.total_annual_cost * costMultiplier,
        annual_vehicle_damage_cost: impact.annual_vehicle_damage_cost * costMultiplier,
        annual_fuel_waste_cost: impact.annual_fuel_waste_cost * costMultiplier,
        annual_freight_delay_cost: impact.annual_freight_delay_cost * costMultiplier,
      };
    });
    
    const totalAnnualCost = adjustedEconomicImpacts.reduce((sum, i) => sum + i.total_annual_cost, 0);
    const repairCost = criticalCount * 2500000; // $2.5M avg per critical section
    
    return {
      total,
      byCondition,
      avgPCI: avgPCI.toFixed(1),
      criticalCount,
      criticalPercent: ((criticalCount / total) * 100).toFixed(1),
      totalAnnualCost,
      repairCost,
      economicImpacts: adjustedEconomicImpacts,
    };
  }, [projectedRoadSegments, economicImpacts, selectedYear]);

  // Pie chart data
  const pieChartData = useMemo(() => {
    if (!stats) return [];
    return Object.entries(stats.byCondition)
      .filter(([_, count]) => count > 0)
      .map(([condition, count]) => ({
        name: condition,
        value: count,
        percentage: ((count / stats.total) * 100).toFixed(1),
        color: CONDITION_COLORS[condition],
      }));
  }, [stats]);

  // Forecast timeline data
  const forecastTimelineData = useMemo(() => {
    const years = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    return years.map(year => {
      const projections = roadConditions.map(r => 
        calculateDegradedPCI(r.pci, year, r.pavement_type)
      );
      const avgPCI = projections.length 
        ? projections.reduce((a, b) => a + b, 0) / projections.length 
        : 0;
      const critical = projections.filter(p => p < 40).length;
      const poor = projections.filter(p => p >= 40 && p < 60).length;
      
      return {
        year: year === 0 ? "Now" : `+${year}yr`,
        yearNum: year,
        avgPCI: Math.round(avgPCI * 10) / 10,
        criticalSections: critical,
        poorSections: poor,
        atRisk: critical + poor,
      };
    });
  }, [roadConditions]);

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white p-3 rounded-lg shadow-lg border border-slate-200">
          <p className="font-semibold text-slate-900">{data.name}</p>
          <p className="text-sm text-slate-600">{data.value} sections</p>
          <p className="text-sm font-medium" style={{ color: data.color }}>{data.percentage}%</p>
        </div>
      );
    }
    return null;
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      if (provinceDropdownOpen) setProvinceDropdownOpen(false);
      else if (highwayDropdownOpen) setHighwayDropdownOpen(false);
      else onClose();
    }
  };

  return (
    <div 
      className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-[2000] p-4"
      role="dialog"
      aria-modal="true"
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
              <div className="p-3 bg-orange-100 text-orange-700 rounded-xl">
                <TrendingDown size={28} />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900">
                  Highway Degradation Forecaster
                </h1>
                <p className="text-sm text-slate-500 mt-1">
                  PCI prediction & economic impact analysis for road infrastructure
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              {/* Refresh Button */}
              <button
                onClick={() => fetchData(true)}
                disabled={refreshing}
                className={clsx(
                  "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all border",
                  refreshing
                    ? "bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed"
                    : "bg-orange-50 text-orange-700 border-orange-200 hover:bg-orange-100"
                )}
              >
                <RefreshCw size={16} className={clsx(refreshing && "animate-spin")} />
                <span className="hidden sm:inline">{refreshing ? "Syncing..." : "Refresh"}</span>
              </button>
              
              {/* Province Selector */}
              <div className="relative" ref={provinceDropdownRef}>
                <button
                  onClick={() => setProvinceDropdownOpen(!provinceDropdownOpen)}
                  className="flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 rounded-xl hover:border-orange-300 focus:outline-none focus:ring-2 focus:ring-orange-500 min-w-[180px] justify-between"
                >
                  <span className="font-medium text-slate-700">{selectedProvince}</span>
                  <ChevronDown size={18} className={clsx("text-slate-400 transition-transform", provinceDropdownOpen && "rotate-180")} />
                </button>
                
                <AnimatePresence>
                  {provinceDropdownOpen && (
                    <motion.ul
                      initial={{ opacity: 0, y: -10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      className="absolute top-full mt-2 left-0 right-0 bg-white border border-slate-200 rounded-xl shadow-lg max-h-64 overflow-auto z-50"
                    >
                      {provinces.map((province, index) => (
                        <li
                          key={province}
                          onClick={() => {
                            setSelectedProvince(province);
                            setProvinceDropdownOpen(false);
                          }}
                          className={clsx(
                            "px-4 py-2.5 cursor-pointer transition-colors",
                            province === selectedProvince
                              ? "bg-orange-50 text-orange-700 font-medium"
                              : "text-slate-700 hover:bg-slate-50",
                            index === 0 && "rounded-t-xl",
                            index === provinces.length - 1 && "rounded-b-xl"
                          )}
                        >
                          {province}
                        </li>
                      ))}
                    </motion.ul>
                  )}
                </AnimatePresence>
              </div>
              
              {/* Close Button */}
              <button 
                onClick={onClose}
                className="p-2 hover:bg-slate-100 rounded-full text-slate-400 hover:text-slate-600 transition-colors"
              >
                <X size={24} />
              </button>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 overflow-auto p-6 bg-slate-50">
          {loading ? (
            <div className="flex items-center justify-center h-96">
              <div className="text-center">
                <RefreshCw className="animate-spin mx-auto text-orange-500 mb-4" size={40} />
                <p className="text-slate-500">Loading road data...</p>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Highway Selector & Year Slider Row */}
              <div className="flex flex-wrap items-center gap-4 bg-white rounded-xl border border-slate-200 p-4">
                {/* Highway Selector */}
                <div className="relative" ref={highwayDropdownRef}>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Highway</label>
                  <button
                    onClick={() => setHighwayDropdownOpen(!highwayDropdownOpen)}
                    disabled={!highways.length}
                    className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-lg hover:border-orange-300 focus:outline-none focus:ring-2 focus:ring-orange-500 min-w-[200px] justify-between"
                  >
                    <span className="font-medium text-slate-700">{selectedHighway || "Select Highway"}</span>
                    <ChevronDown size={16} className={clsx("text-slate-400 transition-transform", highwayDropdownOpen && "rotate-180")} />
                  </button>
                  
                  <AnimatePresence>
                    {highwayDropdownOpen && highways.length > 0 && (
                      <motion.ul
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className="absolute top-full mt-2 left-0 right-0 bg-white border border-slate-200 rounded-xl shadow-lg max-h-64 overflow-auto z-50"
                      >
                        {highways.map((highway, index) => (
                          <li
                            key={highway}
                            onClick={() => {
                              setSelectedHighway(highway);
                              setHighwayDropdownOpen(false);
                            }}
                            className={clsx(
                              "px-4 py-2.5 cursor-pointer transition-colors",
                              highway === selectedHighway
                                ? "bg-orange-50 text-orange-700 font-medium"
                                : "text-slate-700 hover:bg-slate-50",
                              index === 0 && "rounded-t-xl",
                              index === highways.length - 1 && "rounded-b-xl"
                            )}
                          >
                            {highway}
                          </li>
                        ))}
                      </motion.ul>
                    )}
                  </AnimatePresence>
                </div>

                {/* Divider */}
                <div className="h-12 w-px bg-slate-200" />

                {/* Year Slider */}
                <div className="flex-1 min-w-[300px]">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => setIsPlaying(!isPlaying)}
                      className={clsx(
                        "w-8 h-8 rounded-full flex items-center justify-center transition-colors",
                        isPlaying 
                          ? "bg-orange-600 text-white" 
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      )}
                    >
                      {isPlaying ? <Pause size={14} /> : <Play size={14} className="ml-0.5" />}
                    </button>
                    
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-xs font-medium text-slate-500">Projection Year</label>
                        <span className="text-sm font-semibold text-orange-600">
                          {selectedYear === 0 ? "Current" : `+${selectedYear} years`}
                        </span>
                      </div>
                      <input
                        type="range"
                        min={0}
                        max={10}
                        value={selectedYear}
                        onChange={(e) => setSelectedYear(parseInt(e.target.value))}
                        className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-orange-600"
                      />
                      <div className="flex justify-between text-xs text-slate-400 mt-1">
                        <span>Now</span>
                        <span>+5 yrs</span>
                        <span>+10 yrs</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Stats Cards */}
              {stats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-white rounded-xl border border-slate-200 p-5">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="p-2 bg-blue-100 text-blue-700 rounded-lg">
                        <Activity size={20} />
                      </div>
                    </div>
                    <p className="text-sm text-slate-500">Total Segments</p>
                    <p className="text-2xl font-bold text-slate-900">{stats.total}</p>
                    <p className="text-xs text-slate-400 mt-1">
                      {selectedHighway} in {selectedProvince}
                    </p>
                  </div>

                  <div className="bg-white rounded-xl border border-slate-200 p-5">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="p-2 bg-red-100 text-red-700 rounded-lg">
                        <AlertTriangle size={20} />
                      </div>
                    </div>
                    <p className="text-sm text-slate-500">Critical Condition</p>
                    <p className="text-2xl font-bold text-red-600">{stats.criticalCount}</p>
                    <p className="text-xs text-slate-400 mt-1">
                      {stats.criticalPercent}% of total
                    </p>
                  </div>

                  <div className="bg-white rounded-xl border border-slate-200 p-5">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="p-2 bg-green-100 text-green-700 rounded-lg">
                        <DollarSign size={20} />
                      </div>
                    </div>
                    <p className="text-sm text-slate-500">Annual Economic Cost</p>
                    <p className="text-2xl font-bold text-slate-900">
                      {stats.totalAnnualCost >= 1000000 
                        ? formatCurrency(stats.totalAnnualCost / 1000000, 'M')
                        : formatCurrency(stats.totalAnnualCost / 1000, 'K')}
                    </p>
                    <p className="text-xs text-slate-400 mt-1">
                      Vehicle damage, fuel waste, delays
                    </p>
                  </div>

                  <div className="bg-white rounded-xl border border-slate-200 p-5">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="p-2 bg-purple-100 text-purple-700 rounded-lg">
                        <Construction size={20} />
                      </div>
                    </div>
                    <p className="text-sm text-slate-500">Est. Repair Cost</p>
                    <p className="text-2xl font-bold text-slate-900">
                      {stats.repairCost >= 1000000 
                        ? formatCurrency(stats.repairCost / 1000000, 'M')
                        : formatCurrency(stats.repairCost / 1000, 'K')}
                    </p>
                    <p className="text-xs text-slate-400 mt-1">
                      To fix critical sections
                    </p>
                  </div>
                </div>
              )}

              {/* Tab Navigation */}
              <div className="flex gap-1 bg-white rounded-xl p-1.5 border border-slate-200 w-fit">
                <button
                  onClick={() => setActiveTab("overview")}
                  className={clsx(
                    "px-5 py-2 rounded-lg text-sm font-medium transition-all",
                    activeTab === "overview"
                      ? "bg-orange-600 text-white shadow-sm"
                      : "text-slate-600 hover:bg-slate-100"
                  )}
                >
                  Overview
                </button>
                <button
                  onClick={() => setActiveTab("forecast")}
                  className={clsx(
                    "px-5 py-2 rounded-lg text-sm font-medium transition-all",
                    activeTab === "forecast"
                      ? "bg-orange-600 text-white shadow-sm"
                      : "text-slate-600 hover:bg-slate-100"
                  )}
                >
                  Forecast
                </button>
                <button
                  onClick={() => setActiveTab("economic")}
                  className={clsx(
                    "px-5 py-2 rounded-lg text-sm font-medium transition-all",
                    activeTab === "economic"
                      ? "bg-orange-600 text-white shadow-sm"
                      : "text-slate-600 hover:bg-slate-100"
                  )}
                >
                  Economic Impact
                </button>
                <button
                  onClick={() => setActiveTab("winter")}
                  className={clsx(
                    "px-5 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2",
                    activeTab === "winter"
                      ? "bg-cyan-600 text-white shadow-sm"
                      : "text-slate-600 hover:bg-slate-100"
                  )}
                >
                  <Snowflake size={14} />
                  Winter Resilience
                </button>
                <button
                  onClick={() => setActiveTab("corridor")}
                  className={clsx(
                    "px-5 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2",
                    activeTab === "corridor"
                      ? "bg-purple-600 text-white shadow-sm"
                      : "text-slate-600 hover:bg-slate-100"
                  )}
                >
                  <Route size={14} />
                  Corridor Optimization
                </button>
              </div>

              {/* Tab Content */}
              <AnimatePresence mode="wait">
                {/* Overview Tab */}
                {activeTab === "overview" && (
                  <motion.div
                    key="overview"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="space-y-6"
                  >
              {/* Charts Row */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Condition Breakdown */}
                <div className="bg-white rounded-xl border border-slate-200 p-5">
                  <h3 className="font-semibold text-slate-800 mb-4">
                    Condition Breakdown
                    {selectedYear > 0 && (
                      <span className="ml-2 text-xs font-normal text-red-500">(Year +{selectedYear} projection)</span>
                    )}
                  </h3>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={pieChartData}
                          dataKey="value"
                          nameKey="name"
                          cx="50%"
                          cy="50%"
                          innerRadius={50}
                          outerRadius={80}
                          paddingAngle={2}
                        >
                          {pieChartData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip content={<CustomTooltip />} />
                        <Legend 
                          verticalAlign="bottom" 
                          height={36}
                          formatter={(value) => <span className="text-sm text-slate-600">{value}</span>}
                        />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* PCI Degradation Timeline */}
                <div className="bg-white rounded-xl border border-slate-200 p-5">
                  <h3 className="font-semibold text-slate-800 mb-4">
                    PCI Degradation Timeline
                  </h3>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={forecastTimelineData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis 
                          dataKey="year" 
                          tick={{ fontSize: 11, fill: '#64748b' }}
                          axisLine={{ stroke: '#cbd5e1' }}
                        />
                        <YAxis 
                          domain={[0, 100]}
                          tick={{ fontSize: 11, fill: '#64748b' }}
                          axisLine={{ stroke: '#cbd5e1' }}
                        />
                        <Tooltip 
                          content={({ active, payload, label }) => {
                            if (active && payload && payload.length) {
                              const data = payload[0].payload;
                              return (
                                <div className="bg-white p-3 rounded-lg shadow-lg border border-slate-200 text-sm">
                                  <p className="font-semibold text-slate-900">{label}</p>
                                  <p className="text-slate-600">Avg PCI: <span className="font-medium" style={{ color: getPCIColor(data.avgPCI) }}>{data.avgPCI}</span></p>
                                  <p className="text-slate-600">Critical: <span className="font-medium text-red-600">{data.criticalSections}</span></p>
                                  <p className="text-slate-600">Poor: <span className="font-medium text-orange-600">{data.poorSections}</span></p>
                                </div>
                              );
                            }
                            return null;
                          }}
                        />
                        <defs>
                          <linearGradient id="colorPCI" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#f97316" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="#f97316" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <Area 
                          type="monotone" 
                          dataKey="avgPCI" 
                          stroke="#f97316" 
                          strokeWidth={2}
                          fill="url(#colorPCI)"
                          name="Average PCI"
                        />
                        {/* Reference line at selected year */}
                        {selectedYear > 0 && (
                          <Line
                            type="monotone"
                            dataKey={() => forecastTimelineData[selectedYear]?.avgPCI}
                            stroke="transparent"
                          />
                        )}
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>

              {/* Road Sections Table */}
              <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
                  <h3 className="font-semibold text-slate-800">
                    Road Segments
                    {selectedYear > 0 && (
                      <span className="ml-2 text-xs font-normal text-red-500">(Year +{selectedYear} projection)</span>
                    )}
                  </h3>
                  <span className="text-sm text-slate-500">
                    Showing {projectedRoadSegments.length} segments
                  </span>
                </div>
                <div className="overflow-x-auto max-h-80">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 sticky top-0">
                      <tr>
                        <th className="text-left px-5 py-3 font-medium text-slate-600">Section</th>
                        <th className="text-left px-5 py-3 font-medium text-slate-600">Direction</th>
                        <th className="text-left px-5 py-3 font-medium text-slate-600">Pavement</th>
                        <th className="text-center px-5 py-3 font-medium text-slate-600">Current PCI</th>
                        {selectedYear > 0 && (
                          <th className="text-center px-5 py-3 font-medium text-slate-600">Projected PCI</th>
                        )}
                        <th className="text-center px-5 py-3 font-medium text-slate-600">Condition</th>
                        <th className="text-right px-5 py-3 font-medium text-slate-600">Daily Traffic</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {projectedRoadSegments.map((segment, index) => (
                        <tr key={index} className="hover:bg-slate-50">
                          <td className="px-5 py-3 text-slate-900">
                            {segment.section_from} → {segment.section_to}
                          </td>
                          <td className="px-5 py-3 text-slate-600">{segment.direction}</td>
                          <td className="px-5 py-3 text-slate-600">{segment.pavement_type}</td>
                          <td className="px-5 py-3 text-center">
                            <span 
                              className="font-medium"
                              style={{ color: getPCIColor(segment.originalPCI || segment.pci) }}
                            >
                              {(segment.originalPCI || segment.pci).toFixed(1)}
                            </span>
                          </td>
                          {selectedYear > 0 && (
                            <td className="px-5 py-3 text-center">
                              <div className="flex items-center justify-center gap-1">
                                <span 
                                  className="font-medium"
                                  style={{ color: getPCIColor(segment.pci) }}
                                >
                                  {segment.pci.toFixed(1)}
                                </span>
                                <ArrowDown size={12} className="text-red-500" />
                              </div>
                            </td>
                          )}
                          <td className="px-5 py-3 text-center">
                            <span className={clsx(
                              "px-2 py-1 rounded-full text-xs font-medium",
                              CONDITION_BG_COLORS[segment.condition],
                              CONDITION_TEXT_COLORS[segment.condition]
                            )}>
                              {segment.condition}
                            </span>
                          </td>
                          <td className="px-5 py-3 text-right text-slate-600">
                            {(segment.aadt || 0).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
                  </motion.div>
                )}

                {/* Forecast Tab */}
                {activeTab === "forecast" && (
                  <motion.div
                    key="forecast"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="space-y-6"
                  >
                    {/* Forecast Summary Cards */}
                    {forecastSummary && (
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="bg-white rounded-xl border border-slate-200 p-5">
                          <p className="text-sm text-slate-500">Current Avg PCI</p>
                          <p className="text-2xl font-bold" style={{ color: getPCIColor(forecastSummary.average_pci) }}>
                            {forecastSummary.average_pci.toFixed(1)}
                          </p>
                        </div>
                        <div className="bg-white rounded-xl border border-slate-200 p-5">
                          <p className="text-sm text-slate-500">Critical Sections</p>
                          <p className="text-2xl font-bold text-red-600">
                            {forecastSummary.critical_sections}
                          </p>
                        </div>
                        <div className="bg-white rounded-xl border border-slate-200 p-5">
                          <p className="text-sm text-slate-500">Poor Sections</p>
                          <p className="text-2xl font-bold text-orange-600">
                            {forecastSummary.poor_sections}
                          </p>
                        </div>
                        <div className="bg-white rounded-xl border border-slate-200 p-5">
                          <p className="text-sm text-slate-500">Potential Savings</p>
                          <p className="text-2xl font-bold text-green-600">
                            {forecastSummary.potential_savings >= 1000000 
                              ? formatCurrency(forecastSummary.potential_savings / 1000000, 'M')
                              : formatCurrency(forecastSummary.potential_savings / 1000, 'K')}
                          </p>
                        </div>
                      </div>
                    )}

                    {/* Degradation Timeline Chart */}
                    <div className="bg-white rounded-xl border border-slate-200 p-5">
                      <h3 className="font-semibold text-slate-800 mb-4">10-Year PCI Degradation Forecast</h3>
                      <div className="h-72">
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart data={forecastTimelineData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                            <XAxis dataKey="year" tick={{ fontSize: 11, fill: '#64748b' }} />
                            <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#64748b' }} />
                            <Tooltip 
                              content={({ active, payload, label }) => {
                                if (active && payload && payload.length) {
                                  const data = payload[0].payload;
                                  return (
                                    <div className="bg-white p-3 rounded-lg shadow-lg border border-slate-200 text-sm">
                                      <p className="font-semibold text-slate-900">{label}</p>
                                      <p className="text-slate-600">Avg PCI: <span className="font-medium" style={{ color: getPCIColor(data.avgPCI) }}>{data.avgPCI}</span></p>
                                      <p className="text-slate-600">At Risk: <span className="font-medium text-red-600">{data.atRisk} sections</span></p>
                                    </div>
                                  );
                                }
                                return null;
                              }}
                            />
                            <defs>
                              <linearGradient id="colorPCI2" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#f97316" stopOpacity={0.3}/>
                                <stop offset="95%" stopColor="#f97316" stopOpacity={0}/>
                              </linearGradient>
                            </defs>
                            <Area type="monotone" dataKey="avgPCI" stroke="#f97316" strokeWidth={2} fill="url(#colorPCI2)" />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Critical Sections Growth */}
                    <div className="bg-white rounded-xl border border-slate-200 p-5">
                      <h3 className="font-semibold text-slate-800 mb-4">Critical & Poor Sections Over Time</h3>
                      <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={forecastTimelineData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                            <XAxis dataKey="year" tick={{ fontSize: 11, fill: '#64748b' }} />
                            <YAxis tick={{ fontSize: 11, fill: '#64748b' }} />
                            <Tooltip />
                            <Bar dataKey="criticalSections" name="Critical" fill="#ef4444" stackId="a" />
                            <Bar dataKey="poorSections" name="Poor" fill="#f97316" stackId="a" />
                            <Legend />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>

                    {/* Intervention Schedule Table */}
                    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                      <div className="px-5 py-4 border-b border-slate-200">
                        <h3 className="font-semibold text-slate-800">Optimal Intervention Schedule</h3>
                      </div>
                      <div className="overflow-x-auto max-h-64">
                        <table className="w-full text-sm">
                          <thead className="bg-slate-50 sticky top-0">
                            <tr>
                              <th className="text-left px-5 py-3 font-medium text-slate-600">Section</th>
                              <th className="text-center px-5 py-3 font-medium text-slate-600">Current PCI</th>
                              <th className="text-center px-5 py-3 font-medium text-slate-600">Years to Critical</th>
                              <th className="text-center px-5 py-3 font-medium text-slate-600">Optimal Year</th>
                              <th className="text-right px-5 py-3 font-medium text-slate-600">Cost Savings</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {forecasts.slice(0, 10).map((forecast, index) => (
                              <tr key={index} className="hover:bg-slate-50">
                                <td className="px-5 py-3 text-slate-900">{forecast.section}</td>
                                <td className="px-5 py-3 text-center">
                                  <span style={{ color: getPCIColor(forecast.current_pci) }} className="font-medium">
                                    {forecast.current_pci.toFixed(1)}
                                  </span>
                                </td>
                                <td className="px-5 py-3 text-center">
                                  <span className={clsx(
                                    "px-2 py-1 rounded-full text-xs font-medium",
                                    forecast.years_to_critical <= 3 ? "bg-red-100 text-red-700" : 
                                    forecast.years_to_critical <= 5 ? "bg-orange-100 text-orange-700" : 
                                    "bg-green-100 text-green-700"
                                  )}>
                                    {forecast.years_to_critical} years
                                  </span>
                                </td>
                                <td className="px-5 py-3 text-center font-medium text-orange-600">
                                  Year {forecast.optimal_intervention_year}
                                </td>
                                <td className="px-5 py-3 text-right text-green-600 font-medium">
                                  {formatCurrency(forecast.cost_savings_optimal / 1000, 'K')}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </motion.div>
                )}

                {/* Economic Impact Tab */}
                {activeTab === "economic" && stats && (
                  <motion.div
                    key="economic"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="space-y-6"
                  >
                    {/* Economic Summary Cards */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="bg-white rounded-xl border border-slate-200 p-5">
                        <div className="flex items-center gap-2 mb-2">
                          <Car size={18} className="text-red-500" />
                          <p className="text-sm text-slate-500">Vehicle Damage</p>
                        </div>
                        <p className="text-2xl font-bold text-red-600">
                          {formatCurrency(stats.economicImpacts.reduce((sum, i) => sum + i.annual_vehicle_damage_cost, 0) / 1000000, 'M')}
                        </p>
                        <p className="text-xs text-slate-400 mt-1">Annual cost</p>
                      </div>
                      <div className="bg-white rounded-xl border border-slate-200 p-5">
                        <div className="flex items-center gap-2 mb-2">
                          <Fuel size={18} className="text-amber-500" />
                          <p className="text-sm text-slate-500">Fuel Waste</p>
                        </div>
                        <p className="text-2xl font-bold text-amber-600">
                          {formatCurrency(stats.economicImpacts.reduce((sum, i) => sum + i.annual_fuel_waste_cost, 0) / 1000000, 'M')}
                        </p>
                        <p className="text-xs text-slate-400 mt-1">Annual cost</p>
                      </div>
                      <div className="bg-white rounded-xl border border-slate-200 p-5">
                        <div className="flex items-center gap-2 mb-2">
                          <Truck size={18} className="text-blue-500" />
                          <p className="text-sm text-slate-500">Freight Delays</p>
                        </div>
                        <p className="text-2xl font-bold text-blue-600">
                          {formatCurrency(stats.economicImpacts.reduce((sum, i) => sum + i.annual_freight_delay_cost, 0) / 1000000, 'M')}
                        </p>
                        <p className="text-xs text-slate-400 mt-1">Annual cost</p>
                      </div>
                      <div className="bg-white rounded-xl border border-slate-200 p-5">
                        <div className="flex items-center gap-2 mb-2">
                          <DollarSign size={18} className="text-green-500" />
                          <p className="text-sm text-slate-500">Total Impact</p>
                        </div>
                        <p className="text-2xl font-bold text-slate-900">
                          {formatCurrency(stats.totalAnnualCost / 1000000, 'M')}
                        </p>
                        <p className="text-xs text-slate-400 mt-1">Per year</p>
                      </div>
                    </div>

                    {/* Cost Breakdown Pie Chart */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      <div className="bg-white rounded-xl border border-slate-200 p-5">
                        <h3 className="font-semibold text-slate-800 mb-4">Cost Breakdown</h3>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                              <Pie
                                data={[
                                  { name: "Vehicle Damage", value: stats.economicImpacts.reduce((sum, i) => sum + i.annual_vehicle_damage_cost, 0), color: "#ef4444" },
                                  { name: "Fuel Waste", value: stats.economicImpacts.reduce((sum, i) => sum + i.annual_fuel_waste_cost, 0), color: "#f59e0b" },
                                  { name: "Freight Delays", value: stats.economicImpacts.reduce((sum, i) => sum + i.annual_freight_delay_cost, 0), color: "#3b82f6" },
                                ]}
                                dataKey="value"
                                nameKey="name"
                                cx="50%"
                                cy="50%"
                                innerRadius={50}
                                outerRadius={80}
                              >
                                {[
                                  { color: "#ef4444" },
                                  { color: "#f59e0b" },
                                  { color: "#3b82f6" },
                                ].map((entry, index) => (
                                  <Cell key={`cell-${index}`} fill={entry.color} />
                                ))}
                              </Pie>
                              <Tooltip formatter={(value: number) => formatCurrency(value / 1000000, 'M')} />
                              <Legend />
                            </PieChart>
                          </ResponsiveContainer>
                        </div>
                      </div>

                      {/* ROI Analysis */}
                      <div className="bg-white rounded-xl border border-slate-200 p-5">
                        <h3 className="font-semibold text-slate-800 mb-4">Repair ROI Analysis</h3>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={stats.economicImpacts.slice(0, 8).map((impact, i) => ({
                              name: `Sec ${i + 1}`,
                              roi: impact.roi_if_repaired,
                            }))}>
                              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#64748b' }} />
                              <YAxis tick={{ fontSize: 11, fill: '#64748b' }} tickFormatter={(v) => `${v}%`} />
                              <Tooltip formatter={(value: number) => `${value.toFixed(1)}%`} />
                              <Bar dataKey="roi" name="ROI if Repaired" fill="#22c55e">
                                {stats.economicImpacts.slice(0, 8).map((_, index) => (
                                  <Cell key={`cell-${index}`} fill={index % 2 === 0 ? "#22c55e" : "#16a34a"} />
                                ))}
                              </Bar>
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    </div>

                    {/* Economic Impact Table */}
                    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                      <div className="px-5 py-4 border-b border-slate-200">
                        <h3 className="font-semibold text-slate-800">
                          Section Economic Impact
                          {selectedYear > 0 && <span className="ml-2 text-xs font-normal text-red-500">(Year +{selectedYear} projection)</span>}
                        </h3>
                      </div>
                      <div className="overflow-x-auto max-h-64">
                        <table className="w-full text-sm">
                          <thead className="bg-slate-50 sticky top-0">
                            <tr>
                              <th className="text-left px-5 py-3 font-medium text-slate-600">Section</th>
                              <th className="text-center px-5 py-3 font-medium text-slate-600">PCI</th>
                              <th className="text-right px-5 py-3 font-medium text-slate-600">Vehicle Damage</th>
                              <th className="text-right px-5 py-3 font-medium text-slate-600">Fuel Waste</th>
                              <th className="text-right px-5 py-3 font-medium text-slate-600">Freight Delay</th>
                              <th className="text-right px-5 py-3 font-medium text-slate-600">Total</th>
                              <th className="text-center px-5 py-3 font-medium text-slate-600">ROI</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {stats.economicImpacts.map((impact, index) => (
                              <tr key={index} className="hover:bg-slate-50">
                                <td className="px-5 py-3 text-slate-900">{impact.section}</td>
                                <td className="px-5 py-3 text-center">
                                  <span style={{ color: getPCIColor(impact.pci) }} className="font-medium">
                                    {impact.pci.toFixed(1)}
                                  </span>
                                </td>
                                <td className="px-5 py-3 text-right text-slate-600">
                                  {formatCurrency(impact.annual_vehicle_damage_cost / 1000, 'K')}
                                </td>
                                <td className="px-5 py-3 text-right text-slate-600">
                                  {formatCurrency(impact.annual_fuel_waste_cost / 1000, 'K')}
                                </td>
                                <td className="px-5 py-3 text-right text-slate-600">
                                  {formatCurrency(impact.annual_freight_delay_cost / 1000, 'K')}
                                </td>
                                <td className="px-5 py-3 text-right font-medium text-slate-900">
                                  {formatCurrency(impact.total_annual_cost / 1000, 'K')}
                                </td>
                                <td className="px-5 py-3 text-center">
                                  <span className="px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">
                                    {impact.roi_if_repaired.toFixed(0)}%
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </motion.div>
                )}

                {/* Winter Resilience Tab */}
                {activeTab === "winter" && (
                  <motion.div
                    key="winter"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="space-y-6"
                  >
                    {winterLoading ? (
                      <div className="flex items-center justify-center h-64">
                        <div className="text-center">
                          <Snowflake className="animate-spin mx-auto text-cyan-500 mb-4" size={40} />
                          <p className="text-slate-500">Analyzing winter vulnerability...</p>
                        </div>
                      </div>
                    ) : (
                      <>
                        {/* Winter Summary Cards */}
                        {winterSummary && (
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div className="bg-white rounded-xl border border-slate-200 p-5">
                              <div className="flex items-center gap-2 mb-2">
                                <ThermometerSnowflake size={18} className="text-cyan-500" />
                                <p className="text-sm text-slate-500">Freeze-Thaw Risk</p>
                              </div>
                              <p className="text-2xl font-bold text-red-600">
                                {winterSummary.risk_distribution.severe + winterSummary.risk_distribution.high}
                              </p>
                              <p className="text-xs text-slate-400 mt-1">Severe/High risk sections</p>
                            </div>
                            <div className="bg-white rounded-xl border border-slate-200 p-5">
                              <div className="flex items-center gap-2 mb-2">
                                <AlertTriangle size={18} className="text-amber-500" />
                                <p className="text-sm text-slate-500">Threshold Risk</p>
                              </div>
                              <p className="text-2xl font-bold text-amber-600">
                                {winterSummary.sections_crossing_threshold}
                              </p>
                              <p className="text-xs text-slate-400 mt-1">Will cross critical threshold</p>
                            </div>
                            <div className="bg-white rounded-xl border border-slate-200 p-5">
                              <div className="flex items-center gap-2 mb-2">
                                <TrendingDown size={18} className="text-orange-500" />
                                <p className="text-sm text-slate-500">Avg PCI Loss</p>
                              </div>
                              <p className="text-2xl font-bold text-orange-600">
                                -{winterSummary.average_expected_pci_loss.toFixed(1)}
                              </p>
                              <p className="text-xs text-slate-400 mt-1">Expected this winter</p>
                            </div>
                            <div className="bg-white rounded-xl border border-slate-200 p-5">
                              <div className="flex items-center gap-2 mb-2">
                                <DollarSign size={18} className="text-green-500" />
                                <p className="text-sm text-slate-500">Potential Savings</p>
                              </div>
                              <p className="text-2xl font-bold text-green-600">
                                {formatCurrency(winterSummary.financials.total_potential_savings / 1000000, 'M')}
                              </p>
                              <p className="text-xs text-slate-400 mt-1">Pre-winter intervention ROI</p>
                            </div>
                          </div>
                        )}

                        {/* Risk Distribution & PCI Loss Charts */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                          {/* Risk Distribution Chart */}
                          {winterSummary && (
                            <div className="bg-white rounded-xl border border-slate-200 p-5">
                              <h3 className="font-semibold text-slate-800 mb-4">Winter Risk Distribution</h3>
                              <div className="h-64">
                                <ResponsiveContainer width="100%" height="100%">
                                  <PieChart>
                                    <Pie
                                      data={[
                                        { name: "Severe", value: winterSummary.risk_distribution.severe, color: "#ef4444" },
                                        { name: "High", value: winterSummary.risk_distribution.high, color: "#f97316" },
                                        { name: "Moderate", value: winterSummary.risk_distribution.moderate, color: "#f59e0b" },
                                        { name: "Low", value: winterSummary.risk_distribution.low, color: "#22c55e" },
                                      ].filter(d => d.value > 0)}
                                      dataKey="value"
                                      nameKey="name"
                                      cx="50%"
                                      cy="50%"
                                      innerRadius={50}
                                      outerRadius={80}
                                    >
                                      {[
                                        { color: "#ef4444" },
                                        { color: "#f97316" },
                                        { color: "#f59e0b" },
                                        { color: "#22c55e" },
                                      ].map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                      ))}
                                    </Pie>
                                    <Tooltip />
                                    <Legend />
                                  </PieChart>
                                </ResponsiveContainer>
                              </div>
                            </div>
                          )}

                          {/* Expected PCI Loss by Section */}
                          <div className="bg-white rounded-xl border border-slate-200 p-5">
                            <h3 className="font-semibold text-slate-800 mb-4">Expected Winter PCI Loss</h3>
                            <div className="h-64">
                              <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={winterVulnerabilities.slice(0, 10).map((v, i) => ({
                                  name: `${v.section_from?.substring(0, 8) || `Sec ${i+1}`}`,
                                  loss: v.expected_pci_loss,
                                  current: v.current_pci,
                                  post: v.post_winter_pci,
                                }))}>
                                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                  <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#64748b' }} />
                                  <YAxis tick={{ fontSize: 11, fill: '#64748b' }} />
                                  <Tooltip 
                                    content={({ active, payload }) => {
                                      if (active && payload && payload.length) {
                                        const data = payload[0].payload;
                                        return (
                                          <div className="bg-white p-3 rounded-lg shadow-lg border border-slate-200 text-sm">
                                            <p className="font-semibold text-slate-900">{data.name}</p>
                                            <p className="text-slate-600">Current PCI: <span className="font-medium">{data.current.toFixed(1)}</span></p>
                                            <p className="text-red-600">PCI Loss: <span className="font-medium">-{data.loss.toFixed(1)}</span></p>
                                            <p className="text-slate-600">Post-Winter: <span className="font-medium">{data.post.toFixed(1)}</span></p>
                                          </div>
                                        );
                                      }
                                      return null;
                                    }}
                                  />
                                  <Bar dataKey="loss" name="PCI Loss" fill="#ef4444">
                                    {winterVulnerabilities.slice(0, 10).map((v, index) => (
                                      <Cell 
                                        key={`cell-${index}`} 
                                        fill={v.risk_level === 'severe' ? '#ef4444' : 
                                              v.risk_level === 'high' ? '#f97316' :
                                              v.risk_level === 'moderate' ? '#f59e0b' : '#22c55e'} 
                                      />
                                    ))}
                                  </Bar>
                                </BarChart>
                              </ResponsiveContainer>
                            </div>
                          </div>
                        </div>

                        {/* Winter Vulnerability Table */}
                        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                          <div className="px-5 py-4 border-b border-slate-200">
                            <h3 className="font-semibold text-slate-800">Freeze-Thaw Vulnerability Analysis</h3>
                          </div>
                          <div className="overflow-x-auto max-h-64">
                            <table className="w-full text-sm">
                              <thead className="bg-slate-50 sticky top-0">
                                <tr>
                                  <th className="text-left px-5 py-3 font-medium text-slate-600">Section</th>
                                  <th className="text-center px-5 py-3 font-medium text-slate-600">Current PCI</th>
                                  <th className="text-center px-5 py-3 font-medium text-slate-600">Risk Level</th>
                                  <th className="text-center px-5 py-3 font-medium text-slate-600">Expected Loss</th>
                                  <th className="text-center px-5 py-3 font-medium text-slate-600">Post-Winter</th>
                                  <th className="text-center px-5 py-3 font-medium text-slate-600">Threshold</th>
                                  <th className="text-left px-5 py-3 font-medium text-slate-600">Recommendation</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-100">
                                {winterVulnerabilities.map((vuln, index) => (
                                  <tr key={index} className="hover:bg-slate-50">
                                    <td className="px-5 py-3 text-slate-900">
                                      {vuln.section_from} → {vuln.section_to}
                                    </td>
                                    <td className="px-5 py-3 text-center">
                                      <span style={{ color: getPCIColor(vuln.current_pci) }} className="font-medium">
                                        {vuln.current_pci.toFixed(1)}
                                      </span>
                                    </td>
                                    <td className="px-5 py-3 text-center">
                                      <span className={clsx(
                                        "px-2 py-1 rounded-full text-xs font-medium",
                                        vuln.risk_level === 'severe' ? "bg-red-100 text-red-700" :
                                        vuln.risk_level === 'high' ? "bg-orange-100 text-orange-700" :
                                        vuln.risk_level === 'moderate' ? "bg-amber-100 text-amber-700" :
                                        "bg-green-100 text-green-700"
                                      )}>
                                        {vuln.risk_level.charAt(0).toUpperCase() + vuln.risk_level.slice(1)}
                                      </span>
                                    </td>
                                    <td className="px-5 py-3 text-center text-red-600 font-medium">
                                      -{vuln.expected_pci_loss.toFixed(1)}
                                    </td>
                                    <td className="px-5 py-3 text-center">
                                      <span style={{ color: getPCIColor(vuln.post_winter_pci) }} className="font-medium">
                                        {vuln.post_winter_pci.toFixed(1)}
                                      </span>
                                    </td>
                                    <td className="px-5 py-3 text-center">
                                      {vuln.crosses_threshold ? (
                                        <span className="px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
                                          {vuln.threshold_crossed}
                                        </span>
                                      ) : (
                                        <span className="text-slate-400">-</span>
                                      )}
                                    </td>
                                    <td className="px-5 py-3 text-slate-600 text-xs max-w-[200px] truncate" title={vuln.recommendation}>
                                      {vuln.recommendation}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>

                        {/* Pre-Winter Intervention Analysis */}
                        {winterInterventions.length > 0 && (
                          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                            <div className="px-5 py-4 border-b border-slate-200">
                              <h3 className="font-semibold text-slate-800">Pre-Winter Intervention ROI</h3>
                              <p className="text-xs text-slate-500 mt-1">Option A: Pre-winter treatment vs Option B: Spring emergency repair</p>
                            </div>
                            <div className="overflow-x-auto max-h-64">
                              <table className="w-full text-sm">
                                <thead className="bg-slate-50 sticky top-0">
                                  <tr>
                                    <th className="text-left px-5 py-3 font-medium text-slate-600">Section</th>
                                    <th className="text-center px-5 py-3 font-medium text-slate-600">Current PCI</th>
                                    <th className="text-center px-5 py-3 font-medium text-slate-600">Pre-Winter Cost</th>
                                    <th className="text-center px-5 py-3 font-medium text-slate-600">Spring Repair</th>
                                    <th className="text-center px-5 py-3 font-medium text-slate-600">Savings</th>
                                    <th className="text-center px-5 py-3 font-medium text-slate-600">ROI</th>
                                    <th className="text-left px-5 py-3 font-medium text-slate-600">Recommendation</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                  {winterInterventions.map((intervention, index) => (
                                    <tr key={index} className="hover:bg-slate-50">
                                      <td className="px-5 py-3 text-slate-900">{intervention.section}</td>
                                      <td className="px-5 py-3 text-center">
                                        <span style={{ color: getPCIColor(intervention.current_pci) }} className="font-medium">
                                          {intervention.current_pci.toFixed(1)}
                                        </span>
                                      </td>
                                      <td className="px-5 py-3 text-center text-slate-600">
                                        {formatCurrency(intervention.option_a.cost / 1000, 'K')}
                                      </td>
                                      <td className="px-5 py-3 text-center text-red-600">
                                        {formatCurrency(intervention.option_b.emergency_repair_cost / 1000, 'K')}
                                      </td>
                                      <td className="px-5 py-3 text-center text-green-600 font-medium">
                                        {formatCurrency(intervention.analysis.cost_savings / 1000, 'K')}
                                      </td>
                                      <td className="px-5 py-3 text-center">
                                        <span className={clsx(
                                          "px-2 py-1 rounded-full text-xs font-medium",
                                          intervention.analysis.roi_multiplier >= 2 ? "bg-green-100 text-green-700" :
                                          intervention.analysis.roi_multiplier >= 1.5 ? "bg-cyan-100 text-cyan-700" :
                                          "bg-slate-100 text-slate-700"
                                        )}>
                                          {intervention.analysis.roi_multiplier.toFixed(1)}x
                                        </span>
                                      </td>
                                      <td className="px-5 py-3 text-slate-600 text-xs max-w-[180px] truncate" title={intervention.analysis.recommendation}>
                                        {intervention.analysis.recommendation}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </motion.div>
                )}

                {/* Corridor Optimization Tab */}
                {activeTab === "corridor" && (
                  <motion.div
                    key="corridor"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="space-y-6"
                  >
                    {corridorLoading ? (
                      <div className="flex items-center justify-center h-64">
                        <div className="text-center">
                          <Route className="animate-spin mx-auto text-purple-500 mb-4" size={40} />
                          <p className="text-slate-500">Analyzing corridor optimization...</p>
                        </div>
                      </div>
                    ) : (
                      <>
                        {/* Corridor Summary Cards */}
                        {corridorSummary && (
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div className="bg-white rounded-xl border border-slate-200 p-5">
                              <div className="flex items-center gap-2 mb-2">
                                <Package size={18} className="text-purple-500" />
                                <p className="text-sm text-slate-500">Bundle Opportunities</p>
                              </div>
                              <p className="text-2xl font-bold text-purple-600">
                                {corridorSummary.bundles.total_bundles}
                              </p>
                              <p className="text-xs text-slate-400 mt-1">{corridorSummary.bundles.total_bundled_length_km.toFixed(1)} km bundleable</p>
                            </div>
                            <div className="bg-white rounded-xl border border-slate-200 p-5">
                              <div className="flex items-center gap-2 mb-2">
                                <BadgeDollarSign size={18} className="text-green-500" />
                                <p className="text-sm text-slate-500">Potential Savings</p>
                              </div>
                              <p className="text-2xl font-bold text-green-600">
                                {formatCurrency(corridorSummary.savings.total_savings / 1000000, 'M')}
                              </p>
                              <p className="text-xs text-slate-400 mt-1">{corridorSummary.savings.average_savings_percent.toFixed(0)}% avg savings</p>
                            </div>
                            <div className="bg-white rounded-xl border border-slate-200 p-5">
                              <div className="flex items-center gap-2 mb-2">
                                <ArrowLeftRight size={18} className="text-blue-500" />
                                <p className="text-sm text-slate-500">Directional Issues</p>
                              </div>
                              <p className="text-2xl font-bold text-blue-600">
                                {corridorSummary.directional.directions_with_disparity}
                              </p>
                              <p className="text-xs text-slate-400 mt-1">Sections with disparity</p>
                            </div>
                            <div className="bg-white rounded-xl border border-slate-200 p-5">
                              <div className="flex items-center gap-2 mb-2">
                                <Construction size={18} className="text-orange-500" />
                                <p className="text-sm text-slate-500">Top Opportunity</p>
                              </div>
                              <p className="text-2xl font-bold text-orange-600">
                                {formatCurrency(corridorSummary.top_opportunity.savings / 1000000, 'M')}
                              </p>
                              <p className="text-xs text-slate-400 mt-1">{corridorSummary.top_opportunity.bundle_id}</p>
                            </div>
                          </div>
                        )}

                        {/* Bundle Analysis Charts */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                          {/* Savings by Bundle */}
                          <div className="bg-white rounded-xl border border-slate-200 p-5">
                            <h3 className="font-semibold text-slate-800 mb-4">Bundling Savings Potential</h3>
                            <div className="h-64">
                              <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={bundles.slice(0, 8).map((bundle) => ({
                                  name: bundle.bundle_id,
                                  individual: bundle.cost_analysis.individual_approach_cost / 1000000,
                                  bundled: bundle.cost_analysis.bundled_approach_cost / 1000000,
                                  savings: bundle.cost_analysis.savings / 1000000,
                                }))}>
                                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                                  <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#64748b' }} />
                                  <YAxis tick={{ fontSize: 11, fill: '#64748b' }} tickFormatter={(v) => `$${v}M`} />
                                  <Tooltip 
                                    formatter={(value: number) => `$${value.toFixed(2)}M`}
                                    labelFormatter={(label) => `Bundle: ${label}`}
                                  />
                                  <Legend />
                                  <Bar dataKey="individual" name="Individual Cost" fill="#ef4444" />
                                  <Bar dataKey="bundled" name="Bundled Cost" fill="#22c55e" />
                                </BarChart>
                              </ResponsiveContainer>
                            </div>
                          </div>

                          {/* Savings Distribution Pie */}
                          {corridorSummary && (
                            <div className="bg-white rounded-xl border border-slate-200 p-5">
                              <h3 className="font-semibold text-slate-800 mb-4">Cost Comparison Overview</h3>
                              <div className="h-64">
                                <ResponsiveContainer width="100%" height="100%">
                                  <PieChart>
                                    <Pie
                                      data={[
                                        { name: "Bundled Cost", value: corridorSummary.savings.total_bundled_cost, color: "#22c55e" },
                                        { name: "Savings", value: corridorSummary.savings.total_savings, color: "#a855f7" },
                                      ]}
                                      dataKey="value"
                                      nameKey="name"
                                      cx="50%"
                                      cy="50%"
                                      innerRadius={50}
                                      outerRadius={80}
                                    >
                                      <Cell fill="#22c55e" />
                                      <Cell fill="#a855f7" />
                                    </Pie>
                                    <Tooltip formatter={(value: number) => formatCurrency(value / 1000000, 'M')} />
                                    <Legend />
                                  </PieChart>
                                </ResponsiveContainer>
                              </div>
                              <div className="mt-4 text-center">
                                <p className="text-sm text-slate-500">
                                  Individual approach: <span className="font-semibold text-red-600">{formatCurrency(corridorSummary.savings.total_individual_cost / 1000000, 'M')}</span>
                                </p>
                                <p className="text-sm text-slate-500">
                                  Bundled approach: <span className="font-semibold text-green-600">{formatCurrency(corridorSummary.savings.total_bundled_cost / 1000000, 'M')}</span>
                                </p>
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Bundle Opportunities Table */}
                        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                          <div className="px-5 py-4 border-b border-slate-200">
                            <h3 className="font-semibold text-slate-800">Multi-Section Bundle Opportunities</h3>
                            <p className="text-xs text-slate-500 mt-1">Adjacent sections that can be repaired together for cost savings</p>
                          </div>
                          <div className="overflow-x-auto max-h-72">
                            <table className="w-full text-sm">
                              <thead className="bg-slate-50 sticky top-0">
                                <tr>
                                  <th className="text-left px-5 py-3 font-medium text-slate-600">Bundle ID</th>
                                  <th className="text-center px-5 py-3 font-medium text-slate-600">Sections</th>
                                  <th className="text-center px-5 py-3 font-medium text-slate-600">Length</th>
                                  <th className="text-center px-5 py-3 font-medium text-slate-600">Avg PCI</th>
                                  <th className="text-right px-5 py-3 font-medium text-slate-600">Individual</th>
                                  <th className="text-right px-5 py-3 font-medium text-slate-600">Bundled</th>
                                  <th className="text-center px-5 py-3 font-medium text-slate-600">Savings</th>
                                  <th className="text-center px-5 py-3 font-medium text-slate-600">Federal $</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-100">
                                {bundles.map((bundle, index) => (
                                  <tr key={index} className="hover:bg-slate-50">
                                    <td className="px-5 py-3 text-slate-900 font-medium">{bundle.bundle_id}</td>
                                    <td className="px-5 py-3 text-center text-slate-600">{bundle.condition.sections_count}</td>
                                    <td className="px-5 py-3 text-center text-slate-600">{bundle.geometry.total_length_km.toFixed(1)} km</td>
                                    <td className="px-5 py-3 text-center">
                                      <span style={{ color: getPCIColor(bundle.condition.average_pci) }} className="font-medium">
                                        {bundle.condition.average_pci.toFixed(1)}
                                      </span>
                                    </td>
                                    <td className="px-5 py-3 text-right text-red-600">
                                      {formatCurrency(bundle.cost_analysis.individual_approach_cost / 1000000, 'M')}
                                    </td>
                                    <td className="px-5 py-3 text-right text-green-600">
                                      {formatCurrency(bundle.cost_analysis.bundled_approach_cost / 1000000, 'M')}
                                    </td>
                                    <td className="px-5 py-3 text-center">
                                      <span className="px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
                                        {bundle.cost_analysis.savings_percent.toFixed(0)}%
                                      </span>
                                    </td>
                                    <td className="px-5 py-3 text-center">
                                      {bundle.benefits.qualifies_for_federal_funding ? (
                                        <span className="px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-700">
                                          Eligible
                                        </span>
                                      ) : (
                                        <span className="text-slate-400">-</span>
                                      )}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>

                        {/* Directional Analysis Table */}
                        {directionalAnalyses.length > 0 && (
                          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                            <div className="px-5 py-4 border-b border-slate-200">
                              <h3 className="font-semibold text-slate-800">Directional Condition Analysis</h3>
                              <p className="text-xs text-slate-500 mt-1">Compare road conditions between directions - identifies single-direction repair opportunities</p>
                            </div>
                            <div className="overflow-x-auto max-h-64">
                              <table className="w-full text-sm">
                                <thead className="bg-slate-50 sticky top-0">
                                  <tr>
                                    <th className="text-left px-5 py-3 font-medium text-slate-600">Highway</th>
                                    <th className="text-center px-5 py-3 font-medium text-slate-600">Direction 1</th>
                                    <th className="text-center px-5 py-3 font-medium text-slate-600">Direction 2</th>
                                    <th className="text-center px-5 py-3 font-medium text-slate-600">PCI Diff</th>
                                    <th className="text-center px-5 py-3 font-medium text-slate-600">Worse</th>
                                    <th className="text-right px-5 py-3 font-medium text-slate-600">Single Dir Cost</th>
                                    <th className="text-right px-5 py-3 font-medium text-slate-600">Both Cost</th>
                                    <th className="text-left px-5 py-3 font-medium text-slate-600">Recommendation</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100">
                                  {directionalAnalyses.map((analysis, index) => (
                                    <tr key={index} className="hover:bg-slate-50">
                                      <td className="px-5 py-3 text-slate-900">{analysis.highway}</td>
                                      <td className="px-5 py-3 text-center">
                                        <div className="text-xs">
                                          <span className="font-medium">{analysis.direction_1.name}</span>
                                          <br />
                                          <span style={{ color: getPCIColor(analysis.direction_1.avg_pci) }}>
                                            PCI: {analysis.direction_1.avg_pci.toFixed(1)}
                                          </span>
                                        </div>
                                      </td>
                                      <td className="px-5 py-3 text-center">
                                        <div className="text-xs">
                                          <span className="font-medium">{analysis.direction_2.name}</span>
                                          <br />
                                          <span style={{ color: getPCIColor(analysis.direction_2.avg_pci) }}>
                                            PCI: {analysis.direction_2.avg_pci.toFixed(1)}
                                          </span>
                                        </div>
                                      </td>
                                      <td className="px-5 py-3 text-center">
                                        <span className={clsx(
                                          "px-2 py-1 rounded-full text-xs font-medium",
                                          analysis.comparison.pci_difference >= 10 ? "bg-red-100 text-red-700" :
                                          analysis.comparison.pci_difference >= 5 ? "bg-amber-100 text-amber-700" :
                                          "bg-green-100 text-green-700"
                                        )}>
                                          {analysis.comparison.pci_difference.toFixed(1)}
                                        </span>
                                      </td>
                                      <td className="px-5 py-3 text-center text-slate-600">
                                        {analysis.comparison.worse_direction}
                                      </td>
                                      <td className="px-5 py-3 text-right text-green-600">
                                        {formatCurrency(analysis.recommendation.single_direction_cost / 1000000, 'M')}
                                      </td>
                                      <td className="px-5 py-3 text-right text-slate-600">
                                        {formatCurrency(analysis.recommendation.both_directions_cost / 1000000, 'M')}
                                      </td>
                                      <td className="px-5 py-3 text-slate-600 text-xs max-w-[180px] truncate" title={analysis.recommendation.action}>
                                        {analysis.recommendation.action}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Footer */}
              <footer className="flex items-center justify-between text-xs text-slate-400 pt-2">
                <div className="flex items-center gap-2">
                  <Database size={14} />
                  <span>Data Source: Transportation MCP Server</span>
                </div>
                <span>Pavement Condition Index (PCI) • Scale: 0-100</span>
              </footer>
            </div>
          )}
        </main>
      </motion.div>
    </div>
  );
}
