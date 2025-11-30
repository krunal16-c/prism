"use client";

import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { BridgeLocation, CONDITION_COLORS } from "@/types";

// Province center coordinates for map positioning
const PROVINCE_CENTERS: Record<string, { lat: number; lng: number; zoom: number }> = {
  "Ontario": { lat: 51.2538, lng: -85.3232, zoom: 5 },
  "Quebec": { lat: 52.9399, lng: -73.5491, zoom: 5 },
  "British Columbia": { lat: 53.7267, lng: -127.6476, zoom: 5 },
  "Alberta": { lat: 53.9333, lng: -116.5765, zoom: 5 },
  "Manitoba": { lat: 53.7609, lng: -98.8139, zoom: 5 },
  "Saskatchewan": { lat: 52.9399, lng: -106.4509, zoom: 5 },
  "Nova Scotia": { lat: 44.6820, lng: -63.7443, zoom: 7 },
  "New Brunswick": { lat: 46.5653, lng: -66.4619, zoom: 7 },
  "Newfoundland and Labrador": { lat: 53.1355, lng: -57.6604, zoom: 5 },
  "Prince Edward Island": { lat: 46.5107, lng: -63.4168, zoom: 9 },
  "Northwest Territories": { lat: 64.8255, lng: -124.8457, zoom: 4 },
  "Yukon": { lat: 64.2823, lng: -135.0000, zoom: 5 },
  "Nunavut": { lat: 70.2998, lng: -83.1076, zoom: 3 },
};

// Component to handle map recentering when region changes
function MapController({ region }: { region: string }) {
  const map = useMap();
  
  useEffect(() => {
    const center = PROVINCE_CENTERS[region];
    if (center) {
      map.setView([center.lat, center.lng], center.zoom, {
        animate: true,
        duration: 1,
      });
    }
  }, [region, map]);
  
  return null;
}

interface GovernmentMapProps {
  bridges: BridgeLocation[];
  region: string;
}

export default function GovernmentMap({ bridges, region }: GovernmentMapProps) {
  const center = PROVINCE_CENTERS[region] || PROVINCE_CENTERS["Ontario"];
  
  // Memoize bridge markers for performance
  const bridgeMarkers = useMemo(() => {
    return bridges.map((bridge) => {
      const color = CONDITION_COLORS[bridge.condition] || CONDITION_COLORS["Unknown"];
      
      return (
        <CircleMarker
          key={bridge.id}
          center={[bridge.latitude, bridge.longitude]}
          radius={6}
          pathOptions={{
            color: "#ffffff",
            weight: 2,
            fillColor: color,
            fillOpacity: 0.9,
          }}
        >
          <Popup>
            <div className="p-2 min-w-[200px]">
              <h4 className="font-bold text-slate-900 text-sm mb-2">{bridge.name}</h4>
              <div className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Condition:</span>
                  <span 
                    className="font-semibold px-2 py-0.5 rounded"
                    style={{ 
                      backgroundColor: `${color}20`,
                      color: color
                    }}
                  >
                    {bridge.condition}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Year Built:</span>
                  <span className="font-medium text-slate-700">{bridge.year_built}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Last Inspection:</span>
                  <span className="font-medium text-slate-700">{bridge.last_inspection}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">ID:</span>
                  <span className="font-mono text-slate-600">{bridge.id}</span>
                </div>
              </div>
            </div>
          </Popup>
        </CircleMarker>
      );
    });
  }, [bridges]);

  return (
    <MapContainer
      center={[center.lat, center.lng]}
      zoom={center.zoom}
      style={{ height: "100%", width: "100%" }}
      scrollWheelZoom={true}
      className="rounded-xl"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
      />
      <MapController region={region} />
      {bridgeMarkers}
    </MapContainer>
  );
}
