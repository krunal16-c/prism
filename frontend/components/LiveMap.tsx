"use client";

import { useEffect, useState, useCallback } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { BridgeLocation, Asset } from "@/types";
import axios from "axios";
import { RefreshCw, Database, Globe, Filter, X, Loader2, Sparkles } from "lucide-react";

// Custom colored icons based on bridge condition
const getConditionIcon = (condition: string) => {
  let colorClass = "bg-gray-400";
  
  switch (condition.toLowerCase()) {
    case "critical":
    case "very_poor":
      colorClass = "bg-red-600";
      break;
    case "poor":
      colorClass = "bg-orange-500";
      break;
    case "fair":
      colorClass = "bg-yellow-400";
      break;
    case "good":
    case "very_good":
      colorClass = "bg-green-500";
      break;
    default:
      colorClass = "bg-gray-400";
  }

  return L.divIcon({
    className: "custom-marker",
    html: `<div class="${colorClass} w-3 h-3 rounded-full border-2 border-white shadow-md"></div>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6],
    popupAnchor: [0, -8],
  });
};

// Custom icon based on risk score (for original assets)
const getRiskIcon = (riskScore: number) => {
  let colorClass = "bg-green-500";
  if (riskScore >= 75) colorClass = "bg-red-600";
  else if (riskScore >= 50) colorClass = "bg-orange-500";
  else if (riskScore >= 25) colorClass = "bg-yellow-400";

  return L.divIcon({
    className: "custom-marker",
    html: `<div class="${colorClass} w-4 h-4 rounded-full border-2 border-white shadow-md"></div>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    popupAnchor: [0, -10],
  });
};

// Component to handle map view updates
function MapViewController({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, zoom);
  }, [center, zoom, map]);
  return null;
}

interface LiveMapProps {
  assets?: Asset[];
  nlBridges?: BridgeLocation[];
  nlDataSource?: string | null;
  onBridgeSelect?: (bridge: BridgeLocation) => void;
}

export default function LiveMap({ assets = [], nlBridges = [], nlDataSource, onBridgeSelect }: LiveMapProps) {
  const [bridges, setBridges] = useState<BridgeLocation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedRegion, setSelectedRegion] = useState("British Columbia");
  const [regions, setRegions] = useState<string[]>([]);
  const [dataSource, setDataSource] = useState<'government' | 'assets' | 'nlp'>('government');
  const [conditionFilter, setConditionFilter] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [cacheStatus, setCacheStatus] = useState<{ cached: boolean; age_hours?: number } | null>(null);
  const [mapCenter, setMapCenter] = useState<[number, number]>([53.7267, -127.6476]);
  const [mapZoom, setMapZoom] = useState(5);

  // Switch to NLP results when available
  useEffect(() => {
    if (nlBridges && nlBridges.length > 0 && nlDataSource === 'bridges') {
      setDataSource('nlp');
      setBridges(nlBridges);
      // Center map on first bridge
      if (nlBridges[0]) {
        setMapCenter([nlBridges[0].latitude, nlBridges[0].longitude]);
        setMapZoom(7);
      }
    }
  }, [nlBridges, nlDataSource]);

  // Province centers for map navigation
  const provinceCenters: Record<string, [number, number]> = {
    "British Columbia": [53.7267, -127.6476],
    "Alberta": [53.9333, -116.5765],
    "Saskatchewan": [52.9399, -106.4509],
    "Manitoba": [53.7609, -98.8139],
    "Ontario": [51.2538, -85.3232],
    "Quebec": [52.9399, -73.5491],
    "New Brunswick": [46.5653, -66.4619],
    "Nova Scotia": [44.6820, -63.7443],
    "Prince Edward Island": [46.5107, -63.4168],
    "Newfoundland and Labrador": [53.1355, -57.6604],
  };

  // Fetch available regions
  useEffect(() => {
    const fetchRegions = async () => {
      try {
        const response = await axios.get("http://localhost:8000/api/dashboard/regions");
        setRegions(response.data.regions || []);
      } catch (err) {
        console.error("Failed to fetch regions:", err);
        setRegions(Object.keys(provinceCenters));
      }
    };
    fetchRegions();
  }, []);

  // Fetch bridges for selected region
  const fetchBridges = useCallback(async (forceRefresh = false) => {
    if (dataSource === 'assets' || dataSource === 'nlp') return;
    
    setLoading(true);
    setError(null);
    
    try {
      const url = `http://localhost:8000/api/dashboard/bridges/${encodeURIComponent(selectedRegion)}?limit=200${forceRefresh ? '&force_refresh=true' : ''}`;
      const response = await axios.get(url);
      setBridges(response.data.bridges || []);
      
      // Update map center to selected region
      if (provinceCenters[selectedRegion]) {
        setMapCenter(provinceCenters[selectedRegion]);
        setMapZoom(6);
      }
      
      // Fetch cache status
      try {
        const cacheResponse = await axios.get(`http://localhost:8000/api/cache/status?region=${encodeURIComponent(selectedRegion)}`);
        setCacheStatus(cacheResponse.data);
      } catch {
        setCacheStatus(null);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load bridges");
      setBridges([]);
    } finally {
      setLoading(false);
    }
  }, [selectedRegion, dataSource]);

  useEffect(() => {
    if (dataSource === 'government') {
      fetchBridges();
    }
  }, [selectedRegion, dataSource, fetchBridges]);

  // Get display bridges (either from NLP, government data, or filter)
  const displayBridges = dataSource === 'nlp' ? nlBridges : bridges;
  
  // Filter bridges by condition
  const filteredBridges = conditionFilter
    ? displayBridges.filter(b => b.condition.toLowerCase() === conditionFilter.toLowerCase())
    : displayBridges;

  // Get condition counts from display bridges
  const conditionCounts = displayBridges.reduce((acc, b) => {
    const condition = b.condition || 'Unknown';
    acc[condition] = (acc[condition] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  // Calculate stats from display bridges (not just 'bridges')
  const criticalCount = displayBridges.filter(b => 
    ['critical', 'very_poor'].includes(b.condition.toLowerCase())
  ).length;
  
  const poorCount = displayBridges.filter(b => 
    b.condition.toLowerCase() === 'poor'
  ).length;

  return (
    <div className="relative w-full h-full">
      {/* Controls Panel */}
      <div className="absolute top-4 left-4 z-[1000] bg-white/95 backdrop-blur-md rounded-xl shadow-lg border border-slate-200 p-3 space-y-3 max-w-xs">
        {/* NLP Results Banner */}
        {dataSource === 'nlp' && nlBridges.length > 0 && (
          <div className="flex items-center justify-between bg-purple-50 border border-purple-200 rounded-lg px-3 py-2">
            <div className="flex items-center gap-2">
              <Sparkles size={14} className="text-purple-600" />
              <span className="text-xs font-medium text-purple-700">
                NLP Query Results ({nlBridges.length})
              </span>
            </div>
            <button 
              onClick={() => setDataSource('government')}
              className="text-xs text-purple-600 hover:text-purple-800 font-medium"
            >
              Clear
            </button>
          </div>
        )}

        {/* Data Source Toggle */}
        <div className="flex gap-1 p-1 bg-slate-100 rounded-lg">
          <button
            onClick={() => setDataSource('government')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-md text-xs font-medium transition-all ${
              dataSource === 'government' 
                ? 'bg-white text-blue-600 shadow-sm' 
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            <Database size={14} />
            Gov Data
          </button>
          <button
            onClick={() => setDataSource('assets')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-md text-xs font-medium transition-all ${
              dataSource === 'assets' 
                ? 'bg-white text-blue-600 shadow-sm' 
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            <Globe size={14} />
            Assets
          </button>
        </div>

        {/* Region Selector (only for government data) */}
        {(dataSource === 'government' || dataSource === 'nlp') && (
          <>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Region</label>
              <select
                value={selectedRegion}
                onChange={(e) => { setSelectedRegion(e.target.value); if (dataSource === 'nlp') setDataSource('government'); }}
                className="w-full text-sm border border-slate-200 rounded-lg px-2 py-1.5 bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                disabled={dataSource === 'nlp'}
              >
                {regions.map(region => (
                  <option key={region} value={region}>{region}</option>
                ))}
              </select>
            </div>

            {/* Filter Button */}
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="flex items-center gap-2 text-xs text-slate-600 hover:text-blue-600 transition-colors"
            >
              <Filter size={14} />
              Filter by Condition
              {conditionFilter && (
                <span className="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded text-xs">
                  {conditionFilter}
                </span>
              )}
            </button>

            {/* Condition Filters */}
            {showFilters && (
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(conditionCounts).map(([condition, count]) => (
                  <button
                    key={condition}
                    onClick={() => setConditionFilter(
                      conditionFilter === condition ? null : condition
                    )}
                    className={`text-xs px-2 py-1 rounded-full border transition-all ${
                      conditionFilter === condition
                        ? 'bg-blue-600 text-white border-blue-600'
                        : 'bg-white text-slate-600 border-slate-200 hover:border-blue-300'
                    }`}
                  >
                    {condition} ({count})
                  </button>
                ))}
                {conditionFilter && (
                  <button
                    onClick={() => setConditionFilter(null)}
                    className="text-xs px-2 py-1 rounded-full bg-red-50 text-red-600 border border-red-200 hover:bg-red-100"
                  >
                    <X size={12} />
                  </button>
                )}
              </div>
            )}

            {/* Refresh & Cache Status */}
            <div className="flex items-center justify-between pt-2 border-t border-slate-100">
              <div className="text-xs text-slate-500">
                {cacheStatus?.cached ? (
                  <span className="flex items-center gap-1">
                    <Database size={12} className="text-green-500" />
                    Cached {cacheStatus.age_hours !== undefined ? `${Math.round(cacheStatus.age_hours)}h ago` : ''}
                  </span>
                ) : (
                  <span>Live data</span>
                )}
              </div>
              <button
                onClick={() => fetchBridges(true)}
                disabled={loading}
                className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 disabled:opacity-50"
              >
                <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
                Refresh
              </button>
            </div>
          </>
        )}
      </div>

      {/* Stats Panel */}
      <div className="absolute top-4 right-4 z-[1000] bg-white/95 backdrop-blur-md rounded-xl shadow-lg border border-slate-200 p-4 w-56">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
          {dataSource === 'nlp' ? 'NLP Query Results' : dataSource === 'government' ? 'Bridge Status' : 'Asset Status'}
        </h3>
        
        {loading ? (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="animate-spin text-blue-600" size={20} />
          </div>
        ) : (dataSource === 'government' || dataSource === 'nlp') ? (
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm text-slate-600">Total Bridges</span>
              <span className="text-sm font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded-full">
                {filteredBridges.length}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-slate-600">Critical</span>
              <span className="text-sm font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded-full border border-red-100">
                {criticalCount}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-slate-600">Poor</span>
              <span className="text-sm font-bold text-orange-600 bg-orange-50 px-2 py-0.5 rounded-full border border-orange-100">
                {poorCount}
              </span>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm text-slate-600">Active Assets</span>
              <span className="text-sm font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded-full">
                {assets.length}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-slate-600">High Risk</span>
              <span className="text-sm font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded-full border border-red-100">
                {assets.filter(a => (a.risk_scores?.[a.risk_scores.length - 1]?.overall_score || 0) >= 75).length}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Legend - positioned above the NLP query bar */}
      <div className="absolute bottom-20 left-4 z-[1000] bg-white/95 backdrop-blur-md rounded-xl shadow-lg border border-slate-200 p-4">
        <h4 className="text-xs font-bold text-slate-900 mb-3">
          {(dataSource === 'government' || dataSource === 'nlp') ? 'Bridge Condition' : 'Risk Severity'}
        </h4>
        {(dataSource === 'government' || dataSource === 'nlp') ? (
          <div className="space-y-2">
            <LegendItem color="bg-red-600" label="Critical/Very Poor" />
            <LegendItem color="bg-orange-500" label="Poor" />
            <LegendItem color="bg-yellow-400" label="Fair" />
            <LegendItem color="bg-green-500" label="Good/Very Good" />
            <LegendItem color="bg-gray-400" label="Unknown" />
          </div>
        ) : (
          <div className="space-y-2">
            <LegendItem color="bg-red-500" label="Critical (75-100)" />
            <LegendItem color="bg-orange-500" label="High (50-74)" />
            <LegendItem color="bg-yellow-400" label="Medium (25-49)" />
            <LegendItem color="bg-green-500" label="Low (0-24)" />
          </div>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="absolute top-20 left-1/2 -translate-x-1/2 z-[1000] bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Map */}
      <MapContainer
        center={mapCenter}
        zoom={mapZoom}
        style={{ height: "100%", width: "100%" }}
      >
        <MapViewController center={mapCenter} zoom={mapZoom} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        
        {/* Government Bridge Data or NLP Results */}
        {(dataSource === 'government' || dataSource === 'nlp') && filteredBridges.map((bridge) => (
          <Marker
            key={bridge.id}
            position={[bridge.latitude, bridge.longitude]}
            icon={getConditionIcon(bridge.condition)}
            eventHandlers={{
              click: () => onBridgeSelect?.(bridge)
            }}
          >
            <Popup>
              <div className="p-2 min-w-[200px]">
                <h3 className="font-bold text-sm mb-1">{bridge.name}</h3>
                <div className="text-xs space-y-1 text-slate-600">
                  <p><span className="font-medium">Condition:</span> 
                    <span className={`ml-1 px-1.5 py-0.5 rounded text-white ${
                      ['critical', 'very_poor'].includes(bridge.condition.toLowerCase()) ? 'bg-red-600' :
                      bridge.condition.toLowerCase() === 'poor' ? 'bg-orange-500' :
                      bridge.condition.toLowerCase() === 'fair' ? 'bg-yellow-500' :
                      'bg-green-500'
                    }`}>
                      {bridge.condition}
                    </span>
                  </p>
                  {bridge.highway && <p><span className="font-medium">Highway:</span> {bridge.highway}</p>}
                  {bridge.county && <p><span className="font-medium">Area:</span> {bridge.county}</p>}
                  {bridge.year_built && <p><span className="font-medium">Built:</span> {bridge.year_built}</p>}
                  {bridge.structure_type && <p><span className="font-medium">Type:</span> {bridge.structure_type}</p>}
                  {bridge.owner && <p><span className="font-medium">Owner:</span> {bridge.owner}</p>}
                  {bridge.last_inspection && <p><span className="font-medium">Last Inspection:</span> {bridge.last_inspection}</p>}
                </div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* Original Asset Data */}
        {dataSource === 'assets' && assets.map((asset) => {
          const riskScore = asset.risk_scores?.length > 0 
            ? asset.risk_scores[asset.risk_scores.length - 1].overall_score 
            : 0;
          
          return (
            <Marker
              key={asset.id}
              position={[asset.latitude, asset.longitude]}
              icon={getRiskIcon(riskScore)}
            >
              <Popup>
                <div className="p-2">
                  <h3 className="font-bold text-lg">{asset.name}</h3>
                  <p className="text-sm text-gray-600">{asset.type} • {asset.province}</p>
                  <div className="mt-2">
                    <span className={`font-bold ${
                      riskScore >= 75 ? 'text-red-600' : 
                      riskScore >= 50 ? 'text-orange-500' : 
                      'text-green-600'
                    }`}>
                      Risk Score: {riskScore.toFixed(1)}
                    </span>
                  </div>
                  <p className="text-xs mt-1">Daily Usage: {asset.daily_usage?.toLocaleString()}</p>
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className={`w-2.5 h-2.5 rounded-full shadow-sm ring-1 ring-white/50 ${color}`}></span>
      <span className="text-xs font-medium text-slate-600">{label}</span>
    </div>
  );
}
