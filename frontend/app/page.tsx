"use client";

import dynamic from "next/dynamic";
import { useState, useEffect } from "react";
import NLQuery from "@/components/NLQuery";
import Optimizer from "@/components/Optimizer";
import RiskDashboard from "@/components/RiskDashboard";
import GovernmentDashboard from "@/components/GovernmentDashboard";
import HighwayDegradation from "@/components/HighwayDegradation";
import axios from "axios";
import { Asset, BridgeLocation } from "@/types";
import { 
  LayoutDashboard, 
  Map as MapIcon, 
  Settings, 
  Menu, 
  ChevronLeft,
  ShieldAlert,
  Building2,
  Landmark,
  TrendingDown
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import clsx from "clsx";

// Dynamically import LiveMap to avoid SSR issues with Leaflet
const LiveMap = dynamic(() => import("@/components/LiveMap"), {
  ssr: false,
  loading: () => <div className="w-full h-full flex items-center justify-center bg-slate-50 text-slate-400">Loading Intelligence Map...</div>,
});

export default function Home() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [nlBridges, setNlBridges] = useState<BridgeLocation[]>([]);
  const [nlDataSource, setNlDataSource] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showOptimizer, setShowOptimizer] = useState(false);
  const [showDashboard, setShowDashboard] = useState(false);
  const [showGovernmentDashboard, setShowGovernmentDashboard] = useState(false);
  const [showHighwayDegradation, setShowHighwayDegradation] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeView, setActiveView] = useState<'map' | 'dashboard'>('map');
  const [selectedBridge, setSelectedBridge] = useState<BridgeLocation | null>(null);

  useEffect(() => {
    fetchAssets();
  }, []);

  const fetchAssets = async () => {
    try {
      setLoading(true);
      const response = await axios.get("http://localhost:8000/api/assets");
      setAssets(response.data);
    } catch (error) {
      console.error("Error fetching assets:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleQueryResults = (results: any[], dataSource?: string) => {
    if (dataSource === 'bridges') {
      // NLP returned bridge data - store separately
      setNlBridges(results as BridgeLocation[]);
      setNlDataSource('bridges');
    } else {
      // NLP returned asset data
      setAssets(results as Asset[]);
      setNlBridges([]);
      setNlDataSource('assets');
    }
  };

  const handleBridgeSelect = (bridge: BridgeLocation) => {
    setSelectedBridge(bridge);
  };

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden font-sans text-slate-900">
      {/* Sidebar Navigation */}
      <motion.aside 
        initial={{ width: 280 }}
        animate={{ width: sidebarOpen ? 280 : 80 }}
        className="bg-slate-900 text-slate-300 flex flex-col shadow-2xl z-20 relative"
      >
        <div className="p-6 flex items-center justify-between border-b border-slate-800">
          <div className={clsx("flex items-center gap-3 overflow-hidden", !sidebarOpen && "justify-center w-full")}>
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center shrink-0 shadow-lg shadow-blue-900/50">
              <ShieldAlert className="text-white" size={18} />
            </div>
            {sidebarOpen && (
              <motion.div 
                initial={{ opacity: 0 }} 
                animate={{ opacity: 1 }}
                className="font-bold text-white tracking-tight whitespace-nowrap"
              >
                PRISM <span className="text-slate-500 font-normal">Gov</span>
              </motion.div>
            )}
          </div>
          {sidebarOpen && (
            <button onClick={() => setSidebarOpen(false)} className="text-slate-500 hover:text-white transition-colors">
              <ChevronLeft size={20} />
            </button>
          )}
        </div>

        {!sidebarOpen && (
           <button onClick={() => setSidebarOpen(true)} className="p-4 flex justify-center text-slate-500 hover:text-white transition-colors border-b border-slate-800">
             <Menu size={20} />
           </button>
        )}

        <nav className="flex-1 p-4 space-y-2" role="navigation" aria-label="Main navigation">
          <NavItem 
            icon={<MapIcon size={20} />} 
            label="Live Map" 
            active={activeView === 'map'} 
            collapsed={!sidebarOpen}
            onClick={() => setActiveView('map')}
          />
          <NavItem 
            icon={<Landmark size={20} />} 
            label="Gov Data Dashboard" 
            active={showGovernmentDashboard} 
            collapsed={!sidebarOpen}
            onClick={() => setShowGovernmentDashboard(true)}
          />
          <NavItem 
            icon={<TrendingDown size={20} />} 
            label="Highway Forecaster" 
            active={showHighwayDegradation} 
            collapsed={!sidebarOpen}
            onClick={() => setShowHighwayDegradation(true)}
          />
          <NavItem 
            icon={<LayoutDashboard size={20} />} 
            label="Risk Dashboard" 
            active={activeView === 'dashboard'} 
            collapsed={!sidebarOpen}
            onClick={() => setShowDashboard(true)}
          />
          <div className="pt-4 pb-2">
            <div className={clsx("text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2", !sidebarOpen && "hidden")}>
              Tools
            </div>
            <NavItem 
              icon={<Settings size={20} />} 
              label="Budget Optimizer" 
              active={showOptimizer} 
              collapsed={!sidebarOpen}
              onClick={() => setShowOptimizer(true)}
            />
          </div>
        </nav>

        <div className="p-4 border-t border-slate-800 bg-slate-950/50">
          <div className={clsx("flex items-center gap-3", !sidebarOpen && "justify-center")}>
            <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-xs font-bold text-white">
              JD
            </div>
            {sidebarOpen && (
              <div className="overflow-hidden">
                <div className="text-sm font-medium text-white truncate">John Doe</div>
                <div className="text-xs text-slate-500 truncate">Infrastructure Minister</div>
              </div>
            )}
          </div>
        </div>
      </motion.aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col relative overflow-hidden">
        {/* Map Background */}
        <div className="flex-1 relative bg-slate-100">
          <LiveMap 
            assets={assets} 
            nlBridges={nlBridges}
            nlDataSource={nlDataSource}
            onBridgeSelect={handleBridgeSelect} 
          />
        </div>

        {/* Bottom Command Bar */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 w-full max-w-2xl z-[2000] px-4">
          <NLQuery onResults={handleQueryResults} />
        </div>
      </main>

      {/* Selected Bridge Panel */}
      <AnimatePresence>
        {selectedBridge && (
          <motion.div
            initial={{ x: 300, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 300, opacity: 0 }}
            className="absolute right-0 top-0 h-full w-80 bg-white shadow-2xl z-[2000] overflow-y-auto"
          >
            <div className="p-4 border-b border-slate-200 flex justify-between items-center sticky top-0 bg-white">
              <h3 className="font-bold text-slate-900">Bridge Details</h3>
              <button 
                onClick={() => setSelectedBridge(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <h4 className="font-semibold text-lg text-slate-900">{selectedBridge.name}</h4>
                <p className="text-sm text-slate-500">{selectedBridge.region}</p>
              </div>
              
              <div className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
                ['critical', 'very_poor'].includes(selectedBridge.condition.toLowerCase()) 
                  ? 'bg-red-100 text-red-700' 
                  : selectedBridge.condition.toLowerCase() === 'poor' 
                    ? 'bg-orange-100 text-orange-700'
                    : selectedBridge.condition.toLowerCase() === 'fair'
                      ? 'bg-yellow-100 text-yellow-700'
                      : 'bg-green-100 text-green-700'
              }`}>
                {selectedBridge.condition}
              </div>

              <div className="space-y-2 text-sm">
                {selectedBridge.highway && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Highway</span>
                    <span className="font-medium text-slate-900">{selectedBridge.highway}</span>
                  </div>
                )}
                {selectedBridge.county && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Area</span>
                    <span className="font-medium text-slate-900">{selectedBridge.county}</span>
                  </div>
                )}
                {selectedBridge.year_built && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Year Built</span>
                    <span className="font-medium text-slate-900">{selectedBridge.year_built}</span>
                  </div>
                )}
                {selectedBridge.structure_type && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Structure Type</span>
                    <span className="font-medium text-slate-900">{selectedBridge.structure_type}</span>
                  </div>
                )}
                {selectedBridge.owner && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Owner</span>
                    <span className="font-medium text-slate-900">{selectedBridge.owner}</span>
                  </div>
                )}
                {selectedBridge.last_inspection && (
                  <div className="flex justify-between">
                    <span className="text-slate-500">Last Inspection</span>
                    <span className="font-medium text-slate-900">{selectedBridge.last_inspection}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-slate-500">Coordinates</span>
                  <span className="font-medium text-slate-900 text-xs">
                    {selectedBridge.latitude.toFixed(4)}, {selectedBridge.longitude.toFixed(4)}
                  </span>
                </div>
              </div>

              {selectedBridge.source && (
                <div className="pt-2 border-t border-slate-100">
                  <p className="text-xs text-slate-400">Source: {selectedBridge.source}</p>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Modals with AnimatePresence */}
      <AnimatePresence>
        {showOptimizer && <Optimizer onClose={() => setShowOptimizer(false)} />}
        {showDashboard && <RiskDashboard assets={assets} onClose={() => setShowDashboard(false)} />}
        {showGovernmentDashboard && <GovernmentDashboard onClose={() => setShowGovernmentDashboard(false)} />}
        {showHighwayDegradation && <HighwayDegradation onClose={() => setShowHighwayDegradation(false)} />}
      </AnimatePresence>
    </div>
  );
}

// Helper Components
function NavItem({ icon, label, active, collapsed, onClick }: any) {
  return (
    <button 
      onClick={onClick}
      className={clsx(
        "w-full flex items-center gap-3 p-3 rounded-xl transition-all duration-200 group",
        active 
          ? "bg-blue-600 text-white shadow-lg shadow-blue-900/20" 
          : "text-slate-400 hover:bg-slate-800 hover:text-white",
        collapsed && "justify-center"
      )}
    >
      <div className={clsx("shrink-0", active ? "text-white" : "text-slate-400 group-hover:text-white")}>
        {icon}
      </div>
      {!collapsed && (
        <span className="text-sm font-medium whitespace-nowrap">{label}</span>
      )}
    </button>
  );
}

function LegendItem({ color, label }: any) {
  return (
    <div className="flex items-center gap-3">
      <span className={clsx("w-2.5 h-2.5 rounded-full shadow-sm ring-1 ring-white/50", color)}></span>
      <span className="text-xs font-medium text-slate-600">{label}</span>
    </div>
  );
}
